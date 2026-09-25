"""Converte sinal em ação com dono, prazo e passos.

Uma ação sem dono é um lembrete. Uma ação sem prazo é uma opinião.
Nenhuma das duas se cobra, então ambas são erro de construção aqui.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from .avaliador import Nivel, Sinal


class Estado(str, Enum):
    ABERTA = "aberta"
    RESPONDIDA = "respondida"
    ESCALADA = "escalada"
    VENCIDA = "vencida"
    RESOLVIDA = "resolvida"


@dataclass
class Acao:
    id: str
    kpi_id: str
    titulo: str
    passos: list[str]
    dono: str
    nivel: Nivel
    valor: float | None
    unidade: str
    criada_em: datetime
    prazo: datetime
    estado: Estado = Estado.ABERTA
    escalonamentos: int = 0
    respondida_em: datetime | None = None
    resposta: str | None = None
    contexto: dict[str, Any] = field(default_factory=dict)

    @property
    def vencida(self) -> bool:
        return self.estado == Estado.ABERTA and datetime.now() > self.prazo

    def horas_restantes(self) -> float:
        return (self.prazo - datetime.now()).total_seconds() / 3600


def formatar(valor: float | None, unidade: str) -> str:
    if valor is None:
        return "—"
    if unidade == "reais":
        return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if unidade == "percentual":
        return f"{valor:.1f}".replace(".", ",")
    return f"{valor:,.0f}".replace(",", ".")


def identificador(kpi_id: str, quando: datetime) -> str:
    """Uma ação por KPI por dia.

    Reexecutar o motor no mesmo dia atualiza a ação existente em vez de
    empilhar cobrança nova — quem recebe 4 mensagens do mesmo assunto para
    de ler todas.
    """
    semente = f"{kpi_id}:{quando:%Y-%m-%d}"
    return hashlib.sha1(semente.encode()).hexdigest()[:12]


def criar(sinal: Sinal, kpi: dict[str, Any]) -> Acao | None:
    if not sinal.nivel.cobra or sinal.erro:
        return None

    molde = kpi["acao"]
    rotulo = sinal.linha.get("ROTULO") or sinal.linha.get("LISTA") or ""
    titulo = molde["titulo"].format(
        valor=formatar(sinal.valor, sinal.unidade),
        rotulo=rotulo,
    )

    horas = float(molde["sla_resposta_horas"])
    if sinal.nivel is Nivel.CRITICO:
        # Crítico não ganha o mesmo prazo do vermelho. Metade, piso de 1h.
        horas = max(horas / 2, 1.0)

    agora = datetime.now()
    return Acao(
        id=identificador(kpi["id"], agora),
        kpi_id=kpi["id"],
        titulo=titulo,
        passos=list(molde["passos"]),
        dono=kpi["dono"],
        nivel=sinal.nivel,
        valor=sinal.valor,
        unidade=sinal.unidade,
        criada_em=agora,
        prazo=agora + timedelta(hours=horas),
        contexto={k: v for k, v in sinal.linha.items() if v is not None},
    )
