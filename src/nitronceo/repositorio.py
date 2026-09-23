"""Persistência. SQLite por padrão — Postgres/Supabase quando o time crescer.

O que é gravado aqui é o que permite cobrar amanhã o que foi pedido hoje.
Sem isso o motor vira um gerador de e-mail sem memória, que é exatamente o
que já existe e não funciona.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
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

-- Toda resposta que chega por e-mail, inclusive as que não encerram nada.
-- `msg_id` é o Internet Message-Id do e-mail, que é único e estável: é ele
-- que impede a mesma resposta de ser processada duas vezes a cada leitura
-- da caixa.
CREATE TABLE IF NOT EXISTS respostas_email (
    msg_id      TEXT PRIMARY KEY,
    acao_id     TEXT NOT NULL REFERENCES acoes(id),
    de          TEXT NOT NULL,
    texto       TEXT NOT NULL,
    encerra     INTEGER NOT NULL DEFAULT 0,
    recebida_em TEXT NOT NULL,
    lida_em     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_respostas_acao ON respostas_email(acao_id);

-- Quando o último disparo de cobrança saiu. É o que sustenta a cadência
-- de dois em dois dias sem depender do cron acertar o dia: o cron roda
-- todo dia às 17h e pergunta aqui se hoje é dia.
CREATE TABLE IF NOT EXISTS disparos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    quando      TEXT NOT NULL,
    lotes       INTEGER NOT NULL,
    acoes       INTEGER NOT NULL
);

-- Um lote entregue: a mensagem única que um dono recebeu com várias
-- cobranças dentro. Guardado para que a resposta ao lote possa ser
-- distribuída entre todas as ações que ele carregava.
CREATE TABLE IF NOT EXISTS lotes (
    token       TEXT NOT NULL,
    acao_id     TEXT NOT NULL REFERENCES acoes(id),
    dono        TEXT NOT NULL,
    enviado_em  TEXT NOT NULL,
    PRIMARY KEY (token, acao_id)
);
CREATE INDEX IF NOT EXISTS ix_lotes_token ON lotes(token);
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

    def registrar_resposta(
        self, acao_id: str, texto: str, quando: datetime | None = None
    ) -> bool:
        if not self.buscar_acao(acao_id):
            return False
        self.con.execute(
            "UPDATE acoes SET estado = ?, resposta = ?, respondida_em = ?"
            " WHERE id = ?",
            (Estado.RESPONDIDA.value, texto,
             (quando or datetime.now()).isoformat(), acao_id),
        )
        self.con.commit()
        return True

    # ------------------------------------------------------ cadência e lotes

    def ultimo_disparo(self) -> datetime | None:
        linha = self.con.execute(
            "SELECT quando FROM disparos ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return datetime.fromisoformat(linha["quando"]) if linha else None

    def deve_disparar(self, intervalo_dias: int, agora: datetime | None = None) -> bool:
        """Hoje é dia de cobrar?

        A cadência mora aqui, e não no cron, de propósito: `0 17 */2 * *`
        escorrega na virada do mês e ninguém percebe. Assim o cron roda
        todo dia às 17h e pergunta; a resposta é do banco, que sabe quando
        o último disparo saiu de verdade.
        """
        ultimo = self.ultimo_disparo()
        if ultimo is None:
            return True
        agora = agora or datetime.now()
        return (agora.date() - ultimo.date()).days >= intervalo_dias

    def registrar_disparo(self, lotes: int, acoes: int) -> None:
        self.con.execute(
            "INSERT INTO disparos (quando, lotes, acoes) VALUES (?,?,?)",
            (datetime.now().isoformat(), lotes, acoes),
        )
        self.con.commit()

    def registrar_lote(self, token: str, acao_ids: list[str], dono: str) -> None:
        agora = datetime.now().isoformat()
        self.con.executemany(
            "INSERT OR REPLACE INTO lotes (token, acao_id, dono, enviado_em)"
            " VALUES (?,?,?,?)",
            [(token, aid, dono, agora) for aid in acao_ids],
        )
        self.con.commit()

    def acoes_do_lote(self, token: str) -> list[str]:
        return [
            linha["acao_id"] for linha in self.con.execute(
                "SELECT acao_id FROM lotes WHERE token = ?", (token,)
            )
        ]

    # ------------------------------------------------- respostas por e-mail

    def resposta_ja_lida(self, msg_id: str) -> bool:
        """O mesmo e-mail aparece em toda leitura da caixa; processa uma vez.

        Uma resposta a lote vira uma linha por ação, com chave
        `<msg_id>#<acao_id>` — então a pergunta "já li este e-mail?" é
        sobre o prefixo. Comparado por `substr`, e não por LIKE: um
        Message-Id pode conter `_`, que o LIKE trataria como coringa e
        faria duas respostas diferentes passarem por uma só.
        """
        return self.con.execute(
            "SELECT 1 FROM respostas_email"
            " WHERE msg_id = ? OR substr(msg_id, 1, ?) = ?",
            (msg_id, len(msg_id) + 1, f"{msg_id}#"),
        ).fetchone() is not None

    def gravar_resposta_email(
        self,
        msg_id: str,
        acao_id: str,
        de: str,
        texto: str,
        encerra: bool,
        recebida_em: datetime,
    ) -> None:
        self.con.execute(
            "INSERT OR IGNORE INTO respostas_email (msg_id, acao_id, de, texto,"
            " encerra, recebida_em, lida_em) VALUES (?,?,?,?,?,?,?)",
            (msg_id, acao_id, de, texto, int(encerra),
             recebida_em.isoformat(), datetime.now().isoformat()),
        )
        self.con.commit()

    def respondeu_nas_ultimas(self, acao_id: str, horas: float) -> bool:
        """Houve resposta por e-mail dentro da janela de carência?

        É o que sustenta a promessa feita no corpo da cobrança: quem
        responde para de levar lembrete por um tempo. Sem isso, a pessoa
        responderia e seria cobrada de novo na rodada seguinte — a forma
        mais rápida de ensinar todo mundo a ignorar o sistema.
        """
        corte = (datetime.now() - timedelta(hours=horas)).isoformat()
        return self.con.execute(
            "SELECT 1 FROM respostas_email WHERE acao_id = ? AND recebida_em >= ?",
            (acao_id, corte),
        ).fetchone() is not None

    def respostas_de(self, acao_id: str) -> list[sqlite3.Row]:
        return list(self.con.execute(
            "SELECT * FROM respostas_email WHERE acao_id = ?"
            " ORDER BY recebida_em", (acao_id,)
        ))

    def acoes_aguardando_resposta(self) -> list[Acao]:
        """Ações que ainda esperam retorno de alguém.

        Inclui a vencida e a escalada de propósito: resposta que chega
        atrasada continua sendo resposta, e é justamente nesses casos que
        importa registrar que a pessoa finalmente se manifestou.
        """
        return [
            _para_acao(linha) for linha in self.con.execute(
                "SELECT * FROM acoes WHERE estado IN (?, ?, ?) ORDER BY prazo",
                (Estado.ABERTA.value, Estado.ESCALADA.value,
                 Estado.VENCIDA.value),
            )
        ]

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

    def totais_de_cobranca(self) -> tuple[int, int]:
        """(cobranças disparadas, das quais escaladas) — para o painel."""
        linha = self.con.execute(
            "SELECT COUNT(*) AS n,"
            " SUM(CASE WHEN rodada >= 1 THEN 1 ELSE 0 END) AS esc FROM cobrancas"
        ).fetchone()
        return int(linha["n"] or 0), int(linha["esc"] or 0)

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


def abrir(caminho: Path | str = "dados/nitronceo.db"):
    """O repositório certo para o ambiente.

    Com `NITRONCEO_DATABASE_URL` no ambiente, usa Postgres (Supabase) —
    é o de produção, e é o único que sobrevive ao container morrer. Sem
    ela, SQLite: os testes rodam sem rede e sem credencial, e quem está
    desenvolvendo não precisa de banco nenhum para começar.

    A escolha é por ambiente, e não por argumento, porque quem chama
    (motor, CLI, leitor de respostas) não deve ter opinião sobre onde a
    memória mora.
    """
    import os

    dsn = os.getenv("NITRONCEO_DATABASE_URL")
    if dsn:
        from .repositorio_pg import RepositorioPG

        return RepositorioPG(dsn)
    return Repositorio(caminho)
