"""Orquestração: roda a matriz, gera ações, dispara cobranças.

Uma rodada faz três coisas, nesta ordem:
  1. mede e julga cada KPI devido agora;
  2. abre ação para o que está vermelho;
  3. varre o que já estava aberto e cobra quem não respondeu.

O passo 3 é independente do 1: mesmo numa rodada em que tudo esteja verde,
as cobranças pendentes de ontem continuam subindo a escada.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from .acoes import Acao, Estado, criar, formatar
from .avaliador import Nivel, Sinal, avaliar
from .cobranca import Cobranca, aplicar, proxima_cobranca
from .config import RAIZ, Config
from .notificadores.base import Mensagem, Notificador
from .repositorio import Repositorio
from .respostas import marcar
from .sankhya import Fonte, FonteArquivo, montar_sql

# Link do painel publicado. Quem é cobrado responde LÁ, não no terminal —
# a maior parte dos donos nunca vai abrir um shell.
PAINEL = os.getenv(
    "NITRONCEO_PAINEL", "https://claude.ai/artifact/3aE3YSU2uJY5QW4PHDfsqz"
)

class Redator(Protocol):
    """Quem sabe escrever a cobrança melhor que o template.

    Implementado por `analista.Renato`. Devolver None ou levantar exceção
    é resposta válida: o motor volta ao texto determinístico e segue.
    """

    def texto_cobranca(
        self, acao: Acao, sinal: Sinal, kpi: dict[str, Any]
    ) -> str | None: ...


# Quanto tempo uma resposta por e-mail segura os lembretes. É a promessa
# feita no corpo da cobrança, e ela tem que valer: responder e ser cobrado
# na rodada seguinte é a forma mais rápida de ensinar a ignorar o sistema.
# Não encerra nada — só compra silêncio até a pessoa ter tempo de agir.
CARENCIA_APOS_RESPOSTA_H = float(os.getenv("NITRONCEO_CARENCIA_H", "24"))

ICONE = {
    Nivel.VERDE: "🟢",
    Nivel.AMARELO: "🟡",
    Nivel.VERMELHO: "🔴",
    Nivel.CRITICO: "🚨",
}


@dataclass
class Rodada:
    sinais: list[Sinal] = field(default_factory=list)
    acoes_novas: list[Acao] = field(default_factory=list)
    cobrancas: list[Cobranca] = field(default_factory=list)
    falhas: list[tuple[str, str]] = field(default_factory=list)
    falhas_de_redacao: list[tuple[str, str]] = field(default_factory=list)
    desvios: list[tuple[str, str]] = field(default_factory=list)
    falhas_de_envio: list[tuple[str, str, str]] = field(default_factory=list)


class Motor:
    def __init__(
        self,
        cfg: Config,
        fonte: Fonte,
        repo: Repositorio,
        notificadores: dict[str, Notificador],
        raiz: Path = RAIZ,
        redator: Redator | None = None,
        fallback: str | None = None,
    ) -> None:
        self.cfg = cfg
        self.fonte = fonte
        self.repo = repo
        self.notificadores = notificadores
        self.raiz = Path(raiz)
        # Quem escreve o corpo da cobrança. Sem redator, o texto é o
        # determinístico de sempre — que é o certo por padrão: o modelo
        # pode cair, e uma cobrança que não sai é pior que uma genérica.
        self.redator = redator
        self.falhas_de_redacao: list[tuple[str, str]] = []
        # Canal usado quando o que a matriz pediu não está no ar. A matriz
        # foi escrita supondo Teams; rodar só com e-mail não pode significar
        # que o amarelo inteiro emudece.
        self.fallback = fallback
        self.desvios: list[tuple[str, str]] = []
        self.falhas_de_envio: list[tuple[str, str, str]] = []

    # ------------------------------------------------------------------ medir

    def medir(self, kpi: dict[str, Any]) -> Sinal:
        sql = montar_sql(self.raiz / kpi["sql"], self.cfg.params)
        fonte = self.fonte
        if isinstance(fonte, FonteArquivo):
            fonte = fonte.para(kpi["id"])
        return avaliar(kpi, fonte.consultar(sql))

    # ------------------------------------------------------------------ rodar

    def rodar(self, apenas: list[str] | None = None, cobrar: bool = True) -> Rodada:
        rodada = Rodada()
        self.falhas_de_redacao = []
        self.desvios = []
        self.falhas_de_envio = []

        for kpi in self.cfg.matriz["kpis"]:
            if apenas and kpi["id"] not in apenas:
                continue
            try:
                sinal = self.medir(kpi)
            except Exception as exc:  # a falha de um KPI não derruba os outros
                rodada.falhas.append((kpi["id"], str(exc)))
                continue

            self.repo.gravar_sinal(sinal)
            rodada.sinais.append(sinal)

            acao = criar(sinal, kpi)
            if acao and sinal.notificavel:
                if self.repo.salvar_acao(acao):
                    rodada.acoes_novas.append(acao)
                    self._notificar_abertura(acao, sinal, kpi)

        if cobrar:
            rodada.cobrancas = self.cobrar_pendentes()

        rodada.falhas_de_redacao = list(self.falhas_de_redacao)
        rodada.desvios = list(self.desvios)
        rodada.falhas_de_envio = list(self.falhas_de_envio)
        return rodada

    # ----------------------------------------------------------------- cobrar

    def cobrar_pendentes(self) -> list[Cobranca]:
        disparadas: list[Cobranca] = []
        for acao in self.repo.acoes_em_aberto():
            cobranca = proxima_cobranca(acao, self.cfg)
            if not cobranca:
                continue
            if self.repo.respondeu_nas_ultimas(acao.id, CARENCIA_APOS_RESPOSTA_H):
                # Respondeu há pouco: o assunto não fechou, mas cobrar de
                # novo agora seria cobrar quem já se manifestou.
                continue
            self._notificar_cobranca(cobranca)
            novo_estado = aplicar(acao, cobranca)
            self.repo.atualizar_estado(acao.id, novo_estado, acao.escalonamentos)
            self.repo.registrar_cobranca(
                acao.id, cobranca.rodada,
                ", ".join(self.cfg.papel(cobranca.destinatario).emails),
                "teams", cobranca.motivo,
            )
            disparadas.append(cobranca)
        return disparadas

    # ------------------------------------------------------------- mensagens

    def _notificar_abertura(self, acao: Acao, sinal: Sinal, kpi: dict[str, Any]) -> None:
        papel = self.cfg.papel(acao.dono)
        canais = kpi["notificar"].get(sinal.nivel.canais_de, [])
        if not canais:
            return

        reincidencia = self.repo.dias_consecutivos_ruins(kpi["id"])
        msg = Mensagem(
            assunto=f"{ICONE[sinal.nivel]} {marcar(acao.id)} {acao.titulo}",
            corpo_md=self._corpo(acao, sinal, kpi, reincidencia),
            destinatarios=papel.emails,
            upns=papel.upns,
            contatos_ghl=papel.contatos_ghl,
            urgente=sinal.nivel is Nivel.CRITICO,
            canal_equipe=self.cfg.canal_teams(kpi.get("canal_teams")),
        )
        self._despachar(canais, msg, papel.emails)

    def _notificar_cobranca(self, cobranca: Cobranca) -> None:
        papel = self.cfg.papel(cobranca.destinatario)
        acao = cobranca.acao
        corpo = [
            f"**{acao.titulo}**",
            "",
            cobranca.motivo,
            "",
            f"Aberta em {acao.criada_em:%d/%m %H:%M}, prazo era "
            f"{acao.prazo:%d/%m %H:%M}.",
            "",
            "O que estava pedido:",
        ]
        corpo += [f"- {p}" for p in acao.passos]
        corpo += [
            "",
            f"**Responda neste e-mail** ou no painel: {PAINEL}#cob-{acao.id}",
        ]

        prefixo = "ESCALADA" if cobranca.escalada else "COBRANÇA"
        msg = Mensagem(
            assunto=f"⏰ {prefixo} {marcar(acao.id)}: {acao.titulo}",
            corpo_md="\n".join(corpo),
            destinatarios=papel.emails,
            upns=papel.upns,
            contatos_ghl=papel.contatos_ghl,
            urgente=cobranca.urgente,
        )
        canais = ["teams", "email"] if cobranca.escalada else ["teams"]
        self._despachar(canais, msg, papel.emails)

    def _corpo(
        self, acao: Acao, sinal: Sinal, kpi: dict[str, Any], reincidencia: int
    ) -> str:
        """Texto da cobrança: do redator quando ele responde, do template
        quando não. A falha do redator nunca impede o disparo."""
        if self.redator is not None:
            try:
                escrito = self.redator.texto_cobranca(acao, sinal, kpi)
            except Exception as exc:
                self.falhas_de_redacao.append((acao.id, str(exc)))
                escrito = None
            if escrito:
                return "\n".join([escrito, "", *self._rodape(acao, sinal, kpi)])
        return self._corpo_acao(acao, sinal, kpi, reincidencia)

    def _rodape(self, acao: Acao, sinal: Sinal, kpi: dict[str, Any]) -> list[str]:
        """O que é do sistema, não do redator: prazo, link e procedência."""
        return [
            f"Prazo de resposta: {acao.prazo:%d/%m às %H:%M} "
            f"({acao.horas_restantes():.0f}h).",
            f"**Responda neste e-mail** ou no painel: {PAINEL}#cob-{acao.id}",
            f"Responder já me avisa e segura os lembretes por "
            f"{CARENCIA_APOS_RESPOSTA_H:.0f}h. Para encerrar de vez, comece a "
            "resposta com **RESOLVIDO** — um retorno parcial é bem-vindo e "
            "mantém a ação aberta, que é o certo.",
            "",
            f"_Base do número: {kpi['sql']} — apurado em "
            f"{sinal.medido_em:%d/%m/%Y %H:%M}._",
        ]

    def _corpo_acao(
        self, acao: Acao, sinal: Sinal, kpi: dict[str, Any], reincidencia: int
    ) -> str:
        linhas = [
            f"**{kpi['pergunta']}**",
            "",
            f"{ICONE[sinal.nivel]} {sinal.titulo}: **{acao.titulo}**",
        ]

        if reincidencia >= 3:
            linhas += [
                "",
                f"⚠️ {reincidencia}º dia seguido neste nível. Não é um dia ruim — "
                "é uma tendência, e a resposta precisa tratar a causa.",
            ]

        contexto = {
            k: v for k, v in acao.contexto.items()
            if k not in (kpi["metrica"], "LISTA") and not isinstance(v, str)
        }
        if contexto:
            linhas += ["", "Números da apuração:"]
            linhas += [f"- {k}: {v}" for k, v in list(contexto.items())[:8]]

        if acao.contexto.get("LISTA"):
            linhas += ["", f"Detalhe: {acao.contexto['LISTA']}"]

        linhas += ["", "**O que preciso de você:**"]
        linhas += [f"- {p}" for p in acao.passos]
        linhas += [
            "",
            f"Prazo de resposta: {acao.prazo:%d/%m às %H:%M} "
            f"({acao.horas_restantes():.0f}h).",
            f"**Responda neste e-mail** ou no painel: {PAINEL}#cob-{acao.id}",
            f"Responder já me avisa e segura os lembretes por "
            f"{CARENCIA_APOS_RESPOSTA_H:.0f}h. Para encerrar de vez, comece a "
            "resposta com **RESOLVIDO**. Um retorno parcial é bem-vindo e "
            "mantém a ação aberta — é assim que tem que ser.",
            "",
            f"_Base do número: {kpi['sql']} — apurado em "
            f"{sinal.medido_em:%d/%m/%Y %H:%M}._",
        ]
        return "\n".join(linhas)

    def _canais_vivos(self, pedidos: list[str]) -> list[str]:
        """Os canais que a matriz pediu e que estão realmente configurados.

        Quando nenhum está, cai no fallback em vez de emudecer: uma cobrança
        no canal errado ainda chega na pessoa; uma cobrança que não sai não
        chega em lugar nenhum.
        """
        vivos = [c for c in pedidos if c in self.notificadores]
        if vivos or not pedidos:
            return vivos
        if self.fallback and self.fallback in self.notificadores:
            self.desvios.append((",".join(pedidos), self.fallback))
            return [self.fallback]
        return []

    def _despachar(
        self, canais: list[str], msg: Mensagem, emails: list[str]
    ) -> None:
        for canal in self._canais_vivos(canais):
            notificador = self.notificadores.get(canal)
            if not notificador:
                continue
            alvo = msg
            if canal == "email":
                # O e-mail vai só para as pessoas; o canal de equipe é
                # exclusividade do Teams.
                alvo = Mensagem(
                    assunto=msg.assunto,
                    corpo_md=msg.corpo_md,
                    destinatarios=emails,
                    urgente=msg.urgente,
                )
            try:
                notificador.enviar(alvo)
            except Exception as exc:
                # Um UPN errado devolve 404 no Graph. Sem este try, a
                # primeira pessoa mal cadastrada derruba a rodada inteira e
                # as outras 36 cobranças não saem.
                self.falhas_de_envio.append((canal, msg.assunto, str(exc)))


def pulso(rodada: Rodada, cfg: Config) -> str:
    """Resumo da rodada para o CEO — o que ele leria de manhã."""
    agora = datetime.now()
    linhas = [f"## Pulso Nitron — {agora:%d/%m/%Y %H:%M}", ""]

    ordem = {Nivel.CRITICO: 0, Nivel.VERMELHO: 1, Nivel.AMARELO: 2, Nivel.VERDE: 3}
    for sinal in sorted(rodada.sinais, key=lambda s: ordem[s.nivel]):
        sombra = " _(sombra)_" if sinal.modo == "sombra" else ""
        if sinal.erro:
            linhas.append(f"⚪ {sinal.titulo}: sem medição — {sinal.erro}{sombra}")
            continue
        valor = formatar(sinal.valor, sinal.unidade)
        sufixo = "%" if sinal.unidade == "percentual" else ""
        prefixo = "R$ " if sinal.unidade == "reais" else ""
        linhas.append(
            f"{ICONE[sinal.nivel]} {sinal.titulo}: {prefixo}{valor}{sufixo}{sombra}"
        )

    if rodada.acoes_novas:
        linhas += ["", "### Ações abertas agora"]
        for acao in rodada.acoes_novas:
            papel = cfg.papel(acao.dono)
            linhas.append(
                f"- [{acao.id}] {acao.titulo} — {papel.quem} "
                f"(até {acao.prazo:%d/%m %H:%M})"
            )

    if rodada.cobrancas:
        linhas += ["", "### Cobranças disparadas"]
        for c in rodada.cobrancas:
            papel = cfg.papel(c.destinatario)
            tipo = "escalada" if c.escalada else "lembrete"
            linhas.append(f"- [{c.acao.id}] {tipo} para {papel.quem}: {c.motivo}")

    if rodada.falhas:
        linhas += ["", "### KPIs que não mediram"]
        linhas += [f"- {kid}: {erro}" for kid, erro in rodada.falhas]

    if rodada.falhas_de_envio:
        # O mais grave da lista: a ação existe, o prazo corre, e a pessoa
        # não foi avisada. Vai no topo do bloco de problemas.
        linhas += ["", "### ⚠️ Cobranças que NÃO chegaram no destinatário"]
        linhas += [
            f"- [{canal}] {assunto}: {erro}"
            for canal, assunto, erro in rodada.falhas_de_envio
        ]

    if rodada.desvios:
        de_para = sorted(set(rodada.desvios))
        linhas += ["", "### Cobranças que saíram por outro canal"]
        linhas += [
            f"- a matriz pedia {pedido}, que não está configurado; foi por {usado}"
            for pedido, usado in de_para
        ]

    if rodada.falhas_de_redacao:
        # A cobrança saiu — com o texto padrão. Vale registrar porque é
        # sintoma de credencial vencida, não de problema na operação.
        linhas += ["", "### Cobranças que saíram com o texto padrão"]
        linhas += [
            f"- {aid}: o redator não respondeu — {erro}"
            for aid, erro in rodada.falhas_de_redacao
        ]

    return "\n".join(linhas)
