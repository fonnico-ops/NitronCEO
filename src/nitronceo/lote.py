"""Uma mensagem por gestor, com tudo o que é dele naquele dia.

A matriz gera uma ação por KPI. Entregá-las como uma mensagem cada faz
sentido no papel e falha na caixa de entrada: na primeira rodada real, a
produção recebeu cinco e-mails no mesmo minuto. Cinco cobranças
simultâneas não são cinco cobranças — são ruído, e ruído ensina a filtrar
o remetente.

O lote junta tudo de um dono numa mensagem só, ordenada por gravidade e
prazo. O que **não** muda: cada cobrança mantém o próprio token, o próprio
prazo e a própria escada. O agrupamento é de entrega, não de
responsabilidade.

Como a resposta volta:

  - responder o lote registra retorno em TODAS as cobranças dele e segura
    os lembretes de todas — a pessoa se manifestou, e o sistema não pode
    cobrá-la de novo no dia seguinte por causa de um detalhe de formato;
  - **RESOLVIDO [NTR-xxxxxxxx]** encerra aquela cobrança;
  - **RESOLVIDO** sozinho só encerra quando o lote tem uma cobrança só.
    Com várias, encerrar tudo por uma palavra seria aceitar que "resolvido"
    vale para cinco assuntos que a pessoa talvez nem tenha lido.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime

from .acoes import Acao
from .avaliador import Nivel
from .config import Config, Papel

ICONE = {
    Nivel.VERDE: "🟢",
    Nivel.AMARELO: "🟡",
    Nivel.VERMELHO: "🔴",
    Nivel.CRITICO: "🚨",
}


def marcar_lote(acoes: list[Acao]) -> str:
    """Token do lote: estável para as mesmas ações, no mesmo dia.

    Derivado dos ids das ações para que reenviar o mesmo lote produza o
    mesmo token — e uma resposta antiga continue casando.
    """
    semente = "|".join(sorted(a.id for a in acoes))
    return hashlib.sha1(semente.encode()).hexdigest()[:8]


@dataclass
class Lote:
    papel: Papel
    acoes: list[Acao]
    token: str
    assunto: str
    corpo_md: str
    contatos_ghl: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)


def _ordem(acao: Acao) -> tuple:
    peso = {Nivel.CRITICO: 0, Nivel.VERMELHO: 1, Nivel.AMARELO: 2, Nivel.VERDE: 3}
    return (peso[acao.nivel], acao.prazo)


def montar(
    papel: Papel,
    acoes: list[Acao],
    cfg: Config,
    painel: str,
    agora: datetime | None = None,
) -> Lote:
    agora = agora or datetime.now()
    acoes = sorted(acoes, key=_ordem)
    token = marcar_lote(acoes)
    por_kpi = {k["id"]: k for k in cfg.matriz["kpis"]}

    criticos = sum(1 for a in acoes if a.nivel is Nivel.CRITICO)
    primeiro_nome = papel.pessoas[0].nome.split()[0] if papel.pessoas else papel.nome

    linhas = [
        f"{primeiro_nome}, {_abertura(len(acoes), criticos)}",
        "",
        "Cada ponto abaixo tem prazo próprio. Responda este e-mail: um "
        "retorno, mesmo parcial, vale para todos e segura os lembretes.",
        "",
    ]

    for n, acao in enumerate(acoes, 1):
        kpi = por_kpi[acao.kpi_id]
        linhas += [
            "---",
            "",
            f"## {n}. {ICONE[acao.nivel]} {acao.titulo}",
            "",
            f"_{kpi['pergunta']}_",
            "",
        ]

        numeros = {
            k: v for k, v in acao.contexto.items()
            if k not in (kpi["metrica"], "LISTA", "ROTULO")
            and not isinstance(v, str)
        }
        if numeros:
            linhas += [f"- {k}: {v}" for k, v in list(numeros.items())[:6]]
            linhas.append("")
        if acao.contexto.get("LISTA"):
            linhas += [f"Detalhe: {acao.contexto['LISTA']}", ""]

        linhas.append("**O que preciso de você:**")
        linhas += [f"- {p}" for p in acao.passos]
        linhas += [
            "",
            f"Prazo: **{acao.prazo:%d/%m às %H:%M}** "
            f"({acao.horas_restantes():.0f}h) · para encerrar este ponto, "
            f"escreva **RESOLVIDO [NTR-{acao.id[:8]}]**",
            f"_Base: {kpi['sql']}_",
            "",
        ]

    linhas += [
        "---",
        "",
        f"Detalhe de cada ponto e histórico no painel: {painel}",
        "",
        f"_Apurado em {agora:%d/%m/%Y %H:%M}. Próxima rodada em 2 dias._",
    ]

    plural = "pontos" if len(acoes) > 1 else "ponto"
    icone = "🚨" if criticos else "🔴"
    return Lote(
        papel=papel,
        acoes=acoes,
        token=token,
        assunto=(
            f"{icone} [NTR-L-{token}] {papel.nome}: {len(acoes)} {plural} "
            f"fora da linha"
        ),
        corpo_md="\n".join(linhas),
        contatos_ghl=papel.contatos_ghl,
        emails=papel.emails,
    )


def _abertura(quantos: int, criticos: int) -> str:
    if quantos == 1:
        return "um ponto da sua área saiu da linha."
    if criticos:
        return (
            f"{quantos} pontos da sua área saíram da linha, "
            f"{criticos} deles críticos."
        )
    return f"{quantos} pontos da sua área saíram da linha."


def agrupar(
    acoes: list[Acao], cfg: Config, painel: str, agora: datetime | None = None
) -> list[Lote]:
    """Um lote por dono, do mais carregado para o menos."""
    por_dono: dict[str, list[Acao]] = {}
    for acao in acoes:
        por_dono.setdefault(acao.dono, []).append(acao)

    lotes = [
        montar(cfg.papel(dono), suas, cfg, painel, agora)
        for dono, suas in por_dono.items()
    ]
    return sorted(lotes, key=lambda x: -len(x.acoes))
