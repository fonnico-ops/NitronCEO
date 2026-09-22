"""Renato — a camada que lê o conjunto, não a linha.

A matriz é determinística de propósito: compara número com limiar e abre
ação. Isso é o que a torna confiável e auditável, e é também o seu teto —
ela nunca enxerga que a mesma injetora é a pior em setup *e* em ciclo,
porque são dois KPIs e ela olha um de cada vez.

Este módulo é a parte que olha o conjunto. Ele não decide cobrança: as
ações já vieram prontas do motor, com dono e prazo definidos por regra.
Ele produz três coisas — a leitura cruzada para o CEO, as prioridades do
dia e, quando pedido, o texto de uma cobrança específica.

Nada aqui inventa número. O modelo recebe o dossiê já apurado e é
instruído a só citar o que está nele; o que ele acrescenta é a ligação
entre os números, que é justamente o que nenhuma query faz.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .acoes import Acao, formatar
from .avaliador import Nivel, Sinal
from .config import RAIZ, Config

MODELO = os.getenv("NITRONCEO_MODELO", "claude-opus-5")

# Persona e achados: o prefixo caro que não muda entre rodadas. Fica em
# blocos de sistema com cache — o dossiê do dia, que muda sempre, vai na
# mensagem do usuário para não invalidar o cache.
PERSONA = RAIZ / "config" / "renato.md"
ACHADOS = RAIZ / "docs" / "achados-de-dados.md"

ROTULO = {
    Nivel.VERDE: "verde",
    Nivel.AMARELO: "amarelo",
    Nivel.VERMELHO: "VERMELHO",
    Nivel.CRITICO: "CRÍTICO",
}


class SemCredencial(RuntimeError):
    """Não há chave de API — o Renato não roda, e isso não é um bug."""


@dataclass
class Leitura:
    texto: str
    modelo: str
    gerada_em: datetime = field(default_factory=datetime.now)
    tokens_entrada: int = 0
    tokens_cache: int = 0
    tokens_saida: int = 0

    @property
    def custo_em_cache(self) -> str:
        total = self.tokens_entrada + self.tokens_cache
        if not total:
            return "sem contagem"
        return f"{self.tokens_cache}/{total} tokens de entrada vieram do cache"


# ----------------------------------------------------------------- dossiê


def _linha_sinal(sinal: Sinal, cfg: Config) -> str:
    if sinal.erro:
        return f"- {sinal.titulo} [{sinal.area}]: SEM MEDIÇÃO — {sinal.erro}"

    valor = formatar(sinal.valor, sinal.unidade)
    prefixo = "R$ " if sinal.unidade == "reais" else ""
    sufixo = "%" if sinal.unidade == "percentual" else ""
    sombra = " (SOMBRA — não notifica ninguém)" if sinal.modo == "sombra" else ""
    dono = cfg.papel(sinal.dono).quem

    linha = (
        f"- {sinal.titulo} [{sinal.area}] = {prefixo}{valor}{sufixo} "
        f"-> {ROTULO[sinal.nivel]}, dono {dono}{sombra}"
    )

    # O contexto é onde estão os nomes próprios: qual injetora, qual item,
    # qual cliente. Sem ele a leitura cruzada não tem em que se apoiar.
    detalhe = {
        k: v for k, v in (sinal.linha or {}).items()
        if v not in (None, "") and k.upper() != "LISTA"
    }
    if detalhe:
        pares = ", ".join(f"{k}={v}" for k, v in list(detalhe.items())[:10])
        linha += f"\n    {pares}"
    if (sinal.linha or {}).get("LISTA"):
        linha += f"\n    LISTA: {str(sinal.linha['LISTA'])[:600]}"
    return linha


def montar_dossie(
    sinais: list[Sinal],
    abertas: list[Acao],
    cfg: Config,
    historico: dict[str, int] | None = None,
) -> str:
    """O material de uma rodada, em texto, na ordem em que importa."""
    agora = datetime.now()
    peso = {Nivel.CRITICO: 0, Nivel.VERMELHO: 1, Nivel.AMARELO: 2, Nivel.VERDE: 3}
    ordenados = sorted(sinais, key=lambda s: (peso[s.nivel], s.area))

    partes = [f"# Dossiê da rodada — {agora:%d/%m/%Y %H:%M}", "", "## Sinais apurados"]
    partes += [_linha_sinal(s, cfg) for s in ordenados] or ["- (nenhum)"]

    reincidentes = {k: v for k, v in (historico or {}).items() if v >= 3}
    if reincidentes:
        partes += ["", "## Reincidência (dias seguidos fora do verde)"]
        partes += [f"- {k}: {v} dias" for k, v in sorted(
            reincidentes.items(), key=lambda kv: -kv[1]
        )]

    partes += ["", "## Cobranças em aberto"]
    if abertas:
        for acao in abertas:
            papel = cfg.papel(acao.dono)
            situacao = "VENCIDA" if acao.vencida else f"{acao.horas_restantes():.0f}h"
            partes.append(
                f"- [{acao.id[:6]}] {acao.titulo} — {papel.quem}, {situacao}, "
                f"{acao.escalonamentos} escalonamento(s)"
            )
    else:
        partes.append("- (nenhuma)")

    return "\n".join(partes)


# ------------------------------------------------------------------ Renato


class Renato:
    """A IA de gestão. Lê o dossiê com o conhecimento da empresa carregado."""

    def __init__(
        self,
        cfg: Config,
        cliente: Any | None = None,
        modelo: str = MODELO,
        raiz: Path = RAIZ,
    ) -> None:
        self.cfg = cfg
        self.modelo = modelo
        self.raiz = Path(raiz)
        self._cliente = cliente

    # -------------------------------------------------------------- cliente

    @property
    def cliente(self) -> Any:
        if self._cliente is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover - ambiente sem SDK
                raise SemCredencial(
                    "O pacote `anthropic` não está instalado. "
                    "Instale com: pip install anthropic"
                ) from exc
            if not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")):
                raise SemCredencial(
                    "Sem ANTHROPIC_API_KEY no ambiente. O Renato precisa dela "
                    "para analisar; o resto do NitronCEO roda sem."
                )
            self._cliente = anthropic.Anthropic()
        return self._cliente

    # --------------------------------------------------------- conhecimento

    def conhecimento(self) -> list[dict[str, Any]]:
        """Blocos de sistema: a persona e os achados, marcados para cache.

        São ~40 mil tokens que não mudam entre rodadas. Sem o marcador de
        cache, cada rodada do dia pagaria o prefixo inteiro de novo.
        """
        blocos: list[dict[str, Any]] = []
        for arquivo in (PERSONA, ACHADOS):
            caminho = self.raiz / arquivo.relative_to(RAIZ)
            if not caminho.exists():
                continue
            blocos.append({"type": "text", "text": caminho.read_text(encoding="utf-8")})

        if not blocos:
            raise SemCredencial(
                f"Não achei {PERSONA.name}. Sem a persona, o Renato é um "
                "modelo genérico opinando sobre uma empresa que não conhece."
            )

        blocos.append({"type": "text", "text": self._quadro_de_papeis()})
        # O marcador vai no último bloco: tudo antes dele entra no cache.
        blocos[-1]["cache_control"] = {"type": "ephemeral"}
        return blocos

    def _quadro_de_papeis(self) -> str:
        linhas = ["# Papéis vigentes (gerado de pessoas.yaml)", ""]
        for chave, papel in self.cfg.pessoas["papeis"].items():
            sobe = papel.get("escalonar_para") or "—"
            quem = ", ".join(
                f"{p['nome']} <{p['email']}>" for p in papel.get("pessoas", [])
            )
            linhas.append(f"- `{chave}` ({papel['nome']}): {quem} | escala para: {sobe}")

        ativos = [k for k in self.cfg.matriz["kpis"] if k["modo"] == "ativo"]
        sombra = [k["id"] for k in self.cfg.matriz["kpis"] if k["modo"] != "ativo"]
        linhas += [
            "",
            f"KPIs: {len(ativos)} ativos, {len(sombra)} em sombra "
            f"({', '.join(sombra) or 'nenhum'}).",
        ]
        return "\n".join(linhas)

    # ---------------------------------------------------------------- pedir

    def _perguntar(self, instrucao: str, max_tokens: int = 8000) -> Leitura:
        import anthropic

        try:
            with self.cliente.messages.stream(
                model=self.modelo,
                max_tokens=max_tokens,
                thinking={"type": "adaptive"},
                output_config={"effort": "high"},
                system=self.conhecimento(),
                messages=[{"role": "user", "content": instrucao}],
            ) as fluxo:
                resposta = fluxo.get_final_message()
        except anthropic.BadRequestError as exc:
            raise RuntimeError(f"Pedido recusado pela API: {exc}") from exc
        except anthropic.AuthenticationError as exc:
            raise SemCredencial(f"Credencial inválida: {exc}") from exc
        except anthropic.RateLimitError as exc:
            raise RuntimeError(f"Limite de taxa atingido: {exc}") from exc
        except anthropic.APIStatusError as exc:
            raise RuntimeError(f"API respondeu {exc.status_code}: {exc}") from exc
        except anthropic.APIConnectionError as exc:
            raise RuntimeError(f"Não consegui falar com a API: {exc}") from exc

        texto = "\n".join(
            b.text for b in resposta.content if getattr(b, "type", "") == "text"
        ).strip()
        uso = resposta.usage
        return Leitura(
            texto=texto,
            modelo=self.modelo,
            tokens_entrada=getattr(uso, "input_tokens", 0) or 0,
            tokens_cache=getattr(uso, "cache_read_input_tokens", 0) or 0,
            tokens_saida=getattr(uso, "output_tokens", 0) or 0,
        )

    # -------------------------------------------------------------- leitura

    def leitura(
        self,
        sinais: list[Sinal],
        abertas: list[Acao],
        historico: dict[str, int] | None = None,
    ) -> Leitura:
        dossie = montar_dossie(sinais, abertas, self.cfg, historico)
        return self._perguntar(
            f"{dossie}\n\n{_PEDIDO_LEITURA}"
        )

    # ------------------------------------------------------------- cobrança

    def redigir_cobranca(
        self, acao: Acao, sinal: Sinal, kpi: dict[str, Any], rodada: int = 1
    ) -> Leitura:
        papel = self.cfg.papel(acao.dono)
        contexto = "\n".join(
            f"- {k}: {v}" for k, v in list((sinal.linha or {}).items())[:12]
        )
        passos = "\n".join(f"- {p}" for p in acao.passos)
        pedido = (
            f"# Cobrança a redigir (rodada {rodada} de 3)\n\n"
            f"KPI: {kpi['titulo']}\n"
            f"Pergunta que o KPI responde: {kpi['pergunta']}\n"
            f"Nível: {ROTULO[sinal.nivel]}\n"
            f"Destinatário: {papel.quem} ({papel.nome})\n"
            f"Prazo de resposta: {acao.prazo:%d/%m às %H:%M}\n"
            f"Query de origem: {kpi['sql']}\n\n"
            f"Números apurados:\n{contexto or '- (sem detalhe)'}\n\n"
            f"Passos já definidos pela matriz:\n{passos}\n\n"
            f"{_PEDIDO_COBRANCA}"
        )
        return self._perguntar(pedido, max_tokens=2000)

    # ------------------------------------------------- protocolo do motor

    def texto_cobranca(
        self, acao: Acao, sinal: Sinal, kpi: dict[str, Any]
    ) -> str | None:
        """Adaptador para `motor.Redator`.

        Devolve só o corpo; prazo, link do painel e procedência do número
        são acrescentados pelo motor, porque são fato do sistema e não
        podem depender de o modelo ter lembrado deles.
        """
        return self.redigir_cobranca(acao, sinal, kpi).texto or None


_PEDIDO_LEITURA = """---

Escreva a leitura da rodada para o CEO, em markdown, nesta ordem e sem
outras seções:

## O que mudou
Duas a quatro frases. Se nada saiu da linha, diga isso em duas frases e
encerre a seção — não invente movimento.

## Leitura cruzada
O que um sinal diz sobre o outro. Esta é a seção que justifica a sua
existência: a matriz já comparou cada número com o limiar dela sozinha.
Só afirme uma ligação se os dois números estiverem no dossiê acima.
Se não houver ligação defensável hoje, escreva "nenhuma ligação nova" e
siga. Nunca use KPI em sombra como base de cobrança; citar é permitido
desde que você diga que está em sombra.

## As três de hoje
No máximo três itens. Cada um: o que fazer, quem, e por que este e não
outro. Se houver menos de três coisas que merecem o dia do CEO, liste
menos.

## Risco que ninguém está olhando
Um parágrafo, ou "nenhum" se for o caso. Vale apontar lacuna de dado
quando ela estiver escondendo risco.

Regras: só cite números presentes no dossiê; não arredonde para cima; não
estime o que não foi medido. Se um sinal está sem medição, isso é um fato
sobre a operação e pode entrar na leitura."""


_PEDIDO_COBRANCA = """---

Escreva a mensagem de cobrança para esta pessoa, em markdown, no seu
tom: número primeiro, pedido claro, prazo explícito, sem ameaça e sem
ironia. No máximo 200 palavras.

Não inclua assunto, saudação de rodapé nem link do painel — o motor
acrescenta. Não repita os passos literalmente se conseguir dizê-los
melhor, mas não invente passo novo nem número que não esteja acima.
Se for rodada 2 ou 3, reconheça que já houve cobrança anterior sem
dramatizar."""
