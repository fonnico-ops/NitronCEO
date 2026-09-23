"""Lê as respostas que chegam por e-mail e as amarra de volta na cobrança.

Quando a cobrança sai do e-mail do CEO, a pessoa responde no e-mail — não
no painel. Isso é o comportamento certo dela e o problema do sistema: a
resposta cai numa caixa de entrada e a ação continua aberta para sempre,
subindo a escada contra alguém que já respondeu.

O elo é um token no assunto:

    ⏰ COBRANÇA [NTR-a1b2c3d4]: NTR Log emitiu apenas 2.6% do frete

O token sobrevive ao `RE:` que o Outlook põe na frente, e é o que permite
achar a resposta sem depender de thread-id, de plus-addressing (que o
tenant pode não ter ligado) nem de o respondente citar número de ação.

Duas decisões que valem explicação:

**Responder não encerra.** Uma resposta registra, aparece no painel e no
pulso, mas a ação só fecha quando a pessoa escreve RESOLVIDO. "Vou ver
amanhã" é retorno legítimo e não é solução; encerrar nele seria ensinar o
sistema a aceitar evasiva. A escada de cobrança, no entanto, para: quem
respondeu não leva lembrete.

**O e-mail lido é deduplicado pelo Message-Id.** A caixa é varrida inteira
a cada rodada; sem isso a mesma resposta seria registrada de novo toda vez.

Há dois leitores, um por caminho de entrega, com a mesma regra de
encerramento:

  `LeitorDeCaixa`  — a cobrança saiu pelo Microsoft Graph, a resposta volta
                     para a caixa que assinou.
  `LeitorDoGHL`    — a cobrança saiu pelo sender do GHL, e a resposta volta
                     para a *conversa* do GHL, não para caixa nenhuma. Sem
                     este leitor, quem responde uma cobrança do GHL continua
                     sendo cobrado — o defeito que o outro leitor existe
                     para evitar, reaparecendo pelo outro canal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from .repositorio import Repositorio

# O token que amarra a resposta na ação. Curto para não poluir o assunto, e
# com prefixo para não colidir com número de pedido ou de nota.
TOKEN = re.compile(r"\[NTR-([0-9a-f]{8})\]", re.IGNORECASE)

# A palavra que fecha. Sozinha numa linha ou no começo da resposta — não
# vale no meio de uma frase, senão "isso não está resolvido" encerraria.
ENCERRA = re.compile(r"^\s*(resolvido|resolvida)\b", re.IGNORECASE)

# Onde o Outlook começa a citar o e-mail original. Tudo daqui para baixo é
# a cobrança de volta, não a resposta da pessoa.
CITACAO = re.compile(
    r"^\s*(de:|from:|enviada em:|sent:|em .{0,40} escreveu:|"
    r"-{3,}\s*mensagem original|_{5,})",
    re.IGNORECASE | re.MULTILINE,
)


def marcar(acao_id: str) -> str:
    """O token de uma ação, como aparece no assunto."""
    return f"[NTR-{acao_id[:8].lower()}]"


def acao_do_assunto(assunto: str) -> str | None:
    achado = TOKEN.search(assunto or "")
    return achado.group(1).lower() if achado else None


def limpar(corpo: str) -> str:
    """O que a pessoa escreveu, sem a cobrança citada embaixo.

    Não tenta ser um parser de e-mail: corta no primeiro marcador de
    citação e devolve o que veio antes. Se não achar marcador, devolve
    tudo — melhor um texto com sobra que um texto cortado no lugar errado.
    """
    # Tag de bloco vira quebra de linha ANTES de apagar as tags. O corte da
    # citação depende do "De:" estar no começo de uma linha, e num e-mail
    # HTML ele vem dentro de um <div> — sem isto o corpo inteiro vira uma
    # linha só e a cobrança citada entra na resposta.
    texto = re.sub(
        r"<\s*(br|/p|/div|/tr|/li|/h[1-6]|/blockquote)\s*/?>",
        "\n", corpo or "", flags=re.IGNORECASE,
    )
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = (
        texto.replace("&nbsp;", " ").replace("&amp;", "&")
        .replace("&lt;", "<").replace("&gt;", ">")
    )
    corte = CITACAO.search(texto)
    if corte:
        texto = texto[: corte.start()]
    linhas = [ln.strip() for ln in texto.splitlines()]
    return "\n".join(ln for ln in linhas if ln).strip()


def encerra(texto: str) -> bool:
    return bool(ENCERRA.match(texto or ""))


@dataclass
class RespostaLida:
    acao_id: str
    de: str
    texto: str
    encerra: bool
    recebida_em: datetime
    msg_id: str


class LeitorDeCaixa:
    """Varre a caixa que assina as cobranças atrás de respostas.

    Recebe o cliente Graph já montado (o mesmo de `notificadores.graph`),
    para não duplicar autenticação — e para que trocar de caixa seja trocar
    uma variável de ambiente, não código.
    """

    def __init__(self, graph: Any, caixa: str, repo: Repositorio) -> None:
        self.graph = graph
        self.caixa = caixa
        self.repo = repo

    def mensagens(self, desde: datetime, limite: int = 200) -> list[dict[str, Any]]:
        corte = desde.astimezone().isoformat()
        caminho = (
            f"/users/{self.caixa}/messages"
            f"?$filter=receivedDateTime ge {corte}"
            f"&$select=id,subject,from,body,bodyPreview,receivedDateTime,"
            f"internetMessageId"
            f"&$orderby=receivedDateTime desc&$top={limite}"
        )
        return self.graph.get(caminho).get("value", [])

    def ler(self, dias: int = 30) -> list[RespostaLida]:
        """As respostas novas, já gravadas e com a ação atualizada."""
        conhecidas = {
            a.id[:8].lower(): a.id
            for a in self.repo.acoes_aguardando_resposta()
        }
        if not conhecidas:
            return []

        novas: list[RespostaLida] = []
        for msg in self.mensagens(datetime.now() - timedelta(days=dias)):
            msg_id = msg.get("internetMessageId") or msg.get("id")
            if not msg_id or self.repo.resposta_ja_lida(msg_id):
                continue

            marca = acao_do_assunto(msg.get("subject", ""))
            acao_id = conhecidas.get(marca) if marca else None
            if not acao_id:
                continue

            de = (
                (msg.get("from") or {}).get("emailAddress", {}).get("address", "")
            ).lower()
            if de == self.caixa.lower():
                # A própria cobrança, voltando na varredura da caixa.
                continue

            corpo = (msg.get("body") or {}).get("content") or msg.get(
                "bodyPreview", ""
            )
            texto = limpar(corpo)
            fecha = encerra(texto)
            quando = _data(msg.get("receivedDateTime"))

            self.repo.gravar_resposta_email(
                msg_id, acao_id, de, texto, fecha, quando
            )
            if fecha:
                self.repo.registrar_resposta(acao_id, texto, quando)

            novas.append(
                RespostaLida(acao_id, de, texto, fecha, quando, msg_id)
            )
        return novas


def _data(bruto: str | None) -> datetime:
    try:
        return datetime.fromisoformat(str(bruto).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return datetime.now()


# --------------------------------------------------------------- pelo GHL


class LeitorDoGHL:
    """Varre as conversas do GHL atrás de respostas às cobranças.

    A cobrança enviada pelo sender do GHL não passa por caixa de e-mail
    nenhuma do nosso lado: a resposta da pessoa chega como mensagem
    `inbound` dentro da conversa. É o mesmo problema do outro leitor, com
    outra fonte — e a mesma regra de encerramento, de propósito: quem é
    cobrado não deve precisar saber por qual cano a cobrança veio.
    """

    def __init__(self, ghl: Any, repo: Repositorio) -> None:
        self.ghl = ghl
        self.repo = repo

    def mensagens(self, desde: datetime, limite: int = 100) -> list[dict[str, Any]]:
        """Mensagens de e-mail da location desde a data. O GHL recusa
        `limit` abaixo de 10, então o piso é dele, não nosso."""
        return self.ghl.exportar_emails(desde, max(limite, 10))

    def ler(self, dias: int = 30) -> list[RespostaLida]:
        conhecidas = {
            a.id[:8].lower(): a.id
            for a in self.repo.acoes_aguardando_resposta()
        }
        if not conhecidas:
            return []

        novas: list[RespostaLida] = []
        for msg in self.mensagens(datetime.now() - timedelta(days=dias)):
            if msg.get("direction") != "inbound":
                # A própria cobrança. Na conversa ela aparece ao lado da
                # resposta, e sem este corte entraria como se fosse uma.
                continue

            msg_id = msg.get("id")
            if not msg_id or self.repo.resposta_ja_lida(msg_id):
                continue

            marca = acao_do_assunto(assunto_de(msg))
            acao_id = conhecidas.get(marca) if marca else None
            if not acao_id:
                continue

            # A listagem devolve a mensagem `inbound` quase vazia: sem
            # `body` e sem `from`, com o assunto escondido em `meta.email`.
            # O conteúdo da resposta só existe no detalhe do e-mail.
            corpo, de = msg.get("body"), _remetente(msg)
            if not corpo or not de:
                detalhe = self._detalhe(msg)
                corpo = corpo or detalhe.get("body") or ""
                de = de or _remetente(detalhe)

            texto = limpar(corpo)
            fecha = encerra(texto)
            quando = _data(msg.get("dateAdded"))

            self.repo.gravar_resposta_email(
                msg_id, acao_id, de, texto, fecha, quando
            )
            if fecha:
                self.repo.registrar_resposta(acao_id, texto, quando)

            novas.append(RespostaLida(acao_id, de, texto, fecha, quando, msg_id))
        return novas

    def _detalhe(self, msg: dict[str, Any]) -> dict[str, Any]:
        """Busca o e-mail completo de uma mensagem da listagem."""
        ids = ((msg.get("meta") or {}).get("email") or {}).get("messageIds") or []
        alvo = ids[0] if ids else msg.get("id")
        if not alvo:
            return {}
        try:
            return self.ghl.email_detalhe(alvo)
        except Exception:
            # Uma resposta que não abre não pode derrubar a leitura das
            # outras. Sem corpo ela não encerra nada, e é isso que se quer.
            return {}


def assunto_de(msg: dict[str, Any]) -> str:
    """O assunto, venha ele de onde vier.

    Nas mensagens `outbound` o GHL põe `subject` na raiz; nas `inbound`,
    só dentro de `meta.email`. Procurar apenas na raiz faz o leitor
    encontrar zero respostas — em silêncio, que é o pior jeito de falhar.
    """
    raiz = msg.get("subject")
    if raiz:
        return str(raiz)
    return str(((msg.get("meta") or {}).get("email") or {}).get("subject") or "")


def _remetente(msg: dict[str, Any]) -> str:
    """O endereço de quem respondeu, do jeito que o GHL devolve.

    Numa mensagem `inbound` o campo `from` vem como "Nome <email>" ou só o
    e-mail; o que interessa para o registro é o endereço.
    """
    bruto = str(msg.get("from") or "")
    if "<" in bruto and ">" in bruto:
        return bruto[bruto.index("<") + 1:bruto.index(">")].strip().lower()
    return bruto.strip().lower()
