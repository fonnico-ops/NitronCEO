"""A escada de cobrança.

Esta é a parte que as ferramentas de BI não têm e por isso não substituem um
CEO: o que acontece quando ninguém responde.

    rodada 0  prazo vence           -> relembra o dono, no mesmo canal
    rodada 1  prazo + 50%           -> escala para o gestor do dono
    rodada 2  prazo dobrado         -> escala para o CEO
    rodada 3+ silêncio              -> para de cobrar e vira pauta de reunião

Parar na rodada 3 é deliberado. Cobrança que se repete para sempre deixa de
ser cobrança e vira ruído — e o problema passa a ser da pessoa que não
responde, não do indicador. Isso é decisão de gente, não de software.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .acoes import Acao, Estado
from .config import Config

MAX_RODADAS = 3


@dataclass
class Cobranca:
    acao: Acao
    rodada: int
    destinatario: str   # chave do papel
    motivo: str
    urgente: bool

    @property
    def escalada(self) -> bool:
        return self.rodada >= 1


def _vencimento_da_rodada(acao: Acao, rodada: int) -> datetime:
    janela = acao.prazo - acao.criada_em
    if rodada == 0:
        return acao.prazo
    if rodada == 1:
        return acao.criada_em + janela * 1.5
    return acao.criada_em + janela * 2


def proxima_cobranca(
    acao: Acao, cfg: Config, agora: datetime | None = None
) -> Cobranca | None:
    """Decide se esta ação merece cobrança agora, e de quem."""
    agora = agora or datetime.now()

    if acao.estado in (Estado.RESPONDIDA, Estado.RESOLVIDA):
        return None

    rodada = acao.escalonamentos
    if rodada >= MAX_RODADAS:
        return None

    if agora < _vencimento_da_rodada(acao, rodada):
        return None

    dono = cfg.papel(acao.dono)

    if rodada == 0:
        return Cobranca(
            acao=acao,
            rodada=0,
            destinatario=dono.chave,
            motivo=(
                f"Prazo de resposta venceu há "
                f"{_horas(agora - acao.prazo)}. Ainda sem retorno."
            ),
            urgente=False,
        )

    gestor = dono.escalonar_para
    if rodada == 1 and gestor:
        return Cobranca(
            acao=acao,
            rodada=1,
            destinatario=gestor,
            motivo=(
                f"{dono.nome} não respondeu em "
                f"{_horas(agora - acao.criada_em)}. Escalando."
            ),
            urgente=True,
        )

    # rodada 2, ou rodada 1 sem gestor definido: sobe para o CEO.
    ceo = next(
        (p.chave for p in cfg.papeis.values() if p.escalonar_para is None), None
    )
    if not ceo or ceo == acao.dono:
        return None

    return Cobranca(
        acao=acao,
        rodada=rodada,
        destinatario=ceo,
        motivo=(
            f"Sem resposta de {dono.nome} nem do gestor em "
            f"{_horas(agora - acao.criada_em)}. Isto virou pauta sua."
        ),
        urgente=True,
    )


def aplicar(acao: Acao, cobranca: Cobranca) -> Estado:
    """Novo estado da ação depois de disparada a cobrança."""
    acao.escalonamentos = cobranca.rodada + 1
    return Estado.ESCALADA if cobranca.escalada else Estado.VENCIDA


def _horas(delta: timedelta) -> str:
    horas = int(delta.total_seconds() // 3600)
    if horas < 1:
        return f"{int(delta.total_seconds() // 60)} min"
    if horas < 48:
        return f"{horas}h"
    return f"{horas // 24} dias"
