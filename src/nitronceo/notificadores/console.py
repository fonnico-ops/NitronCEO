"""Saída para terminal. É o modo padrão do `--dry-run`.

Existe para que ninguém descubra que a matriz manda mensagem errada depois
que ela já chegou no Teams do time.
"""

from __future__ import annotations

import sys

from .base import Mensagem


class Console:
    nome = "console"

    def __init__(self, stream=sys.stdout) -> None:
        self.stream = stream

    def enviar(self, msg: Mensagem) -> bool:
        marca = "!! URGENTE" if msg.urgente else "--"
        alvo = ", ".join(msg.destinatarios) or "(canal de equipe)"
        if msg.canal_equipe:
            alvo += f" [{msg.canal_equipe['team']} / {msg.canal_equipe['canal']}]"

        print(f"\n{marca} {msg.assunto}", file=self.stream)
        print(f"   para: {alvo}", file=self.stream)
        for linha in msg.corpo_md.splitlines():
            print(f"   {linha}", file=self.stream)
        return True
