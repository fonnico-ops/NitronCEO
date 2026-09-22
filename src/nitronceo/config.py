"""Carga e validação dos arquivos de configuração."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parents[2]


@dataclass
class Papel:
    chave: str
    nome: str
    teams_id: str
    email: str
    escalonar_para: str | None = None


@dataclass
class Config:
    matriz: dict[str, Any]
    pessoas: dict[str, Any]
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def papeis(self) -> dict[str, Papel]:
        return {
            chave: Papel(chave=chave, **dados)
            for chave, dados in self.pessoas["papeis"].items()
        }

    def papel(self, chave: str) -> Papel:
        try:
            return self.papeis[chave]
        except KeyError:
            raise KeyError(
                f"Papel '{chave}' citado na matriz não existe em pessoas.yaml"
            ) from None

    def canal_teams(self, chave: str | None) -> dict[str, str] | None:
        if not chave:
            return None
        return self.pessoas.get("canais_teams", {}).get(chave)


def _ler_yaml(caminho: Path) -> dict[str, Any]:
    with caminho.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def carregar(raiz: Path | None = None) -> Config:
    base = Path(raiz) if raiz else RAIZ
    matriz = _ler_yaml(base / "config" / "matriz.yaml")
    pessoas = _ler_yaml(base / "config" / "pessoas.yaml")

    cfg = Config(matriz=matriz, pessoas=pessoas, params=_params_padrao(matriz))
    _validar(cfg)
    return cfg


def _params_padrao(matriz: dict[str, Any]) -> dict[str, Any]:
    """Parâmetros substituídos nos arquivos .sql como {{NOME}}.

    Ficam aqui, e não espalhados nas queries, porque quase todo desacordo de
    número entre duas áreas é desacordo de parâmetro — recorte de empresa,
    janela, piso — e não de SQL.
    """
    codemp = ",".join(str(c) for c in matriz["recorte_padrao"]["codemp"])
    return {
        "CODEMP": codemp,
        # Fonte de saldo. Ver sql/ruptura_estoque.sql: CODEMP 1 está corrompida.
        "CODEMP_SALDO": "2",
        # Meta de faturamento do mês. Trocar pela meta real do orçamento.
        "META_MENSAL": os.getenv("NITRONCEO_META_MENSAL", "8000000"),
        "JANELA_DIAS": "30",
        "JANELA_VENCIDO_DIAS": "365",
        "CARTEIRA_DIAS": "45",
        "PISO_META_PCT": "80",
        "PISO_RELEVANCIA": "5000",
        "MIN_PARADA_ALERTA": "60",
        "SETUP_TETO_MIN": "240",
        # TOP 2203 = "Devolução Simbólica Consignado": acerto de consignação,
        # não retorno de cliente. Incluí-la infla a devolução em ~3x.
        "TOPS_EXCLUIR_DEVOLUCAO": "2203",
    }


def _validar(cfg: Config) -> None:
    """Falha cedo. Matriz com dono inexistente só aparece na hora de cobrar."""
    vistos: set[str] = set()
    for kpi in cfg.matriz["kpis"]:
        kid = kpi["id"]
        if kid in vistos:
            raise ValueError(f"KPI duplicado na matriz: {kid}")
        vistos.add(kid)

        cfg.papel(kpi["dono"])

        if kpi["modo"] not in {"ativo", "sombra"}:
            raise ValueError(f"{kid}: modo deve ser 'ativo' ou 'sombra'")

        sql = RAIZ / kpi["sql"]
        if not sql.exists():
            raise FileNotFoundError(f"{kid}: arquivo {kpi['sql']} não existe")

        aval = kpi["avaliacao"]
        if aval["tipo"] not in {"limite_inferior", "limite_superior"}:
            raise ValueError(f"{kid}: tipo de avaliação desconhecido")
