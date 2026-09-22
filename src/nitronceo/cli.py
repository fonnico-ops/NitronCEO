"""Linha de comando do NitronCEO.

    nitronceo rodar                 # mede tudo, abre ações, cobra pendentes
    nitronceo rodar --kpi fluxo_caixa_critico --dry-run
    nitronceo cobrar                # só a escada de cobrança
    nitronceo pendentes             # o que está em aberto e com quem
    nitronceo responder <id> "..."  # registra resposta e para a cobrança
    nitronceo validar               # confere matriz + queries sem tocar no ERP
    nitronceo dashboard -o x.html   # gera o painel do pipeline
    nitronceo importar respostas.json   # traz as respostas do painel de volta
    nitronceo renato                # leitura cruzada da rodada, para o CEO
    nitronceo renato --dossie       # só o material, sem chamar o modelo
    nitronceo rodar --com-renato    # ele escreve o texto de cada cobrança
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
from pathlib import Path

from .analista import Renato, SemCredencial, montar_dossie
from .config import RAIZ, carregar
from .dashboard import gerar
from .motor import Motor, pulso
from .notificadores import Console, EmailOutlook, GoHighLevel, Teams
from .repositorio import Repositorio
from .sankhya import FonteArquivo, SankhyaREST, montar_sql


CANAIS = ("teams", "email", "ghl")


def _canais_pedidos(args) -> tuple[str, ...]:
    """Quais canais ficam no ar nesta execução.

    `--canais email` é o modo de produção mais curto: precisa de uma única
    permissão no Entra ID (`Mail.Send`) em vez das quatro que o Teams exige.
    """
    bruto = getattr(args, "canais", None)
    if not bruto:
        return CANAIS
    pedidos = tuple(c.strip().lower() for c in bruto.split(",") if c.strip())
    desconhecidos = [c for c in pedidos if c not in CANAIS]
    if desconhecidos:
        raise SystemExit(
            f"Canal desconhecido: {', '.join(desconhecidos)}. "
            f"Disponíveis: {', '.join(CANAIS)}."
        )
    return pedidos


def _montar(args) -> tuple[Motor, Repositorio]:
    cfg = carregar()
    repo = Repositorio(args.banco)

    escolhidos = _canais_pedidos(args)

    if args.dry_run:
        fonte = FonteArquivo(Path(args.fixtures))
        notificadores = {"teams": Console(), "email": Console(), "ghl": Console()}
    else:
        fonte = SankhyaREST()
        notificadores = {}
        if "teams" in escolhidos:
            notificadores["teams"] = Teams()
        if "email" in escolhidos:
            notificadores["email"] = EmailOutlook()
        # O GHL só entra se estiver configurado. Ausente, os outros canais
        # continuam entregando — ele é canal a mais, não substituto.
        if "ghl" in escolhidos and os.getenv("GHL_TOKEN") and os.getenv(
            "GHL_LOCATION_ID"
        ):
            notificadores["ghl"] = GoHighLevel()

    if escolhidos != CANAIS:
        notificadores = {c: n for c, n in notificadores.items() if c in escolhidos}

    redator = None
    if getattr(args, "com_renato", False):
        redator = Renato(cfg)

    # Sem Teams, o fallback é o e-mail: a matriz foi escrita supondo os
    # dois, e 35 dos 37 KPIs mandam o nível amarelo só pelo Teams.
    fallback = "email" if "email" in notificadores else None

    motor = Motor(cfg, fonte, repo, notificadores, redator=redator, fallback=fallback)
    return motor, repo


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
            print(f"[{c.acao.id}] rodada {c.rodada} -> {papel.quem}: {c.motivo}")
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
                f"[{acao.id}] {acao.nivel.value:9} {papel.quem:26} {atraso:>9}  "
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


def cmd_dashboard(args) -> int:
    """Mede, monta as ações e escreve o painel — sem notificar ninguém."""
    motor, repo = _montar(args)
    # O painel só lê: nada de mensagem para ninguém ao gerar o HTML.
    motor.notificadores = {}
    motor.redator = None  # aqui o Renato analisa; redigir é da rodada de cobrança
    try:
        rodada = motor.rodar(apenas=None, cobrar=False)
        abertas = repo.acoes_em_aberto()
        cobrancas, escaladas = repo.totais_de_cobranca()

        leitura = None
        if getattr(args, "com_renato", False):
            historico = {
                s.kpi_id: repo.dias_consecutivos_ruins(s.kpi_id)
                for s in rodada.sinais
            }
            try:
                leitura = Renato(motor.cfg).leitura(rodada.sinais, abertas, historico)
            except (SemCredencial, RuntimeError) as exc:
                # Painel sem a leitura ainda é o painel. Não vale derrubar a
                # geração por causa da camada opinativa.
                print(f"Sem a leitura do Renato: {exc}", file=sys.stderr)

        html = gerar(
            motor.cfg, rodada.sinais, abertas, cobrancas, escaladas, leitura
        )
        destino = Path(args.saida)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(html, encoding="utf-8")
        print(f"{destino} — {len(rodada.sinais)} KPIs, {len(abertas)} cobranças abertas")
        return 1 if rodada.falhas else 0
    finally:
        repo.fechar()


def cmd_importar(args) -> int:
    """Traz para o banco local as respostas escritas no painel publicado.

    O painel grava cada resposta na base do artifact. Esse arquivo é o que a
    leitura dessa base devolve — uma lista de objetos com `acaoId`, `texto`,
    `criadoEm` e `encerra`. Só as marcadas com `encerra` param a escada de
    cobrança; as demais são recado, não conclusão.
    """
    import json
    from datetime import datetime

    repo = Repositorio(args.banco)
    try:
        bruto = json.loads(Path(args.arquivo).read_text(encoding="utf-8"))
        respostas = bruto.get("documents", bruto) if isinstance(bruto, dict) else bruto

        encerradas = ignoradas = desconhecidas = 0
        for r in respostas:
            corpo = r.get("data", r)
            acao_id = corpo.get("acaoId")
            if not acao_id:
                continue
            if not corpo.get("encerra"):
                ignoradas += 1
                continue
            quando = None
            try:
                quando = datetime.fromisoformat(
                    str(corpo.get("criadoEm", "")).replace("Z", "+00:00")
                )
            except ValueError:
                pass
            if repo.registrar_resposta(acao_id, corpo.get("texto", ""), quando):
                encerradas += 1
                print(f"[{acao_id[:6]}] encerrada")
            else:
                desconhecidas += 1

        print(
            f"\n{encerradas} cobranças encerradas · {ignoradas} respostas sem "
            f"encerramento · {desconhecidas} para ações que não existem aqui"
        )
        return 0
    finally:
        repo.fechar()


def cmd_renato(args) -> int:
    """A leitura cruzada da rodada — o que a matriz sozinha não enxerga.

    Mede tudo sem notificar ninguém, monta o dossiê e pede ao Renato a
    leitura. Com `--dossie`, para no material e não chama o modelo: útil
    para conferir o que ele estaria vendo antes de gastar uma chamada.
    """
    motor, repo = _montar(args)
    motor.notificadores = {}
    motor.redator = None  # aqui ele analisa; escrever cobrança é outro comando
    try:
        rodada = motor.rodar(apenas=args.kpi, cobrar=False)
        abertas = repo.acoes_em_aberto()
        historico = {
            s.kpi_id: repo.dias_consecutivos_ruins(s.kpi_id) for s in rodada.sinais
        }

        if args.dossie:
            print(montar_dossie(rodada.sinais, abertas, motor.cfg, historico))
            return 0

        try:
            leitura = Renato(motor.cfg).leitura(rodada.sinais, abertas, historico)
        except SemCredencial as exc:
            print(f"Renato não rodou: {exc}", file=sys.stderr)
            print("\nO dossiê que ele teria lido:\n", file=sys.stderr)
            print(montar_dossie(rodada.sinais, abertas, motor.cfg, historico))
            return 1

        print(leitura.texto)
        print(
            f"\n_{leitura.modelo} · {leitura.gerada_em:%d/%m %H:%M} · "
            f"{leitura.custo_em_cache} · {leitura.tokens_saida} de saída._"
        )
        if rodada.falhas:
            print(
                f"\n⚠️ {len(rodada.falhas)} KPI(s) não mediram; a leitura "
                "acima foi feita sem eles.",
                file=sys.stderr,
            )
        return 0
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
            f"-> {papel.quem}  ({len(sql)} chars)"
        )

    ativos = sum(1 for k in cfg.matriz["kpis"] if k["modo"] == "ativo")
    print(
        f"\n{len(cfg.matriz['kpis'])} KPIs | {ativos} ativos | "
        f"{len(cfg.matriz['kpis']) - ativos} em sombra | {problemas} com erro"
    )
    return 1 if problemas else 0


def main(argv: list[str] | None = None) -> int:
    # `nitronceo pendentes | head` fecha o pipe no meio da escrita; sem isto o
    # usuário vê um traceback em vez do resultado que ele pediu.
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    p = argparse.ArgumentParser(prog="nitronceo", description=__doc__)
    p.add_argument("--banco", default="dados/nitronceo.db")
    sub = p.add_subparsers(dest="comando", required=True)

    def comum(sp):
        sp.add_argument("--dry-run", action="store_true",
                        help="usa fixtures e imprime no console em vez de enviar")
        sp.add_argument("--fixtures", default="tests/fixtures")
        sp.add_argument(
            "--canais",
            metavar="LISTA",
            help="canais no ar, separados por vírgula (teams, email, ghl). "
                 "Padrão: todos os configurados. Ex.: --canais email",
        )
        return sp

    sp = comum(sub.add_parser("rodar", help="mede, julga, abre ações e cobra"))
    sp.add_argument("--kpi", action="append", help="limita a estes KPIs")
    sp.add_argument("--sem-cobranca", action="store_true")
    sp.add_argument(
        "--com-renato",
        action="store_true",
        help="o Renato escreve o texto de cada cobrança (cai no padrão se falhar)",
    )
    sp.set_defaults(func=cmd_rodar)

    sp = comum(sub.add_parser("renato", help="leitura cruzada da rodada, para o CEO"))
    sp.add_argument("--kpi", action="append", help="limita a estes KPIs")
    sp.add_argument(
        "--dossie",
        action="store_true",
        help="imprime só o material da análise, sem chamar o modelo",
    )
    sp.set_defaults(func=cmd_renato)

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

    sp = sub.add_parser("importar", help="traz as respostas do painel publicado")
    sp.add_argument("arquivo", help="JSON exportado da base do artifact")
    sp.set_defaults(func=cmd_importar)

    sp = comum(sub.add_parser("dashboard", help="gera o painel do pipeline"))
    sp.add_argument("-o", "--saida", default="dashboard.html")
    sp.add_argument(
        "--com-renato",
        action="store_true",
        help="inclui a leitura cruzada do Renato no topo do painel",
    )
    sp.set_defaults(func=cmd_dashboard)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
