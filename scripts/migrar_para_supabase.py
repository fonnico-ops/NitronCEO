#!/usr/bin/env python3
"""Leva a memória do SQLite para o Postgres, sem perder nada.

Roda uma vez, na virada. Depois disso o SQLite fica só para os testes.

    NITRONCEO_DATABASE_URL=postgresql://... \
        python scripts/migrar_para_supabase.py dados/nitronceo.db

É idempotente: pode rodar de novo sem duplicar. As ações usam
`ON CONFLICT DO UPDATE` e as respostas `DO NOTHING`, porque uma resposta
já lida não deve ser reescrita com a leitura de agora.

Os sinais são a exceção deliberada: não têm chave natural, então rodar
duas vezes duplicaria a série histórica. Por isso o script recusa
continuar se já houver sinais do lado do Postgres — salvo `--forcar`.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def _data(bruto):
    if bruto in (None, ""):
        return None
    if isinstance(bruto, datetime):
        return bruto
    return datetime.fromisoformat(str(bruto))


def migrar(caminho_sqlite: str, forcar: bool = False) -> int:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Json

    dsn = os.environ["NITRONCEO_DATABASE_URL"]
    origem = sqlite3.connect(caminho_sqlite)
    origem.row_factory = sqlite3.Row
    destino = psycopg.connect(dsn, row_factory=dict_row, autocommit=True)

    with destino.cursor() as cur:
        cur.execute('SET search_path TO "nitronceo", public')
        cur.execute("SELECT COUNT(*) AS n FROM sinais")
        ja_tem = cur.fetchone()["n"]

    if ja_tem and not forcar:
        print(
            f"O Postgres já tem {ja_tem} sinais. Migrar de novo duplicaria a "
            "série histórica — use --forcar se for mesmo isso que você quer.",
            file=sys.stderr,
        )
        return 1

    contagem = {}

    with destino.cursor() as cur:
        # ORDEM IMPORTA: ações antes de tudo que as referencia.
        acoes = origem.execute("SELECT * FROM acoes").fetchall()
        for a in acoes:
            cur.execute(
                "INSERT INTO acoes (id, kpi_id, titulo, passos, dono, nivel,"
                " valor, unidade, estado, escalonamentos, criada_em, prazo,"
                " respondida_em, resposta, contexto)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                # `contexto` PRECISA entrar aqui. Sem ele, uma linha que já
                # existisse no Postgres com apuração mais pobre sobrevivia à
                # migração — foi o que aconteceu em 23/09/2026: as 21 ações
                # subiram sem o LISTAGG dos SQLs, e as cobranças de 24/09
                # saíram com "69 paradas" no lugar de "INJETORA 31: 110,3h em
                # 3 paradas". O detalhe nomeado é o que faz alguém responder.
                " ON CONFLICT (id) DO UPDATE SET"
                "  estado = EXCLUDED.estado,"
                "  escalonamentos = EXCLUDED.escalonamentos,"
                "  respondida_em = EXCLUDED.respondida_em,"
                "  resposta = EXCLUDED.resposta,"
                "  titulo = EXCLUDED.titulo,"
                "  valor = EXCLUDED.valor,"
                "  contexto = EXCLUDED.contexto",
                (
                    a["id"], a["kpi_id"], a["titulo"],
                    Json(json.loads(a["passos"] or "[]")),
                    a["dono"], a["nivel"], a["valor"], a["unidade"],
                    a["estado"], a["escalonamentos"],
                    _data(a["criada_em"]), _data(a["prazo"]),
                    _data(a["respondida_em"]), a["resposta"],
                    Json(json.loads(a["contexto"] or "{}")),
                ),
            )
        contagem["acoes"] = len(acoes)

        sinais = origem.execute("SELECT * FROM sinais").fetchall()
        for s in sinais:
            cur.execute(
                "INSERT INTO sinais (kpi_id, nivel, valor, unidade, modo,"
                " erro, linha, medido_em) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    s["kpi_id"], s["nivel"], s["valor"], s["unidade"],
                    s["modo"], s["erro"],
                    Json(json.loads(s["linha"] or "{}")), _data(s["medido_em"]),
                ),
            )
        contagem["sinais"] = len(sinais)

        cobrancas = origem.execute("SELECT * FROM cobrancas").fetchall()
        for c in cobrancas:
            cur.execute(
                "INSERT INTO cobrancas (acao_id, rodada, destinatario, canal,"
                " enviada_em, motivo) VALUES (%s,%s,%s,%s,%s,%s)",
                (
                    c["acao_id"], c["rodada"], c["destinatario"], c["canal"],
                    _data(c["enviada_em"]), c["motivo"],
                ),
            )
        contagem["cobrancas"] = len(cobrancas)

        for tabela, sql, campos in (
            (
                "respostas_email",
                "INSERT INTO respostas_email (msg_id, acao_id, de, texto,"
                " encerra, recebida_em, lida_em) VALUES (%s,%s,%s,%s,%s,%s,%s)"
                " ON CONFLICT (msg_id) DO NOTHING",
                lambda r: (
                    r["msg_id"], r["acao_id"], r["de"], r["texto"],
                    bool(r["encerra"]), _data(r["recebida_em"]),
                    _data(r["lida_em"]),
                ),
            ),
            (
                "lotes",
                "INSERT INTO lotes (token, acao_id, dono, enviado_em)"
                " VALUES (%s,%s,%s,%s)"
                " ON CONFLICT (token, acao_id) DO NOTHING",
                lambda r: (
                    r["token"], r["acao_id"], r["dono"], _data(r["enviado_em"])
                ),
            ),
            (
                "disparos",
                "INSERT INTO disparos (quando, lotes, acoes)"
                " VALUES (%s,%s,%s)",
                lambda r: (_data(r["quando"]), r["lotes"], r["acoes"]),
            ),
        ):
            try:
                linhas = origem.execute(f"SELECT * FROM {tabela}").fetchall()
            except sqlite3.OperationalError:
                # Banco antigo, de antes desta tabela existir.
                contagem[tabela] = 0
                continue
            for linha in linhas:
                cur.execute(sql, campos(linha))
            contagem[tabela] = len(linhas)

    origem.close()
    destino.close()

    for tabela, n in contagem.items():
        print(f"  {n:6} {tabela}")
    print(f"\nMigrado de {caminho_sqlite} para o Supabase.")
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    raise SystemExit(
        migrar(args[0] if args else "dados/nitronceo.db", "--forcar" in sys.argv)
    )
