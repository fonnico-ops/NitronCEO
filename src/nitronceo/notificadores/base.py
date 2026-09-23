from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Mensagem:
    assunto: str
    corpo_md: str
    destinatarios: list[str]          # e-mails
    urgente: bool = False
    canal_equipe: dict[str, str] | None = None   # {"team": ..., "canal": ...}
    rotulos: list[str] = field(default_factory=list)
    # UPNs do Microsoft 365. Quase sempre iguais aos e-mails; declarados à
    # parte porque quando divergem o Graph devolve 404 e ninguém é avisado.
    upns: list[str] = field(default_factory=list)

    @property
    def para_teams(self) -> list[str]:
        return self.upns or self.destinatarios


class Notificador(Protocol):
    nome: str

    def enviar(self, msg: Mensagem) -> bool: ...
