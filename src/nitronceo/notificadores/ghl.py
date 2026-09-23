"""Envio por Go High Level (API v2) — o sender do próprio GHL.

A conta da Nitron já envia por aqui: o domínio `nitron.com.br` está
verificado, e há fluxo outbound ativo para caixas internas —
`expedicao2@`, `claudia.ribeiro@`, `financeiro@hyakgroup.com.br`. Não é
preciso consentimento no Entra, nem sincronismo de Outlook, nem subdomínio
novo. O caminho está aberto.

O que NÃO está resolvido é a quem cada cobrança vai parar.

O GHL só envia para um `contactId`. E a base da location Nitron mistura
funcionários com clientes, o que cria uma armadilha concreta, verificada
em 23/09/2026:

    expedicao2@nitron.com.br      -> contato limpo, sem tags        ✅
    cristiane.alves@nitron.com.br -> "Cristiane ATLETICO CLUBE",
                                     cliente COOPERCOTIA cod 100526,
                                     tags sankhya-cliente / nina-*,
                                     seguido pela Nina Financeiro    ❌

O e-mail corporativo da compradora está cadastrado no contato de um
cliente. Mandar a cobrança de Compras para esse id levaria assunto interno
para a conversa do cliente, e ainda poderia disparar automação da Nina.

Por isso este módulo NÃO resolve contato por busca de e-mail. Ele exige
que o `contactId` esteja declarado em `pessoas.yaml`, pessoa por pessoa, e
recusa quem não tem. Duas travas, nesta ordem:

  1. o id tem que estar declarado — busca automática está proibida;
  2. o contato não pode carregar tag de cliente.

`nitronceo ghl-contatos` resolve os ids e mostra quais colidem com
cliente, para a declaração ser uma revisão humana e não um palpite.

Variáveis de ambiente:
    GHL_TOKEN          Private Integration token (Bearer)
    GHL_LOCATION_ID    location onde os contatos estão
    GHL_REMETENTE      e-mail que assina (precisa de domínio verificado)
    GHL_TAGS_CLIENTE   tags que marcam contato de cliente
                       (padrão: sankhya-cliente,nina-conversa,nina-lead-rep)
"""

from __future__ import annotations

import os
from datetime import datetime  # noqa: TC003 - usado na anotação de exportar_emails
from typing import Any

from .base import Mensagem
from .graph import _html

BASE = "https://services.leadconnectorhq.com"
VERSAO = "2021-07-28"

# Tags que provam que o contato NÃO é um funcionário sendo cobrado.
# `lead-puro` entrou porque o contato do próprio CEO a carrega, junto com
# campos de um anúncio de Instagram e a Nina Financeiro como responsável:
# o e-mail está certo, mas a conversa é de campanha, e cobrança interna não
# entra ali.
TAGS_CLIENTE_PADRAO = "sankhya-cliente,nina-conversa,nina-lead-rep,lead-puro"


class ContatoInvalido(LookupError):
    """Não posso jurar que esse contato é a pessoa que quero cobrar."""


class GoHighLevel:
    nome = "ghl"

    def __init__(
        self,
        token: str | None = None,
        location: str | None = None,
        remetente: str | None = None,
        tags_cliente: list[str] | None = None,
        sessao: Any | None = None,
    ) -> None:
        self.token = token or os.environ["GHL_TOKEN"]
        self.location = location or os.environ["GHL_LOCATION_ID"]
        # Quem assina. O padrão é o CEO: a cobrança tem o peso de vir
        # dele, e o domínio nitron.com.br já está verificado no GHL.
        self.remetente = remetente or os.getenv(
            "GHL_REMETENTE", "renato.fonseca@nitron.com.br"
        )
        self.tags_cliente = {
            t.strip().lower()
            for t in (
                tags_cliente
                or os.getenv("GHL_TAGS_CLIENTE", TAGS_CLIENTE_PADRAO).split(",")
            )
            if (t.strip() if isinstance(t, str) else t)
        }
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

    def buscar(self, email: str) -> list[dict[str, Any]]:
        """Os contatos com este e-mail exato. Para diagnóstico, não para envio."""
        resp = self._http().get(
            f"{BASE}/contacts/lookup",
            params={"email": email, "limit": 20},
            headers=self._cabecalhos(),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("contacts", [])

    def e_de_cliente(self, contato: dict[str, Any]) -> bool:
        tags = {str(t).lower() for t in (contato.get("tags") or [])}
        return bool(tags & self.tags_cliente)

    def conferir(self, contato_id: str) -> dict[str, Any]:
        """Lê o contato declarado e recusa se for de cliente.

        A checagem é feita no momento do envio, e não só na declaração,
        porque a base muda: um contato interno hoje pode receber a tag
        `sankhya-cliente` amanhã numa sincronização.
        """
        resp = self._http().get(
            f"{BASE}/contacts/{contato_id}",
            headers=self._cabecalhos(),
            timeout=30,
        )
        if resp.status_code == 404:
            raise ContatoInvalido(
                f"O contato {contato_id} declarado em pessoas.yaml não existe "
                "mais no GHL. Rode `nitronceo ghl-contatos` e atualize."
            )
        resp.raise_for_status()
        contato = resp.json().get("contact", resp.json())

        if self.e_de_cliente(contato):
            nome = contato.get("contactName") or contato.get("firstName") or "?"
            tags = ", ".join(contato.get("tags") or [])
            raise ContatoInvalido(
                f"O contato {contato_id} ({nome}) carrega tag de CLIENTE "
                f"[{tags}]. Cobrança interna não vai para a conversa de um "
                "cliente — corrija o cadastro antes de declarar este id."
            )
        return contato

    # ------------------------------------------------------------- enviar

    def enviar(self, msg: Mensagem) -> bool:
        if not msg.contatos_ghl:
            # Silêncio declarado, não falha: quem não tem contato declarado
            # é cobrado pelos outros canais. Melhor não sair do que sair
            # para a caixa errada.
            return True

        ok = True
        for contato_id in msg.contatos_ghl:
            try:
                self.conferir(contato_id)
            except ContatoInvalido as exc:
                print(f"[ghl] não enviei para {contato_id}: {exc}")
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

    # ---------------------------------------------------------- respostas

    def exportar_emails(
        self, desde: "datetime", limite: int = 100
    ) -> list[dict[str, Any]]:
        """E-mails da location desde a data, mais novos primeiro.

        É por aqui que a resposta a uma cobrança enviada pelo GHL volta:
        ela não chega em caixa nenhuma nossa, chega como mensagem
        `inbound` na conversa. O `limit` tem piso de 10 do lado do GHL.
        """
        pagina, cursor = [], None
        while True:
            params = {
                "channel": "Email",
                "limit": min(max(limite - len(pagina), 10), 100),
                "startDate": desde.astimezone().isoformat(),
                "sortBy": "createdAt",
                "sortOrder": "desc",
            }
            if cursor:
                params["cursor"] = cursor
            resp = self._http().get(
                f"{BASE}/conversations/messages/export",
                params=params,
                headers=self._cabecalhos(),
                timeout=30,
            )
            resp.raise_for_status()
            corpo = resp.json()
            pagina += corpo.get("messages", [])
            cursor = corpo.get("nextCursor")
            # O cursor do GHL vale 2 minutos; parar no limite pedido evita
            # paginar uma caixa inteira atrás de meia dúzia de respostas.
            if not cursor or len(pagina) >= limite:
                return pagina[:limite]

    def email_detalhe(self, email_message_id: str) -> dict[str, Any]:
        """O e-mail inteiro: `from`, `to`, `body`, `subject`.

        Necessário porque a listagem devolve a mensagem `inbound`
        praticamente vazia — só id, direction e `meta.email`. O corpo e o
        remetente da resposta só existem aqui.
        """
        resp = self._http().get(
            f"{BASE}/conversations/messages/email/{email_message_id}",
            headers=self._cabecalhos(),
            timeout=30,
        )
        resp.raise_for_status()
        corpo = resp.json()
        return corpo.get("emailMessage", corpo)

    # --------------------------------------------------------- diagnóstico

    def diagnosticar(self, emails: list[str]) -> list[dict[str, Any]]:
        """Para cada e-mail: que contato existe, e dá para cobrar por ele?"""
        laudo = []
        for email in emails:
            achados = self.buscar(email)
            limpos = [c for c in achados if not self.e_de_cliente(c)]
            laudo.append({
                "email": email,
                "achados": len(achados),
                "contato_id": limpos[0]["id"] if len(limpos) == 1 else None,
                "nome": " ".join(filter(None, [
                    (limpos[0].get("firstName") if limpos else None),
                    (limpos[0].get("lastName") if limpos else None),
                ])) if limpos else "",
                "de_cliente": [
                    {
                        "id": c["id"],
                        "nome": " ".join(filter(None, [
                            c.get("firstName"), c.get("lastName")
                        ])),
                        "tags": c.get("tags") or [],
                    }
                    for c in achados if self.e_de_cliente(c)
                ],
            })
        return laudo
