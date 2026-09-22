"""Cliente de leitura do Sankhya (Oracle) via DbExplorerSP.

Somente SELECT/WITH. Escrita no ERP passa por DatasetSP.save — e nada aqui
precisa escrever: o cérebro lê o ERP e escreve no próprio banco de ações.

Credenciais por ambiente:
    SANKHYA_URL       https://<host>/mge
    SANKHYA_USER
    SANKHYA_PASSWORD

O Sankhya cancela chamadas paralelas na mesma sessão HTTP com erro de
concorrência, então as consultas são serializadas de propósito.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Protocol

_PROIBIDO = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|ALTER|CREATE|TRUNCATE|GRANT)\b",
    re.IGNORECASE,
)


class Fonte(Protocol):
    def consultar(self, sql: str) -> list[dict[str, Any]]: ...


def montar_sql(caminho: Path, params: dict[str, Any]) -> str:
    """Substitui {{PARAM}} e recusa SQL que não seja de leitura."""
    sql = caminho.read_text(encoding="utf-8")
    for chave, valor in params.items():
        sql = sql.replace("{{" + chave + "}}", str(valor))

    faltando = re.findall(r"\{\{(\w+)\}\}", sql)
    if faltando:
        raise KeyError(f"{caminho.name}: parâmetros sem valor: {sorted(set(faltando))}")

    corpo = re.sub(r"--[^\n]*", "", sql)
    if _PROIBIDO.search(corpo):
        raise ValueError(f"{caminho.name}: contém comando de escrita")
    return sql.strip().rstrip(";")


class SankhyaREST:
    """Acesso ao Sankhya de produção."""

    def __init__(
        self,
        url: str | None = None,
        usuario: str | None = None,
        senha: str | None = None,
        timeout: int = 180,
    ) -> None:
        self.url = (url or os.environ["SANKHYA_URL"]).rstrip("/")
        self.usuario = usuario or os.environ["SANKHYA_USER"]
        self.senha = senha or os.environ["SANKHYA_PASSWORD"]
        self.timeout = timeout
        self._sessao = None
        self._token: str | None = None

    def _http(self):
        if self._sessao is None:
            import requests  # importado aqui para manter o dry-run sem dependência

            self._sessao = requests.Session()
        return self._sessao

    def _login(self) -> str:
        if self._token:
            return self._token
        resp = self._http().post(
            f"{self.url}/service.sbr",
            params={"serviceName": "MobileLoginSP.login", "outputType": "json"},
            json={
                "serviceName": "MobileLoginSP.login",
                "requestBody": {
                    "NOMUSU": {"$": self.usuario},
                    "INTERNO": {"$": self.senha},
                },
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        corpo = resp.json()
        if corpo.get("status") not in ("1", 1):
            raise RuntimeError(f"Login Sankhya recusado: {corpo.get('statusMessage')}")
        self._token = corpo["responseBody"]["jsessionid"]["$"]
        return self._token

    def consultar(self, sql: str) -> list[dict[str, Any]]:
        token = self._login()
        resp = self._http().post(
            f"{self.url}/service.sbr",
            params={
                "serviceName": "DbExplorerSP.executeQuery",
                "outputType": "json",
                "mgeSession": token,
            },
            json={
                "serviceName": "DbExplorerSP.executeQuery",
                "requestBody": {"sql": sql},
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        corpo = resp.json()
        if corpo.get("status") not in ("1", 1):
            raise RuntimeError(f"Consulta recusada: {corpo.get('statusMessage')}")

        body = corpo["responseBody"]
        colunas = [c["name"] for c in body["fieldsMetadata"]]
        return [dict(zip(colunas, linha)) for linha in body.get("rows", [])]


class FonteArquivo:
    """Fonte de teste: lê resultados de fixtures/<kpi>.json.

    Existe para que a lógica de avaliação, cobrança e escalada possa ser
    exercitada sem tocar na produção.
    """

    def __init__(self, diretorio: Path) -> None:
        self.diretorio = Path(diretorio)
        self._kpi_atual: str | None = None

    def para(self, kpi_id: str) -> FonteArquivo:
        self._kpi_atual = kpi_id
        return self

    def consultar(self, sql: str) -> list[dict[str, Any]]:  # noqa: ARG002
        if not self._kpi_atual:
            raise RuntimeError("FonteArquivo.para(kpi_id) não foi chamado")
        arquivo = self.diretorio / f"{self._kpi_atual}.json"
        if not arquivo.exists():
            return []
        return json.loads(arquivo.read_text(encoding="utf-8"))
