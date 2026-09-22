from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Mensagem:
    assunto: str
    corpo_md: str
    destinatarios: list[str]          # e-mails / UPNs
    urgente: bool = False
    canal_equipe: dict[str, str] | None = None   # {"team": ..., "canal": ...}
    rotulos: list[str] = field(default_factory=list)


class Notificador(Protocol):
    nome: str

    def enviar(self, msg: Mensagem) -> bool: ...
