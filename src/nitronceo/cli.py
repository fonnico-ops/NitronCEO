"""Linha de comando do NitronCEO.

    nitronceo rodar                 # mede tudo, abre ações, cobra pendentes
    nitronceo rodar --kpi fluxo_caixa_critico --dry-run
    nitronceo cobrar                # só a escada de cobrança
    nitronceo pendentes             # o que está em aberto e com quem
    nitronceo responder <id> "..."  # registra resposta e para a cobrança
    nitronceo validar               # confere matriz + queries sem tocar no ERP
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import RAIZ, carregar
from .motor import Motor, pulso
from .notificadores import Console, EmailOutlook, Teams
from .repositorio import Repositorio
from .sankhya import FonteArquivo, SankhyaREST, montar_sql


def _montar(args) -> tuple[Motor, Repositorio]:
    cfg = carregar()
    repo = Repositorio(args.banco)

    if args.dry_run:
        fonte = FonteArquivo(Path(args.fixtures))
        notificadores = {"teams": Console(), "email": Console()}
    else:
        fonte = SankhyaREST()
        notificadores = {"teams": Teams(), "email": EmailOutlook()}

    return Motor(cfg, fonte, repo, notificadores), repo


def cmd_rodar(args) -> int:
    motor, repo = _montar(args)
    try:
        rodada = motor.rodar(apenas=args.kpi, cobrar=not args.sem_cobranca)
        print(pulso(rodada, motor.cfg))
        return 1 if rodada.falhas else 0
    finally:
        repo.fechar()


def cmd_cobrar(args) -> int:
    motor, repo = _montar(args)
    try:
        cobrancas = motor.cobrar_pendentes()
        if not cobrancas:
            print("Nada a cobrar agora.")
            return 0
        for c in cobrancas:
            papel = motor.cfg.papel(c.destinatario)
            print(f"[{c.acao.id}] rodada {c.rodada} -> {papel.nome}: {c.motivo}")
        return 0
    finally:
        repo.fechar()


def cmd_pendentes(args) -> int:
    cfg = carregar()
    repo = Repositorio(args.banco)
    try:
        abertas = repo.acoes_em_aberto()
        if not abertas:
            print("Nenhuma ação em aberto.")
            return 0
        for acao in abertas:
            papel = cfg.papel(acao.dono)
            atraso = "VENCIDA" if acao.vencida else f"{acao.horas_restantes():.0f}h"
            print(
                f"[{acao.id}] {acao.nivel.value:9} {papel.nome:22} {atraso:>9}  "
                f"cobranças: {repo.cobrancas_de(acao.id)}  {acao.titulo}"
            )
        return 0
    finally:
        repo.fechar()


def cmd_responder(args) -> int:
    repo = Repositorio(args.banco)
    try:
        if repo.registrar_resposta(args.acao_id, args.texto):
            print(f"Resposta registrada. Cobrança de {args.acao_id} encerrada.")
            return 0
        print(f"Ação {args.acao_id} não encontrada.", file=sys.stderr)
        return 1
    finally:
        repo.fechar()


def cmd_validar(args) -> int:  # noqa: ARG001
    """Confere a matriz e monta todo o SQL sem executar nada."""
    cfg = carregar()
    problemas = 0

    for kpi in cfg.matriz["kpis"]:
        try:
            sql = montar_sql(RAIZ / kpi["sql"], cfg.params)
        except Exception as exc:
            print(f"ERRO  {kpi['id']}: {exc}")
            problemas += 1
            continue

        papel = cfg.papel(kpi["dono"])
        marca = "ativo " if kpi["modo"] == "ativo" else "sombra"
        print(
            f"ok    {kpi['id']:28} {marca}  {kpi['metrica']:24} "
            f"-> {papel.nome}  ({len(sql)} chars)"
        )

    ativos = sum(1 for k in cfg.matriz["kpis"] if k["modo"] == "ativo")
    print(
        f"\n{len(cfg.matriz['kpis'])} KPIs | {ativos} ativos | "
        f"{len(cfg.matriz['kpis']) - ativos} em sombra | {problemas} com erro"
    )
    return 1 if problemas else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="nitronceo", description=__doc__)
    p.add_argument("--banco", default="dados/nitronceo.db")
    sub = p.add_subparsers(dest="comando", required=True)

    def comum(sp):
        sp.add_argument("--dry-run", action="store_true",
                        help="usa fixtures e imprime no console em vez de enviar")
        sp.add_argument("--fixtures", default="tests/fixtures")
        return sp

    sp = comum(sub.add_parser("rodar", help="mede, julga, abre ações e cobra"))
    sp.add_argument("--kpi", action="append", help="limita a estes KPIs")
    sp.add_argument("--sem-cobranca", action="store_true")
    sp.set_defaults(func=cmd_rodar)

    comum(sub.add_parser("cobrar", help="só a escada de cobrança")).set_defaults(
        func=cmd_cobrar
    )

    sub.add_parser("pendentes", help="ações em aberto").set_defaults(func=cmd_pendentes)

    sp = sub.add_parser("responder", help="registra resposta de um dono")
    sp.add_argument("acao_id")
    sp.add_argument("texto")
    sp.set_defaults(func=cmd_responder)

    sub.add_parser("validar", help="confere matriz e SQL sem tocar no ERP").set_defaults(
        func=cmd_validar
    )

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
