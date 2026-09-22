"""Persistência. SQLite por padrão — Postgres/Supabase quando o time crescer.

O que é gravado aqui é o que permite cobrar amanhã o que foi pedido hoje.
Sem isso o motor vira um gerador de e-mail sem memória, que é exatamente o
que já existe e não funciona.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .acoes import Acao, Estado
from .avaliador import Nivel, Sinal

ESQUEMA = """
CREATE TABLE IF NOT EXISTS sinais (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kpi_id      TEXT NOT NULL,
    nivel       TEXT NOT NULL,
    valor       REAL,
    unidade     TEXT,
    modo        TEXT NOT NULL,
    erro        TEXT,
    linha       TEXT NOT NULL,
    medido_em   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_sinais_kpi ON sinais(kpi_id, medido_em);

CREATE TABLE IF NOT EXISTS acoes (
    id              TEXT PRIMARY KEY,
    kpi_id          TEXT NOT NULL,
    titulo          TEXT NOT NULL,
    passos          TEXT NOT NULL,
    dono            TEXT NOT NULL,
    nivel           TEXT NOT NULL,
    valor           REAL,
    unidade         TEXT,
    estado          TEXT NOT NULL,
    escalonamentos  INTEGER NOT NULL DEFAULT 0,
    criada_em       TEXT NOT NULL,
    prazo           TEXT NOT NULL,
    respondida_em   TEXT,
    resposta        TEXT,
    contexto        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_acoes_estado ON acoes(estado, prazo);

CREATE TABLE IF NOT EXISTS cobrancas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    acao_id     TEXT NOT NULL REFERENCES acoes(id),
    rodada      INTEGER NOT NULL,
    destinatario TEXT NOT NULL,
    canal       TEXT NOT NULL,
    enviada_em  TEXT NOT NULL,
    motivo      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_cobrancas_acao ON cobrancas(acao_id);
"""


class Repositorio:
    def __init__(self, caminho: Path | str = "dados/nitronceo.db") -> None:
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.caminho)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(ESQUEMA)
        self.con.commit()

    def fechar(self) -> None:
        self.con.close()

    # ---------------------------------------------------------------- sinais

    def gravar_sinal(self, sinal: Sinal) -> None:
        self.con.execute(
            "INSERT INTO sinais (kpi_id, nivel, valor, unidade, modo, erro,"
            " linha, medido_em) VALUES (?,?,?,?,?,?,?,?)",
            (
                sinal.kpi_id, sinal.nivel.value, sinal.valor, sinal.unidade,
                sinal.modo, sinal.erro, json.dumps(sinal.linha, default=str),
                sinal.medido_em.isoformat(),
            ),
        )
        self.con.commit()

    def dias_consecutivos_ruins(self, kpi_id: str, limite: int = 10) -> int:
        """Quantos dias seguidos este KPI está cobrando.

        Reincidência é informação de gestão: o terceiro dia vermelho seguido
        não é o mesmo problema do primeiro, e não deve ser tratado como tal.
        """
        cur = self.con.execute(
            "SELECT DISTINCT date(medido_em) AS d,"
            "  MAX(CASE WHEN nivel IN ('vermelho','critico') THEN 1 ELSE 0 END) AS ruim"
            " FROM sinais WHERE kpi_id = ? GROUP BY date(medido_em)"
            " ORDER BY d DESC LIMIT ?",
            (kpi_id, limite),
        )
        seguidos = 0
        for linha in cur.fetchall():
            if linha["ruim"]:
                seguidos += 1
            else:
                break
        return seguidos

    # ----------------------------------------------------------------- ações

    def salvar_acao(self, acao: Acao) -> bool:
        """Grava a ação. Devolve True se é nova, False se já existia hoje."""
        existente = self.buscar_acao(acao.id)
        if existente:
            self.con.execute(
                "UPDATE acoes SET valor = ?, nivel = ?, titulo = ?, contexto = ?"
                " WHERE id = ?",
                (
                    acao.valor, acao.nivel.value, acao.titulo,
                    json.dumps(acao.contexto, default=str), acao.id,
                ),
            )
            self.con.commit()
            return False

        self.con.execute(
            "INSERT INTO acoes (id, kpi_id, titulo, passos, dono, nivel, valor,"
            " unidade, estado, escalonamentos, criada_em, prazo, contexto)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                acao.id, acao.kpi_id, acao.titulo, json.dumps(acao.passos),
                acao.dono, acao.nivel.value, acao.valor, acao.unidade,
                acao.estado.value, acao.escalonamentos,
                acao.criada_em.isoformat(), acao.prazo.isoformat(),
                json.dumps(acao.contexto, default=str),
            ),
        )
        self.con.commit()
        return True

    def buscar_acao(self, acao_id: str) -> Acao | None:
        linha = self.con.execute(
            "SELECT * FROM acoes WHERE id = ?", (acao_id,)
        ).fetchone()
        return _para_acao(linha) if linha else None

    def acoes_em_aberto(self) -> list[Acao]:
        cur = self.con.execute(
            "SELECT * FROM acoes WHERE estado IN (?,?) ORDER BY prazo",
            (Estado.ABERTA.value, Estado.ESCALADA.value),
        )
        return [_para_acao(l) for l in cur.fetchall()]

    def atualizar_estado(
        self, acao_id: str, estado: Estado, escalonamentos: int | None = None
    ) -> None:
        if escalonamentos is None:
            self.con.execute(
                "UPDATE acoes SET estado = ? WHERE id = ?", (estado.value, acao_id)
            )
        else:
            self.con.execute(
                "UPDATE acoes SET estado = ?, escalonamentos = ? WHERE id = ?",
                (estado.value, escalonamentos, acao_id),
            )
        self.con.commit()

    def registrar_resposta(self, acao_id: str, texto: str) -> bool:
        if not self.buscar_acao(acao_id):
            return False
        self.con.execute(
            "UPDATE acoes SET estado = ?, resposta = ?, respondida_em = ?"
            " WHERE id = ?",
            (Estado.RESPONDIDA.value, texto, datetime.now().isoformat(), acao_id),
        )
        self.con.commit()
        return True

    # ------------------------------------------------------------- cobranças

    def registrar_cobranca(
        self, acao_id: str, rodada: int, destinatario: str, canal: str, motivo: str
    ) -> None:
        self.con.execute(
            "INSERT INTO cobrancas (acao_id, rodada, destinatario, canal,"
            " enviada_em, motivo) VALUES (?,?,?,?,?,?)",
            (acao_id, rodada, destinatario, canal,
             datetime.now().isoformat(), motivo),
        )
        self.con.commit()

    def cobrancas_de(self, acao_id: str) -> int:
        linha = self.con.execute(
            "SELECT COUNT(*) AS n FROM cobrancas WHERE acao_id = ?", (acao_id,)
        ).fetchone()
        return int(linha["n"])


def _para_acao(linha: sqlite3.Row) -> Acao:
    return Acao(
        id=linha["id"],
        kpi_id=linha["kpi_id"],
        titulo=linha["titulo"],
        passos=json.loads(linha["passos"]),
        dono=linha["dono"],
        nivel=Nivel(linha["nivel"]),
        valor=linha["valor"],
        unidade=linha["unidade"] or "",
        criada_em=datetime.fromisoformat(linha["criada_em"]),
        prazo=datetime.fromisoformat(linha["prazo"]),
        estado=Estado(linha["estado"]),
        escalonamentos=linha["escalonamentos"],
        respondida_em=(
            datetime.fromisoformat(linha["respondida_em"])
            if linha["respondida_em"] else None
        ),
        resposta=linha["resposta"],
        contexto=json.loads(linha["contexto"]),
    )
