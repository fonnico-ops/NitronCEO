"""O relatório diário de acompanhamento.

Diferente da cobrança em três coisas, e a diferença é o ponto:

  - **não pede nada.** Quem recebe acompanha; não tem prazo, não entra na
    escada, não é cobrado se não responder.
  - **é o quadro inteiro**, não um indicador. Quem cobra precisa saber de
    um assunto; quem acompanha precisa saber de todos.
  - **encolhe num dia bom.** Num dia em que nada saiu da linha, isto tem
    quatro linhas. Relatório longo sobre dia normal ensina a não ler o
    relatório — e o dia em que importar, ninguém abre.

A ordem é a da urgência de quem lê, não a do sistema: primeiro o que
mudou, depois o que está vencido com alguém, depois o resto.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .acoes import Acao, formatar
from .avaliador import Nivel, Sinal
from .config import Config

ICONE = {
    Nivel.VERDE: "🟢",
    Nivel.AMARELO: "🟡",
    Nivel.VERMELHO: "🔴",
    Nivel.CRITICO: "🚨",
}

AREAS = {
    "comercial": "Comercial",
    "logistica": "Logística e Expedição",
    "producao": "Produção",
    "financeiro": "Financeiro",
    "compras": "Compras",
    "pcp": "PCP",
    "ecommerce": "E-commerce",
    "projetos": "Projetos e Moldes",
}


@dataclass
class Relatorio:
    assunto: str
    corpo_md: str


def _valor(sinal: Sinal) -> str:
    if sinal.erro:
        return "sem medição"
    prefixo = "R$ " if sinal.unidade == "reais" else ""
    sufixo = "%" if sinal.unidade == "percentual" else ""
    return f"{prefixo}{formatar(sinal.valor, sinal.unidade)}{sufixo}"


def montar(
    cfg: Config,
    sinais: list[Sinal],
    abertas: list[Acao],
    leitura: str | None = None,
    agora: datetime | None = None,
) -> Relatorio:
    agora = agora or datetime.now()
    por_kpi = {k["id"]: k for k in cfg.matriz["kpis"]}

    ativos = [s for s in sinais if s.modo == "ativo" and not s.erro]
    criticos = [s for s in ativos if s.nivel is Nivel.CRITICO]
    vermelhos = [s for s in ativos if s.nivel is Nivel.VERMELHO]
    fora = criticos + vermelhos
    vencidas = [a for a in abertas if a.vencida]
    escaladas = [a for a in abertas if a.escalonamentos > 0]
    falhas = [s for s in sinais if s.erro]

    linhas = [
        f"# Nitron — acompanhamento de {agora:%d/%m/%Y}",
        "",
    ]

    # ------------------------------------------------------------ o resumo
    # O atalho do dia bom exige que os indicadores tenham MEDIDO. Sem esta
    # condição, um dia em que a conexão com o ERP caísse e os 37 falhassem
    # sairia como "tudo no alvo" — o alarme que não toca porque a bateria
    # acabou, que é justamente o que este sistema não pode fazer.
    if not fora and not abertas and not falhas:
        linhas += [
            f"Nada fora da linha hoje. {len(ativos)} indicadores medidos, "
            "todos no alvo, nenhuma cobrança em aberto.",
            "",
            "_Sem detalhe porque não há o que detalhar._",
        ]
        return Relatorio(
            assunto=f"🟢 Nitron {agora:%d/%m} — tudo no alvo", corpo_md="\n".join(linhas)
        )

    resumo = (
        f"**{len(fora)} indicadores fora da linha** "
        f"({len(criticos)} críticos, {len(vermelhos)} vermelhos) · "
        f"**{len(abertas)} cobranças em aberto**"
    )
    if vencidas:
        resumo += f" · **{len(vencidas)} já vencidas**"
    linhas += [resumo, ""]

    # Medição quebrada em massa é o assunto do dia, não uma nota de rodapé:
    # sem número, nenhuma das outras linhas deste relatório vale.
    if len(falhas) > len(ativos):
        linhas += [
            f"⚠️ **{len(falhas)} dos {len(sinais)} indicadores não mediram "
            "hoje.** O quadro abaixo está incompleto — trate a apuração "
            "antes de tirar conclusão do que sobrou.",
            "",
        ]

    # ------------------------------------------------ o que precisa de você
    if vencidas or escaladas:
        linhas += ["## Passou do prazo", ""]
        for acao in sorted(vencidas or escaladas, key=lambda a: a.prazo):
            papel = cfg.papel(acao.dono)
            atraso = -acao.horas_restantes()
            marca = f"{acao.escalonamentos}ª escalada · " if acao.escalonamentos else ""
            linhas.append(
                f"- **{papel.quem}** — {acao.titulo}  \n"
                f"  {marca}venceu há {atraso:.0f}h "
                f"(prazo era {acao.prazo:%d/%m %H:%M})"
            )
        linhas.append("")

    # ---------------------------------------------------- a leitura cruzada
    if leitura:
        linhas += ["## Leitura", "", leitura.strip(), ""]

    # -------------------------------------------------------- área por área
    dono_de = {a.kpi_id: a for a in abertas}
    linhas += ["## Onde está fora da linha", ""]
    for chave, nome in AREAS.items():
        do_area = [s for s in fora if por_kpi[s.kpi_id]["area"] == chave]
        if not do_area:
            continue
        do_area.sort(key=lambda s: (s.nivel is not Nivel.CRITICO, s.titulo))
        quem = cfg.papel(por_kpi[do_area[0].kpi_id]["dono"]).quem
        linhas.append(f"**{nome}** — {quem}")
        for s in do_area:
            acao = dono_de.get(s.kpi_id)
            prazo = f" · até {acao.prazo:%d/%m %H:%M}" if acao else ""
            linhas.append(f"- {ICONE[s.nivel]} {s.titulo}: {_valor(s)}{prazo}")
        linhas.append("")

    # ------------------------------------------------------------ o rodapé
    verdes = [s for s in ativos if s.nivel is Nivel.VERDE]
    amarelos = [s for s in ativos if s.nivel is Nivel.AMARELO]
    sombra = [s for s in sinais if s.modo == "sombra"]

    linhas += ["---", ""]
    linhas.append(
        f"{len(verdes)} indicadores no alvo · {len(amarelos)} em atenção · "
        f"{len(sombra)} em sombra (medem, não cobram)"
    )
    if falhas:
        linhas.append(
            f"⚪ **{len(falhas)} não mediram hoje**: "
            + ", ".join(s.titulo for s in falhas[:5])
            + ". Indicador que não mede não é indicador verde."
        )
    linhas += [
        "",
        "_Acompanhamento, não cobrança: nada aqui espera resposta sua. "
        "Cada item já está com o dono e com prazo próprio._",
    ]

    if not fora and not abertas:
        # Só sobraram falhas de medição: o assunto tem que dizer isso, e
        # não fingir um dia tranquilo.
        return Relatorio(
            assunto=(
                f"⚪ Nitron {agora:%d/%m} — {len(falhas)} indicadores não "
                "mediram"
            ),
            corpo_md="\n".join(linhas),
        )

    icone = "🚨" if criticos else "🔴"
    return Relatorio(
        assunto=(
            f"{icone} Nitron {agora:%d/%m} — {len(fora)} fora da linha, "
            f"{len(abertas)} cobranças abertas"
        ),
        corpo_md="\n".join(linhas),
    )
