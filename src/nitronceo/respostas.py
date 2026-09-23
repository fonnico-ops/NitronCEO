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
