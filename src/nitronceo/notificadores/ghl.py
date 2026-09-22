"""Envio por Go High Level (API v2).

Terceiro canal, ao lado do Teams e do Outlook. O GHL manda e-mail a partir
de um *contato* da location — não de um endereço avulso. Isso tem uma
consequência que precisa estar escrita aqui e não descoberta em produção:

    A location da Nitron no GHL contém CLIENTES, não funcionários.

Uma busca por `cristiane.alves@nitron.com.br` na conta atual resolve para
"Cristiane ATLETICO CLUBE" — um contato de cliente, com tags de campanha,
1.041 dias sem comprar. Mandar a cobrança de Compras para esse contato
enviaria o assunto interno da Nitron para a caixa errada e ainda sujaria a
base de marketing.

Por isso este notificador **falha alto** quando não encontra um contato
inequívoco para o e-mail do destinatário, em vez de enviar para o primeiro
resultado parecido. Enquanto não existir uma sub-conta (ou um conjunto de
contatos marcados com a tag interna) com os donos de cobrança cadastrados,
o GHL não é um canal utilizável para cobrança interna — e dizer isso é
mais útil que um `200 OK` que foi para a pessoa errada.

Variáveis de ambiente:
    GHL_TOKEN         Private Integration token (Bearer)
    GHL_LOCATION_ID   location onde os contatos internos estão
    GHL_REMETENTE     e-mail que assina (opcional; usa o padrão da location)
    GHL_TAG_INTERNA   tag que marca contato de funcionário (padrão: nitron-interno)
"""

from __future__ import annotations

import os
from typing import Any

from .base import Mensagem
from .graph import _html

BASE = "https://services.leadconnectorhq.com"
VERSAO = "2021-07-28"


class ContatoAmbiguo(LookupError):
    """Achei contato, mas não posso jurar que é a pessoa certa."""


class GoHighLevel:
    nome = "ghl"

    def __init__(
        self,
        token: str | None = None,
        location: str | None = None,
        remetente: str | None = None,
        tag_interna: str | None = None,
        sessao: Any | None = None,
    ) -> None:
        self.token = token or os.environ["GHL_TOKEN"]
        self.location = location or os.environ["GHL_LOCATION_ID"]
        self.remetente = remetente or os.getenv("GHL_REMETENTE")
        self.tag_interna = (
            tag_interna or os.getenv("GHL_TAG_INTERNA", "nitron-interno")
        ).lower()
        self._sessao = sessao

    # --------------------------------------------------------------- http

    def _http(self):
        if self._sessao is None:
            import requests

            self._sessao = requests.Session()
        return self._sessao

    def _cabecalhos(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Version": VERSAO,
            "Accept": "application/json",
        }

    # ------------------------------------------------------------ contato

    def contato(self, email: str) -> str:
        """Id do contato interno para este e-mail, ou erro explicando por quê.

        Duas travas, nesta ordem: o e-mail tem que bater exatamente, e o
        contato tem que carregar a tag interna. A segunda existe porque a
        primeira sozinha já falhou: um contato de cliente pode ter sido
        cadastrado com o e-mail corporativo de um funcionário.
        """
        resp = self._http().get(
            f"{BASE}/contacts/",
            params={"locationId": self.location, "query": email, "limit": 20},
            headers=self._cabecalhos(),
            timeout=30,
        )
        resp.raise_for_status()
        achados = resp.json().get("contacts", [])

        exatos = [
            c for c in achados
            if (c.get("email") or "").strip().lower() == email.strip().lower()
        ]
        if not exatos:
            raise ContatoAmbiguo(
                f"Nenhum contato no GHL com o e-mail {email}. "
                f"{len(achados)} resultado(s) parecido(s) foram ignorados de "
                "propósito: enviar para um 'parecido' é enviar para a pessoa "
                "errada."
            )

        internos = [
            c for c in exatos
            if any(t.lower() == self.tag_interna for t in (c.get("tags") or []))
        ]
        if not internos:
            nomes = ", ".join(c.get("contactName", "?") for c in exatos[:3])
            raise ContatoAmbiguo(
                f"O e-mail {email} existe no GHL ({nomes}), mas sem a tag "
                f"'{self.tag_interna}'. Esses contatos são de CLIENTE. "
                "Cadastre o funcionário e marque-o com a tag antes de usar "
                "o GHL como canal de cobrança."
            )
        if len(internos) > 1:
            raise ContatoAmbiguo(
                f"{len(internos)} contatos internos com o e-mail {email}. "
                "Deduplique no GHL — não dá para escolher por conta própria."
            )
        return internos[0]["id"]

    # ------------------------------------------------------------- enviar

    def enviar(self, msg: Mensagem) -> bool:
        if not msg.destinatarios:
            return True

        ok = True
        for email in msg.destinatarios:
            try:
                contato_id = self.contato(email)
            except ContatoAmbiguo as exc:
                # Não silencia: o motor precisa saber que este canal não
                # entregou, para não contar a cobrança como enviada.
                print(f"[ghl] não enviei para {email}: {exc}")
                ok = False
                continue

            corpo: dict[str, Any] = {
                "type": "Email",
                "contactId": contato_id,
                "subject": msg.assunto,
                "html": _html(msg),
            }
            if self.remetente:
                corpo["emailFrom"] = self.remetente

            resp = self._http().post(
                f"{BASE}/conversations/messages",
                json=corpo,
                headers={**self._cabecalhos(), "Content-Type": "application/json"},
                timeout=30,
            )
            resp.raise_for_status()

        return ok
