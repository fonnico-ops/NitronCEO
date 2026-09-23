"""A mesma memória, em Postgres (Supabase).

Existe porque o SQLite vivia dentro do container que roda a matriz, e
container é efêmero. Cobrança que perde a memória vira cobrança repetida:
quem respondeu ontem é cobrado de novo hoje, e o time aprende a ignorar o
remetente em duas semanas.

A interface é idêntica à de `repositorio.Repositorio` de propósito — o
motor, o leitor de respostas e a CLI não sabem qual dos dois está por
baixo. O SQLite continua sendo o dos testes: rápido, sem rede, sem
credencial. O Postgres é o de produção.

Diferenças que o Postgres impõe e que estão tratadas aqui:

  - o parâmetro é `%s`, não `?`;
  - `date(x)` vira `x::date`;
  - `INSERT OR IGNORE` / `OR REPLACE` viram `ON CONFLICT`;
  - JSON vira JSONB de verdade, então `passos` e `contexto` voltam como
    lista e dict — sem `json.loads` no caminho de leitura;
  - timestamp é `TIMESTAMPTZ`, e datetime sobe e desce sem `isoformat()`.

Conexão em `NITRONCEO_DATABASE_URL` (a connection string do Supabase, com
service_role — as tabelas têm RLS ligado e nenhuma policy para anon).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any

from .acoes import Acao, Estado
from .avaliador import Nivel, Sinal

SCHEMA = os.getenv("NITRONCEO_SCHEMA", "nitronceo")


class RepositorioPG:
    def __init__(self, dsn: str | None = None, schema: str = SCHEMA) -> None:
        import psycopg
        from psycopg.rows import dict_row

        dsn = dsn or os.environ["NITRONCEO_DATABASE_URL"]
        self.schema = schema
        self.con = psycopg.connect(dsn, row_factory=dict_row, autocommit=True)
        # search_path resolve o schema uma vez, e o SQL abaixo fica igual
        # ao do SQLite — o que torna a diferença entre os dois auditável.
        with self.con.cursor() as cur:
            cur.execute(f'SET search_path TO "{schema}", public')

    def fechar(self) -> None:
        self.con.close()

    def _um(self, sql: str, args: tuple = ()) -> dict[str, Any] | None:
        with self.con.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchone()

    def _todos(self, sql: str, args: tuple = ()) -> list[dict[str, Any]]:
        with self.con.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall()

    def _exec(self, sql: str, args: tuple = ()) -> None:
        with self.con.cursor() as cur:
            cur.execute(sql, args)

    # ---------------------------------------------------------------- sinais

    def gravar_sinal(self, sinal: Sinal) -> None:
        from psycopg.types.json import Json

        self._exec(
            "INSERT INTO sinais (kpi_id, nivel, valor, unidade, modo, erro,"
            " linha, medido_em) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                sinal.kpi_id, sinal.nivel.value, sinal.valor, sinal.unidade,
                sinal.modo, sinal.erro, Json(_limpar(sinal.linha)),
                sinal.medido_em,
            ),
        )

    def dias_consecutivos_ruins(self, kpi_id: str, limite: int = 10) -> int:
        linhas = self._todos(
            "SELECT medido_em::date AS d,"
            "  MAX(CASE WHEN nivel IN ('vermelho','critico') THEN 1 ELSE 0 END) AS ruim"
            " FROM sinais WHERE kpi_id = %s GROUP BY medido_em::date"
            " ORDER BY d DESC LIMIT %s",
            (kpi_id, limite),
        )
        seguidos = 0
        for linha in linhas:
            if linha["ruim"]:
                seguidos += 1
            else:
                break
        return seguidos

    # ----------------------------------------------------------------- ações

    def salvar_acao(self, acao: Acao) -> bool:
        """Grava a ação. True se é nova, False se já existia.

        O `ON CONFLICT` faz num comando o que no SQLite eram dois — e
        elimina a janela entre o SELECT e o INSERT, que com duas rodadas
        simultâneas criaria a mesma ação duas vezes.
        """
        from psycopg.types.json import Json

        linha = self._um(
            "INSERT INTO acoes (id, kpi_id, titulo, passos, dono, nivel, valor,"
            " unidade, estado, escalonamentos, criada_em, prazo, contexto)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
            " ON CONFLICT (id) DO UPDATE SET"
            "   valor = EXCLUDED.valor, nivel = EXCLUDED.nivel,"
            "   titulo = EXCLUDED.titulo, contexto = EXCLUDED.contexto"
            " RETURNING (xmax = 0) AS nova",
            (
                acao.id, acao.kpi_id, acao.titulo, Json(acao.passos),
                acao.dono, acao.nivel.value, acao.valor, acao.unidade,
                acao.estado.value, acao.escalonamentos,
                acao.criada_em, acao.prazo, Json(_limpar(acao.contexto)),
            ),
        )
        return bool(linha and linha["nova"])

    def buscar_acao(self, acao_id: str) -> Acao | None:
        linha = self._um("SELECT * FROM acoes WHERE id = %s", (acao_id,))
        return _para_acao(linha) if linha else None

    def acoes_em_aberto(self) -> list[Acao]:
        return [
            _para_acao(x) for x in self._todos(
                "SELECT * FROM acoes WHERE estado IN (%s,%s) ORDER BY prazo",
                (Estado.ABERTA.value, Estado.ESCALADA.value),
            )
        ]

    def acoes_aguardando_resposta(self) -> list[Acao]:
        return [
            _para_acao(x) for x in self._todos(
                "SELECT * FROM acoes WHERE estado IN (%s,%s,%s) ORDER BY prazo",
                (Estado.ABERTA.value, Estado.ESCALADA.value,
                 Estado.VENCIDA.value),
            )
        ]

    def atualizar_estado(
        self, acao_id: str, estado: Estado, escalonamentos: int | None = None
    ) -> None:
        if escalonamentos is None:
            self._exec(
                "UPDATE acoes SET estado = %s WHERE id = %s",
                (estado.value, acao_id),
            )
        else:
            self._exec(
                "UPDATE acoes SET estado = %s, escalonamentos = %s WHERE id = %s",
                (estado.value, escalonamentos, acao_id),
            )

    def registrar_resposta(
        self, acao_id: str, texto: str, quando: datetime | None = None
    ) -> bool:
        linha = self._um(
            "UPDATE acoes SET estado = %s, resposta = %s, respondida_em = %s"
            " WHERE id = %s RETURNING id",
            (Estado.RESPONDIDA.value, texto, quando or datetime.now(), acao_id),
        )
        return linha is not None

    # ------------------------------------------------------ cadência e lotes

    def ultimo_disparo(self) -> datetime | None:
        linha = self._um("SELECT quando FROM disparos ORDER BY id DESC LIMIT 1")
        return linha["quando"] if linha else None

    def deve_disparar(self, intervalo_dias: int, agora: datetime | None = None) -> bool:
        ultimo = self.ultimo_disparo()
        if ultimo is None:
            return True
        agora = agora or datetime.now(tz=ultimo.tzinfo)
        return (agora.date() - ultimo.date()).days >= intervalo_dias

    def registrar_disparo(self, lotes: int, acoes: int) -> None:
        self._exec(
            "INSERT INTO disparos (quando, lotes, acoes) VALUES (%s,%s,%s)",
            (datetime.now(), lotes, acoes),
        )

    def registrar_lote(self, token: str, acao_ids: list[str], dono: str) -> None:
        agora = datetime.now()
        with self.con.cursor() as cur:
            cur.executemany(
                "INSERT INTO lotes (token, acao_id, dono, enviado_em)"
                " VALUES (%s,%s,%s,%s)"
                " ON CONFLICT (token, acao_id) DO UPDATE"
                " SET enviado_em = EXCLUDED.enviado_em",
                [(token, aid, dono, agora) for aid in acao_ids],
            )

    def acoes_do_lote(self, token: str) -> list[str]:
        return [
            x["acao_id"] for x in self._todos(
                "SELECT acao_id FROM lotes WHERE token = %s", (token,)
            )
        ]

    # ------------------------------------------------- respostas por e-mail

    def resposta_ja_lida(self, msg_id: str) -> bool:
        return self._um(
            "SELECT 1 AS x FROM respostas_email"
            " WHERE msg_id = %s OR substr(msg_id, 1, %s) = %s",
            (msg_id, len(msg_id) + 1, f"{msg_id}#"),
        ) is not None

    def gravar_resposta_email(
        self, msg_id: str, acao_id: str, de: str, texto: str,
        encerra: bool, recebida_em: datetime,
    ) -> None:
        self._exec(
            "INSERT INTO respostas_email (msg_id, acao_id, de, texto, encerra,"
            " recebida_em, lida_em) VALUES (%s,%s,%s,%s,%s,%s,%s)"
            " ON CONFLICT (msg_id) DO NOTHING",
            (msg_id, acao_id, de, texto, encerra, recebida_em, datetime.now()),
        )

    def respondeu_nas_ultimas(self, acao_id: str, horas: float) -> bool:
        return self._um(
            "SELECT 1 AS x FROM respostas_email"
            " WHERE acao_id = %s AND recebida_em >= %s",
            (acao_id, datetime.now().astimezone() - timedelta(hours=horas)),
        ) is not None

    def respostas_de(self, acao_id: str) -> list[dict[str, Any]]:
        return self._todos(
            "SELECT * FROM respostas_email WHERE acao_id = %s"
            " ORDER BY recebida_em",
            (acao_id,),
        )

    # ------------------------------------------------------------- cobranças

    def registrar_cobranca(
        self, acao_id: str, rodada: int, destinatario: str, canal: str, motivo: str
    ) -> None:
        self._exec(
            "INSERT INTO cobrancas (acao_id, rodada, destinatario, canal,"
            " enviada_em, motivo) VALUES (%s,%s,%s,%s,%s,%s)",
            (acao_id, rodada, destinatario, canal, datetime.now(), motivo),
        )

    def totais_de_cobranca(self) -> tuple[int, int]:
        linha = self._um(
            "SELECT COUNT(*) AS n,"
            " COUNT(*) FILTER (WHERE rodada > 1) AS escaladas FROM cobrancas"
        )
        return (linha["n"] or 0, linha["escaladas"] or 0) if linha else (0, 0)

    def cobrancas_de(self, acao_id: str) -> int:
        linha = self._um(
            "SELECT COUNT(*) AS n FROM cobrancas WHERE acao_id = %s", (acao_id,)
        )
        return linha["n"] if linha else 0


def _limpar(dados: dict[str, Any]) -> dict[str, Any]:
    """JSONB não engole Decimal nem datetime; vira texto o que não é nativo."""
    saida = {}
    for chave, valor in (dados or {}).items():
        if isinstance(valor, (str, int, float, bool)) or valor is None:
            saida[chave] = valor
        else:
            saida[chave] = str(valor)
    return saida


def _para_acao(linha: dict[str, Any]) -> Acao:
    """JSONB já volta como lista/dict — sem json.loads no caminho."""
    return Acao(
        id=linha["id"],
        kpi_id=linha["kpi_id"],
        titulo=linha["titulo"],
        passos=linha["passos"] or [],
        dono=linha["dono"],
        nivel=Nivel(linha["nivel"]),
        valor=linha["valor"],
        unidade=linha["unidade"],
        estado=Estado(linha["estado"]),
        escalonamentos=linha["escalonamentos"],
        criada_em=linha["criada_em"],
        prazo=linha["prazo"],
        respondida_em=linha["respondida_em"],
        resposta=linha["resposta"],
        contexto=linha["contexto"] or {},
    )
