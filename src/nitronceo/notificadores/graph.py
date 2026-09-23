"""Teams e Outlook via Microsoft Graph (client credentials).

Registro de app no Entra ID com permissões de aplicação:
    Mail.Send                        -> e-mail
    ChannelMessage.Send              -> mensagem em canal de equipe
    Chat.Create + ChatMessage.Send   -> mensagem direta (1:1)

Variáveis de ambiente:
    MS_TENANT_ID  MS_CLIENT_ID  MS_CLIENT_SECRET
    MS_REMETENTE   caixa que assina os e-mails (ex.: ceo-bot@nitron.com.br)

Mensagem direta 1:1 por client credentials exige que o app tenha permissão de
aplicação para chats; se a TI não liberar isso, o fallback natural é mandar
tudo no canal da área e deixar o e-mail como trilha individual.
"""

from __future__ import annotations

import os
import re
from typing import Any

from .base import Mensagem

GRAPH = "https://graph.microsoft.com/v1.0"


class _Graph:
    def __init__(self) -> None:
        self.tenant = os.environ["MS_TENANT_ID"]
        self.client_id = os.environ["MS_CLIENT_ID"]
        self.secret = os.environ["MS_CLIENT_SECRET"]
        self._token: str | None = None
        self._sessao = None

    def _http(self):
        if self._sessao is None:
            import requests

            self._sessao = requests.Session()
        return self._sessao

    def token(self) -> str:
        if self._token:
            return self._token
        resp = self._http().post(
            f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
            timeout=30,
        )
        resp.raise_for_status()
        self._token = resp.json()["access_token"]
        return self._token

    def post(self, caminho: str, corpo: dict[str, Any]) -> Any:
        resp = self._http().post(
            f"{GRAPH}{caminho}",
            json=corpo,
            headers={"Authorization": f"Bearer {self.token()}"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json() if resp.content else None

    def get(self, caminho: str) -> Any:
        resp = self._http().get(
            f"{GRAPH}{caminho}",
            headers={"Authorization": f"Bearer {self.token()}"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()


class Teams:
    nome = "teams"

    def __init__(self, graph: _Graph | None = None) -> None:
        self.graph = graph or _Graph()

    def enviar(self, msg: Mensagem) -> bool:
        corpo = _html(msg)
        ok = True

        if msg.canal_equipe:
            ok &= self._canal(
                msg.canal_equipe["team"], msg.canal_equipe["canal"], corpo, msg.urgente
            )

        for upn in msg.para_teams:
            ok &= self._direto(upn, corpo, msg.urgente)

        return ok

    def _canal(self, equipe: str, canal: str, html: str, urgente: bool) -> bool:
        team_id = self._id_equipe(equipe)
        canal_id = self._id_canal(team_id, canal)
        self.graph.post(
            f"/teams/{team_id}/channels/{canal_id}/messages",
            {
                "body": {"contentType": "html", "content": html},
                "importance": "high" if urgente else "normal",
            },
        )
        return True

    def _direto(self, upn: str, html: str, urgente: bool) -> bool:
        chat = self.graph.post(
            "/chats",
            {
                "chatType": "oneOnOne",
                "members": [
                    {
                        "@odata.type": "#microsoft.graph.aadUserConversationMember",
                        "roles": ["owner"],
                        "user@odata.bind": (
                            f"https://graph.microsoft.com/v1.0/users('{upn}')"
                        ),
                    }
                ],
            },
        )
        self.graph.post(
            f"/chats/{chat['id']}/messages",
            {
                "body": {"contentType": "html", "content": html},
                "importance": "high" if urgente else "normal",
            },
        )
        return True

    def _id_equipe(self, nome: str) -> str:
        for t in self.graph.get("/groups?$filter=resourceProvisioningOptions/Any("
                                "x:x eq 'Team')")["value"]:
            if t["displayName"] == nome:
                return t["id"]
        raise LookupError(f"Equipe do Teams não encontrada: {nome}")

    def _id_canal(self, team_id: str, nome: str) -> str:
        for c in self.graph.get(f"/teams/{team_id}/channels")["value"]:
            if c["displayName"] == nome:
                return c["id"]
        raise LookupError(f"Canal não encontrado: {nome}")


class EmailOutlook:
    nome = "email"

    def __init__(self, graph: _Graph | None = None, remetente: str | None = None) -> None:
        self.graph = graph or _Graph()
        self.remetente = remetente or os.environ["MS_REMETENTE"]

    def enviar(self, msg: Mensagem) -> bool:
        if not msg.destinatarios:
            return True
        self.graph.post(
            f"/users/{self.remetente}/sendMail",
            {
                "message": {
                    "subject": msg.assunto,
                    "body": {"contentType": "HTML", "content": _html(msg)},
                    "toRecipients": [
                        {"emailAddress": {"address": e}} for e in msg.destinatarios
                    ],
                    "importance": "high" if msg.urgente else "normal",
                },
                "saveToSentItems": True,
            },
        )
        return True


# Cada nível de título, do mais longo para o mais curto: `## ` casaria
# dentro de `### ` se a ordem fosse outra.
TITULOS = (("### ", "h3"), ("## ", "h2"), ("# ", "h1"))

_NEGRITO = re.compile(r"\*\*(.+?)\*\*")
_ITALICO = re.compile(r"(?<![\w*])_(.+?)_(?![\w*])")


def _inline(texto: str) -> str:
    """Negrito e itálico. O que sobrar de `*` ou `_` é texto literal.

    O negrito carrega significado no corpo da cobrança — é o número e o
    prazo que estão marcados. Apagar os asteriscos, como esta função fazia
    antes, entregava a frase inteira no mesmo peso.
    """
    texto = _NEGRITO.sub(r"<strong>\1</strong>", texto)
    return _ITALICO.sub(r"<em>\1</em>", texto)


def _html(msg: Mensagem) -> str:
    """Markdown mínimo -> HTML. Nem o Graph nem o GHL renderizam markdown."""
    partes: list[str] = []
    lista_aberta = False

    for bruta in msg.corpo_md.splitlines():
        linha = bruta.strip()
        item = linha.startswith(("- ", "* "))

        if lista_aberta and not item:
            partes.append("</ul>")
            lista_aberta = False

        if item:
            if not lista_aberta:
                partes.append("<ul>")
                lista_aberta = True
            partes.append(f"<li>{_inline(linha[2:])}</li>")
            continue

        if not linha:
            partes.append("<br>")
            continue

        if set(linha) <= {"-", "_", "*"} and len(linha) >= 3:
            partes.append("<hr>")
            continue

        for marca, tag in TITULOS:
            if linha.startswith(marca):
                partes.append(f"<{tag}>{_inline(linha[len(marca):])}</{tag}>")
                break
        else:
            partes.append(f"<p>{_inline(linha)}</p>")

    if lista_aberta:
        partes.append("</ul>")

    corpo = "\n".join(partes)
    return f"<div style='font-family:Segoe UI,Arial,sans-serif'>{corpo}</div>"
