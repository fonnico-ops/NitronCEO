"""Uma mensagem por gestor, com tudo o que é dele naquele dia.

A matriz gera uma ação por KPI. Entregá-las como uma mensagem cada faz
sentido no papel e falha na caixa de entrada: na primeira rodada real, a
produção recebeu cinco e-mails no mesmo minuto. Cinco cobranças
simultâneas não são cinco cobranças — são ruído, e ruído ensina a filtrar
o remetente.

O lote junta tudo de um dono numa mensagem só, ordenada por gravidade e
prazo. O que **não** muda: cada cobrança mantém o próprio token, o próprio
prazo e a própria escada. O agrupamento é de entrega, não de
responsabilidade.

Como a resposta volta:

  - responder o lote registra retorno em TODAS as cobranças dele e segura
    os lembretes de todas — a pessoa se manifestou, e o sistema não pode
    cobrá-la de novo no dia seguinte por causa de um detalhe de formato;
  - **RESOLVIDO [NTR-xxxxxxxx]** encerra aquela cobrança;
  - **RESOLVIDO** sozinho só encerra quando o lote tem uma cobrança só.
    Com várias, encerrar tudo por uma palavra seria aceitar que "resolvido"
    vale para cinco assuntos que a pessoa talvez nem tenha lido.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime

from .acoes import Acao
from .avaliador import Nivel
from .config import Config, Papel
from .numeros import e_base, frase, unidade_de, vestir_lista

ICONE = {
    Nivel.VERDE: "🟢",
    Nivel.AMARELO: "🟡",
    Nivel.VERMELHO: "🔴",
    Nivel.CRITICO: "🚨",
}


def marcar_lote(acoes: list[Acao]) -> str:
    """Token do lote: estável para as mesmas ações, no mesmo dia.

    Derivado dos ids das ações para que reenviar o mesmo lote produza o
    mesmo token — e uma resposta antiga continue casando.
    """
    semente = "|".join(sorted(a.id for a in acoes))
    return hashlib.sha1(semente.encode()).hexdigest()[:8]


@dataclass
class Lote:
    papel: Papel
    acoes: list[Acao]
    token: str
    assunto: str
    corpo_md: str
    contatos_ghl: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)


def _ordem(acao: Acao) -> tuple:
    peso = {Nivel.CRITICO: 0, Nivel.VERMELHO: 1, Nivel.AMARELO: 2, Nivel.VERDE: 3}
    return (peso[acao.nivel], acao.prazo)


def montar(
    papel: Papel,
    acoes: list[Acao],
    cfg: Config,
    painel: str,
    agora: datetime | None = None,
) -> Lote:
    agora = agora or datetime.now()
    acoes = sorted(acoes, key=_ordem)
    token = marcar_lote(acoes)
    por_kpi = {k["id"]: k for k in cfg.matriz["kpis"]}

    criticos = sum(1 for a in acoes if a.nivel is Nivel.CRITICO)
    primeiro_nome = papel.pessoas[0].nome.split()[0] if papel.pessoas else papel.nome

    linhas = [
        f"{primeiro_nome}, {_abertura(len(acoes), criticos)}",
        "",
        "Cada ponto abaixo tem prazo próprio. Responda este e-mail: um "
        "retorno, mesmo parcial, vale para todos e segura os lembretes.",
        "",
    ]

    for n, acao in enumerate(acoes, 1):
        kpi = por_kpi[acao.kpi_id]
        linhas += [
            "---",
            "",
            f"## {n}. {ICONE[acao.nivel]} {acao.titulo}",
            "",
            f"_{kpi['pergunta']}_",
            "",
        ]

        resumo = _resumo(acao, kpi)
        if resumo:
            linhas += [resumo, ""]

        for titulo_lista, itens in _detalhe(acao):
            linhas.append(f"**{titulo_lista}**")
            linhas += [f"- {i}" for i in itens]
            linhas.append("")

        linhas.append("**O que preciso de você:**")
        linhas += [f"- {p}" for p in acao.passos]
        linhas += [
            "",
            f"Prazo: **{acao.prazo:%d/%m às %H:%M}** "
            f"({acao.horas_restantes():.0f}h) · para encerrar este ponto, "
            f"escreva **RESOLVIDO [NTR-{acao.id[:8]}]**",
            "",
        ]

    linhas += [
        "---",
        "",
        f"Detalhe de cada ponto e histórico no painel: {painel}",
        "",
        f"_Apurado em {agora:%d/%m/%Y %H:%M}. Próxima rodada em 2 dias._",
    ]

    plural = "pontos" if len(acoes) > 1 else "ponto"
    icone = "🚨" if criticos else "🔴"
    return Lote(
        papel=papel,
        acoes=acoes,
        token=token,
        assunto=(
            f"{icone} [NTR-L-{token}] {papel.nome}: {len(acoes)} {plural} "
            f"fora da linha"
        ),
        corpo_md="\n".join(linhas),
        contatos_ghl=papel.contatos_ghl,
        emails=papel.emails,
    )


# Quanto um número pesa na decisão de quem lê. Dinheiro primeiro: é o que
# faz um gerente parar o que está fazendo. Contagem depois, porque dá o
# tamanho do problema. Percentual e média por último — explicam, não
# convocam.
PESO_UNIDADE = {"reais": 0, "contagem": 1, "dias": 2, "horas": 2,
                "minutos": 2, "percentual": 3}

# Quantos números cabem antes de a linha virar planilha.
MAX_NUMEROS = 4


def _relevancia(par: tuple[str, float]) -> tuple[int, int, float]:
    coluna, valor = par
    return (int(e_base(coluna)),
            PESO_UNIDADE.get(unidade_de(coluna), 4),
            -abs(valor or 0))


def _resumo(acao: Acao, kpi: dict) -> str:
    """Os números da cobrança numa linha, do mais decisivo ao menos.

    A métrica que disparou o nível já está no título — repeti-la aqui só
    gastaria a primeira linha, que é a única que muita gente lê.
    """
    if kpi["acao"].get("resumo"):
        return _preencher(kpi["acao"]["resumo"], acao.contexto)

    numeros = [
        (k, v) for k, v in acao.contexto.items()
        if k not in (kpi["metrica"], "LISTA", "LISTA_CAUDA", "ROTULO")
        and isinstance(v, (int, float)) and not isinstance(v, bool)
    ]
    if not numeros:
        return ""

    numeros.sort(key=_relevancia)
    ditos = [frase(k, v) for k, v in numeros[:MAX_NUMEROS]]
    return f"**{ditos[0]}**" + ("".join(f" · {d}" for d in ditos[1:]))


def _preencher(molde: str, contexto: dict) -> str:
    """`{VLR_TRAVADO}` vira `R$ 505.694,43` — sem o rótulo, que o molde já dá."""
    from .numeros import formatar_numero
    saida = molde
    for chave, valor in contexto.items():
        marca = "{" + chave + "}"
        if marca in saida:
            saida = saida.replace(marca, formatar_numero(valor, unidade_de(chave)))
    return saida


def _detalhe(acao: Acao) -> list[tuple[str, list[str]]]:
    """As listas nomeadas do SQL viram bullets.

    É a parte que mais pesa para quem responde: `INJETORA 31: 110,3h em 3
    paradas` é acionável, `69 paradas` não é. O LISTAGG dos SQLs separa os
    itens por ` · `; quando vier como frase única, vai como frase única —
    quebrar por vírgula partiria `(35d, Atraso)` no meio.
    """
    blocos = []
    for chave, titulo in (("LISTA", "Onde está concentrado:"),
                          ("LISTA_CAUDA", "Os itens da cauda:")):
        bruto = acao.contexto.get(chave)
        if not isinstance(bruto, str) or not bruto.strip():
            continue
        texto = vestir_lista(bruto.strip())
        itens = [x.strip() for x in texto.split(" · ") if x.strip()]
        blocos.append((titulo, itens[:8]))
    return blocos


def _abertura(quantos: int, criticos: int) -> str:
    if quantos == 1:
        return "um ponto da sua área saiu da linha."
    if criticos:
        return (
            f"{quantos} pontos da sua área saíram da linha, "
            f"{criticos} deles críticos."
        )
    return f"{quantos} pontos da sua área saíram da linha."


def agrupar(
    acoes: list[Acao], cfg: Config, painel: str, agora: datetime | None = None
) -> list[Lote]:
    """Um lote por dono, do mais carregado para o menos."""
    por_dono: dict[str, list[Acao]] = {}
    for acao in acoes:
        por_dono.setdefault(acao.dono, []).append(acao)

    lotes = [
        montar(cfg.papel(dono), suas, cfg, painel, agora)
        for dono, suas in por_dono.items()
    ]
    return sorted(lotes, key=lambda x: -len(x.acoes))
