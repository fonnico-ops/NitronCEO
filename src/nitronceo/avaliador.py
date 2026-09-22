"""Transforma número em julgamento.

O julgamento é o que dá direito à cobrança. Sem ele o número é informação,
e informação não obriga ninguém a nada.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class Nivel(str, Enum):
    VERDE = "verde"
    AMARELO = "amarelo"
    VERMELHO = "vermelho"
    CRITICO = "critico"

    @property
    def cobra(self) -> bool:
        return self in (Nivel.VERMELHO, Nivel.CRITICO)

    @property
    def canais_de(self) -> str:
        """Nível cujo mapa de notificação se aplica (crítico herda vermelho)."""
        return "vermelho" if self is Nivel.CRITICO else self.value


@dataclass
class Sinal:
    kpi_id: str
    titulo: str
    area: str
    nivel: Nivel
    valor: float | None
    unidade: str
    dono: str
    modo: str
    medido_em: datetime
    linha: dict[str, Any]
    erro: str | None = None

    @property
    def notificavel(self) -> bool:
        return self.modo == "ativo" and self.erro is None


def classificar(avaliacao: dict[str, Any], valor: float) -> Nivel:
    verde, amarelo, vermelho = (
        float(avaliacao["verde"]),
        float(avaliacao["amarelo"]),
        float(avaliacao["vermelho"]),
    )

    if avaliacao["tipo"] == "limite_inferior":
        # Menor é pior: 100 / 92 / 85 -> abaixo de 85 é crítico.
        if valor >= verde:
            return Nivel.VERDE
        if valor >= amarelo:
            return Nivel.AMARELO
        if valor >= vermelho:
            return Nivel.VERMELHO
        return Nivel.CRITICO

    # limite_superior — maior é pior: 1.5 / 3 / 5 -> acima de 5 é crítico.
    if valor <= verde:
        return Nivel.VERDE
    if valor <= amarelo:
        return Nivel.AMARELO
    if valor <= vermelho:
        return Nivel.VERMELHO
    return Nivel.CRITICO


def avaliar(kpi: dict[str, Any], linhas: list[dict[str, Any]]) -> Sinal:
    agora = datetime.now()
    base = dict(
        kpi_id=kpi["id"],
        titulo=kpi["titulo"],
        area=kpi["area"],
        unidade=kpi.get("unidade", ""),
        dono=kpi["dono"],
        modo=kpi["modo"],
        medido_em=agora,
    )

    if not linhas:
        return Sinal(
            **base, nivel=Nivel.VERDE, valor=None, linha={},
            erro="consulta não retornou linha",
        )

    linha = linhas[0]
    metrica = kpi["metrica"]
    if metrica not in linha:
        return Sinal(
            **base, nivel=Nivel.VERDE, valor=None, linha=linha,
            erro=f"coluna '{metrica}' ausente no resultado",
        )

    bruto = linha[metrica]
    if bruto is None:
        # Métrica nula é ausência de medição, não sinal verde. Dizer "está
        # tudo bem" porque a query voltou vazia é como o alarme que não toca
        # porque a bateria acabou.
        return Sinal(
            **base, nivel=Nivel.VERDE, valor=None, linha=linha,
            erro=f"métrica '{metrica}' voltou nula",
        )

    valor = float(bruto)
    return Sinal(**base, nivel=classificar(kpi["avaliacao"], valor),
                 valor=valor, linha=linha)
