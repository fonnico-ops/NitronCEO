"""Carga e validação dos arquivos de configuração."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parents[2]


@dataclass
class Pessoa:
    nome: str
    email: str


@dataclass
class Papel:
    """Um dono de cobrança. Pode ser mais de uma pessoa.

    Quando são duas, as duas recebem — o papel é o dono, não o indivíduo.
    Dividir a cobrança entre elas seria transformá-la em cobrança de ninguém.
    """

    chave: str
    nome: str
    pessoas: list[Pessoa]
    escalonar_para: str | None = None

    @property
    def emails(self) -> list[str]:
        return [p.email for p in self.pessoas]

    @property
    def quem(self) -> str:
        """Os nomes, para aparecer na mensagem e no painel."""
        return " e ".join(p.nome for p in self.pessoas)


@dataclass
class Config:
    matriz: dict[str, Any]
    pessoas: dict[str, Any]
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def papeis(self) -> dict[str, Papel]:
        return {
            chave: Papel(
                chave=chave,
                nome=dados["nome"],
                pessoas=[Pessoa(**p) for p in dados["pessoas"]],
                escalonar_para=dados.get("escalonar_para"),
            )
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
        # Fonte de saldo: CODEMP 1 está corrompida (3e19 unidades).
        "CODEMP_SALDO": "2,4,14",
        # A meta é DIÁRIA e é a mesma para faturar e para carregar: a
        # fábrica escoa na mesma capacidade, e separar as duas é o que
        # produz agenda com dia de R$ 1,8 mi ao lado de dia de R$ 37 mil.
        "META_DIA": os.getenv("NITRONCEO_META_DIA", "500000"),
        # Recorte da meta: só as quatro empresas que produzem e expedem.
        # Diferente do recorte do grupo (que inclui 3 NTR Log, 17 Hyak Group
        # e 20 ACIUD) de propósito — ver sql/faturamento_ritmo.sql.
        "CODEMP_META": "1,2,4,14",
        "AGENDA_DIAS": "15",
        "JANELA_DIAS": "30",
        "JANELA_VENCIDO_DIAS": "365",
        "CARTEIRA_DIAS": "45",
        "PISO_META_PCT": "80",
        "PISO_RELEVANCIA": "5000",
        "MIN_PARADA_ALERTA": "60",
        # Parada de setup acima disto não é troca de molde, é apontamento
        # que ficou aberto atravessando turno — vira contagem à parte.
        "SETUP_TETO_MIN": "1440",
        "SETUP_PADRAO_MIN": "40",
        # Códigos de TPRMTP (cadastro de motivos de parada).
        "MOTIVO_SETUP": "10",
        "MOTIVO_MOLDE": "6",
        "MOTIVO_REFEICAO": "13",
        "MOTIVO_LIBERADO": "30",
        "REFEICAO_TETO_MIN": "90",
        # TOP 2203 = "Devolução Simbólica Consignado": acerto de consignação,
        # não retorno de cliente. Incluí-la infla a devolução em ~3x.
        "TOPS_EXCLUIR_DEVOLUCAO": "2203",
        # CODLOCAL "Estoque para Transferência": conta de contrapartida,
        # negativa por construção. Somá-la destrói o saldo — ver
        # sql/ruptura_estoque.sql.
        "LOCAL_TRANSFERENCIA": "1080000",
        # Fila de liberação (TSILIB). Eventos de crédito vão para o
        # financeiro; todo o resto é decisão do comercial.
        "LIBERACAO_DIAS": "180",
        "EVENTOS_CREDITO": "3,15,8",
        "COBERTURA_ALERTA_DIAS": "15",
        "DEMANDA_PISO_MES": "5000",
        "DEVEDOR_PISO": "50000",
        "GASTO_PISO_MES": "50000",
        # Naturezas de COMPRA (grupo 3 = custo de material e serviço de
        # produção, mais o adiantamento a fornecedor). O resto da despesa —
        # financiamento, dividendo, folha, imposto, aluguel — não é decisão
        # de quem compra, e cobrar Compras por ela seria cobrança sem alçada.
        "NAT_INJECAO_TERCEIRIZADA": "3010105",
        "REATIVAR_PISO": "5000",
        "NAT_COMPRAS": ("3010101,3010103,3010105,3010106,3010107,3010108,"
                        "3010109,3010110,8010700"),
        "GASTO_ESTOURO_PCT": "130",
        "QUEDA_PISO_BASE": "20000",
        "QUEDA_PCT": "70",
        # NTR Log: CODEMP 3 / CODPARC 65253; natureza do frete na Nitron.
        "NAT_FRETE_NTR": "9010107",
        "CODPARC_NTRLOG": "65253",
        "CODEMP_NTRLOG": "3",
        # Teak Brazil: São Paulo e Rondônia, fora do recorte Nitron.
        "CODEMP_TEAK": "8,21",
    }


def _validar(cfg: Config) -> None:
    """Falha cedo. Matriz com dono inexistente só aparece na hora de cobrar."""
    for chave, papel in cfg.papeis.items():
        if not papel.pessoas:
            raise ValueError(f"Papel '{chave}' não tem ninguém para cobrar")
        alvo = papel.escalonar_para
        if alvo and alvo not in cfg.papeis:
            raise ValueError(f"Papel '{chave}' escala para '{alvo}', que não existe")

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
