"""Traduz a linha do SQL para a língua de quem vai responder.

O SQL devolve `VLR_TRAVADO: 505694.43`. Isso é nome de coluna, não é
informação: quem abre o e-mail às 8h da manhã precisa ler
`R$ 505.694,43 travado` e decidir. Na primeira rodada agrupada de
24/09/2026 as cobranças saíram com o nome da coluna e o float cru, e o
retorno foi zero — não porque o número estivesse errado, mas porque
ninguém lê planilha em e-mail.

Duas funções, as duas puramente derivadas do NOME da coluna:

  `unidade_de`   VLR_/META_/SALDO_ são reais, PCT_ é percentual, HORAS_ é
                 hora, DIAS_ é dia. A convenção vale nos 37 SQLs — foi
                 conferida coluna a coluna nas 182 que as fixtures
                 produzem;
  `rotulo_de`    quebra o nome em palavras e traduz token a token, com
                 `ROTULOS` cobrindo o que a tradução mecânica erraria.

Nada aqui inventa número: só muda como ele aparece.
"""

from __future__ import annotations

import re

# Colunas cujo rótulo mecânico sairia errado, ambíguo ou feio. O valor é o
# rótulo, ou (rótulo, unidade) quando o NOME da coluna mente sobre o tipo do
# número — `QUEDA_ACIMA_50PCT` termina em PCT mas conta produtos, e exibi-lo
# como "70,0%" seria inventar um percentual que ninguém mediu.
ROTULOS: dict[str, str | tuple[str, str]] = {
    "AINDA_COMPRANDO": "devedores que seguem comprando",
    "COB_ABAIXO_ALERTA": "itens com cobertura abaixo do alerta",
    "COB_MENOR_7D": "itens com menos de 7 dias de cobertura",
    "COM_EQPTO_PARADO": "com equipamento parado",
    "COM_VENDA_180D": "com venda nos últimos 180 dias",
    "DIAS_MAX": "o mais antigo",
    "DIAS_MEDIO": "em média",
    "IDADE_MAX": "o mais antigo",
    "IDADE_MEDIANA": "de idade mediana",
    "LISTA": "detalhe",
    "MTD": "no mês até hoje",
    "OS_JANELA": "ordens de serviço na janela",
    "PARADOS_MAIS_7D": "parados há mais de 7 dias",
    "PARADOS_MAIS_30D": "parados há mais de 30 dias",
    "PCT_PROJECAO_META": "da meta, na projeção",
    "PCT_SOBRE_FATURAMENTO": "do faturamento",
    "PIOR_ATRASO": "pior atraso",
    "QTD_MTD": "pedidos no mês até hoje",
    "QUEDA_ACIMA_50PCT": ("produtos caíram mais de 50%", "contagem"),
    "ABERTAS_ACIMA_180D": "abertas há mais de 180 dias",
    "ACIMA_PADRAO": "acima do padrão",
    "APONTAMENTO_SUSPEITO": "apontamentos suspeitos",
    "DEVEDORES_ACIMA_PISO": "devedores acima do piso",
    "DIAS_DE_META": ("dias de meta na carteira", "contagem"),
    "ENDERECOS_NEGATIVOS": "endereços com saldo negativo",
    "FECHADAS_ACIMA_30D": "fechadas em mais de 30 dias",
    "GAP_EMISSAO": "de diferença na emissão",
    "ITENS_SALDO_PARCIAL": "itens com saldo parcial",
    "MAQUINAS": "máquinas",
    "MAQUINAS_ACIMA_140": "máquinas acima de 140% do ciclo padrão",
    "MAQUINAS_AFETADAS": "máquinas afetadas",
    "MEDIANA_FECHAMENTO": ("de mediana para fechar", "dias"),
    "MEDIA_7D": "de média em 7 dias",
    "MEDIA_MES_6M": "de média mensal em 6 meses",
    "META_DIA": "de meta por dia",
    "META_MES": "de meta no mês",
    "NOTAS_JANELA": "notas na janela",
    "PCT_ACIMA_PADRAO": "acima do padrão",
    "PCT_CANHOTO_PROPRIA": "de canhoto na frota própria",
    "PCT_CANHOTO_TRANSP": "de canhoto na transportadora",
    "PCT_VS_MEDIA": "da média",
    "PCT_VS_PADRAO": "do padrão",
    "PEDIDOS_MTD": "pedidos no mês até hoje",
    "PROJECAO_FECHAMENTO": "de projeção de fechamento",
    "QTD_COM_DEVOLUCAO_VINCULADA": "com devolução vinculada",
    "QTD_TOTAL": "no total",
    "REALIZADO_MTD": "realizado no mês até hoje",
    "REFEICAO_LONGA": "refeições longas",
    "RITMO_DIA_UTIL": "de ritmo por dia útil",
    "SALDO_NAO_POSITIVO": ("itens sem saldo positivo", "contagem"),
    "SETUPS_VALIDOS": "setups válidos",
    "SKUS_VENDIDOS": "SKUs vendidos",
    "SUSPENSOS_TOTAL": "suspensos no total",
    "TICKET_MEDIO_HIST": "de ticket médio histórico",
    "TICKET_MTD": "de ticket no mês até hoje",
    "TITULOS": "títulos",
    "TITULOS_FRETE": "títulos de frete",
    "TITULOS_SEM_NOTA": "títulos sem nota",
    "VLR_AGENDADO_TOTAL": "agendado no total",
    "VLR_CAUDA": "na cauda",
    "VLR_DIA_ATUAL": "por dia, hoje",
    "VLR_DIA_HIST": "por dia, no histórico",
    "VLR_LIQUIDAVEL": "liquidável",
    "VLR_NA_CARTEIRA": "na carteira",
    "VLR_TRIMESTRE": "no trimestre",
    "ACIMA_25PCT": ("acima de 25% do padrão", "contagem"),
    "ACIMA_50PCT": ("acima de 50% do padrão", "contagem"),
    "ROTULO": "referência",
    "SKUS_ATE_2_UNID": "SKUs com até 2 unidades vendidas",
    "SKUS_ATE_80PCT": ("SKUs fazem 80% da venda", "contagem"),
    "MEDIANA_MIN": "de mediana",
    "MEDIA_MIN": "em média",
    "PADRAO_MIN": "de padrão",
    "HORAS_PARADAS": "paradas",
    "HORAS_PARADAS_TOTAL": "paradas no total",
    "HORAS_PERDIDAS": "perdidas",
    "HORAS_SEM_MOTIVO": "sem motivo apontado",
    "PARADAS_60MIN": ("paradas acima de 60 min", "contagem"),
    "SALDO_D0_D7": "de saldo de hoje a D+7",
    "SALDO_D8_D30": "de saldo de D+8 a D+30",
    "SALDO_D0_D30": "de saldo nos próximos 30 dias",
    "PAGAR_D0_D7": "a pagar de hoje a D+7",
    "PAGAR_D8_D30": "a pagar de D+8 a D+30",
    "RECEBER_D0_D7": "a receber de hoje a D+7",
    "RECEBER_D8_D30": "a receber de D+8 a D+30",
    "VLR_ACIMA_90D": "vencido há mais de 90 dias",
    "VLR_ATE_30D": "vencido há até 30 dias",
    "VLR_VENDIDO_180D": "vendidos em 180 dias",
    "FECHADAS_365D": "fechadas em 12 meses",
    "VLR_DIA_MEDIA_90D": "por dia, média de 90 dias",
    "PCT_VS_MEDIA_90D": "da média de 90 dias",
    "SKUS_CAUDA": "SKUs de cauda",
    "UTEIS_DECORRIDOS": "dias úteis decorridos",
    "UTEIS_TOTAIS": "dias úteis no mês",
    "VLR_12M": "em 12 meses",
    "VLR_MTD": "no mês até hoje",
    "VLR_TRIM_ANO_PASSADO": "no mesmo trimestre do ano passado",
}

# Tradução token a token do que sobra. A ordem não importa: cada palavra
# do nome é trocada isoladamente.
PALAVRAS = {
    "VLR": "", "QTD": "", "PCT": "", "NUM": "",
    "MEDIA": "média", "MEDIO": "médio", "MEDIANA": "mediana",
    "MAX": "máximo", "MIN": "minutos", "TOTAL": "total",
    "DIAS": "dias", "HORAS": "horas", "MES": "no mês", "MESES": "meses",
    "ATE": "até", "SEM": "sem", "COM": "com", "ACIMA": "acima de",
    "MAIS": "mais de", "VS": "contra", "NAO": "não",
    "EQPTO": "equipamento", "OS": "ordens de serviço",
    "PROD": "produto", "PRODUTOS": "produtos", "PEDIDOS": "pedidos",
    "CARTEIRA": "na carteira", "PADRAO": "padrão", "MEDIO12M": "média 12m",
}

SUFIXO_DIA = ("D0", "D7", "D30", "D8", "180D", "365D", "90D", "12M", "180", "60MIN")


def unidade_de(coluna: str) -> str:
    """Que tipo de número é esse, pelo nome da coluna."""
    c = coluna.upper()
    forcada = ROTULOS.get(c)
    if isinstance(forcada, tuple):
        return forcada[1]
    if c.startswith(("VLR_", "META_", "SALDO_", "PAGAR_", "RECEBER_",
                     "DESPESA_", "FATURAMENTO_", "EMITIDO_", "GAP_",
                     "FRETE_PAGO", "PROJECAO_", "REALIZADO_", "RITMO_",
                     "EXCESSO_", "TICKET_")) or c in {"VLR", "MEDIA_MES_6M"}:
        return "reais"
    if c.startswith("PCT") or c.endswith("PCT") or "PCT_" in c:
        return "percentual"
    if c.startswith("HORAS") or c.endswith("_H"):
        return "horas"
    if c.endswith("_MIN") or c.startswith("MEDIANA_MIN") or c in {"PADRAO_MIN"}:
        return "minutos"
    if c.startswith("DIAS") or c.startswith("IDADE") or c == "PIOR_ATRASO":
        return "dias"
    return "contagem"


def formatar_numero(valor: float | int | None, unidade: str) -> str:
    """O número já vestido: R$, %, h, min, d — pronto para a frase."""
    if valor is None:
        return "—"
    if isinstance(valor, str):
        return valor

    def br(v: float, casas: int) -> str:
        return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")

    if unidade == "reais":
        return f"R$ {br(valor, 2)}"
    if unidade == "percentual":
        return f"{br(valor, 1)}%"
    if unidade == "horas":
        return f"{br(valor, 1)}h"
    if unidade == "minutos":
        return f"{br(valor, 0)} min"
    if unidade == "dias":
        # Mediana de 0,8 dia não é "1 dias": arredondar para cima aqui
        # transformaria "fecha no mesmo dia" em "leva um dia".
        casas = 1 if 0 < abs(valor) < 10 and valor != int(valor) else 0
        if abs(valor) == 1:
            return "1 dia"
        return f"{br(valor, casas)} dias"
    return br(valor, 0)


def rotulo_de(coluna: str) -> str:
    """O nome da coluna em português de gente."""
    c = coluna.upper()
    pronto = ROTULOS.get(c)
    if pronto is not None:
        return pronto[0] if isinstance(pronto, tuple) else pronto

    # A unidade já aparece no número: repeti-la no rótulo daria
    # "773,4h horas paradas".
    muda = {"horas": {"HORAS"}, "minutos": {"MIN"},
            "dias": {"DIAS"}, "percentual": {"PCT"}}.get(unidade_de(c), set())

    partes = []
    for palavra in c.split("_"):
        if palavra in muda:
            continue
        if palavra in SUFIXO_DIA:
            partes.append(_periodo(palavra))
        elif palavra in PALAVRAS:
            if PALAVRAS[palavra]:
                partes.append(PALAVRAS[palavra])
        else:
            partes.append(palavra.lower())
    return " ".join(p for p in partes if p).strip()


def _periodo(palavra: str) -> str:
    if palavra.startswith("D") and palavra[1:].isdigit():
        return f"em D+{palavra[1:]}"
    if palavra.endswith("D") and palavra[:-1].isdigit():
        return f"em {palavra[:-1]} dias"
    if palavra.endswith("M") and palavra[:-1].isdigit():
        return f"em {palavra[:-1]} meses"
    return palavra.lower()


def frase(coluna: str, valor: float | int | None) -> str:
    """`VLR_TRAVADO`, 505694.43 -> `R$ 505.694,43 travado`."""
    numero = formatar_numero(valor, unidade_de(coluna))
    rotulo = rotulo_de(coluna)
    return f"{numero} {rotulo}".strip() if rotulo else numero


# Colunas que são a BASE de comparação, não o problema. `FECHADAS_365D`
# num ponto sobre OS abertas é o denominador: abrir a frase com ela conta
# a boa notícia numa cobrança. Vão para o fim da linha, nunca para a
# primeira posição.
BASES = {
    "APONTAMENTOS", "FECHADAS_365D", "FECHADAS_ONTEM", "ITENS_CARTEIRA",
    "MONITORADAS", "MAQUINAS", "META_DIA", "META_MES", "NOTAS_EMITIDAS",
    "ORDENS_ONTEM", "OS_JANELA", "PEDIDOS_CARTEIRA", "PEDIDOS_MTD",
    "PRODUTOS_COM_GIRO", "QTD_MTD", "QTD_TOTAL", "REPRESENTANTES",
    "SETUPS", "SETUPS_VALIDOS", "SKUS_VENDIDOS", "SUSPENSOS_TOTAL",
    "TITULOS", "UTEIS_DECORRIDOS", "UTEIS_TOTAIS", "VLR_CARTEIRA",
    "VLR_FATURADO", "VLR_TOTAL", "AGENDAMENTOS", "DIAS_AGENDADOS",
}


def e_base(coluna: str) -> bool:
    """Esse número descreve o problema, ou o tamanho do universo?"""
    return coluna.upper() in BASES


_REAIS = re.compile(r"R\$ ?(\d{4,})(?![\d.,])")
_UNIDADES = re.compile(r"(?<![\d.,])(\d{4,}) un\b")


def _milhar(n: str) -> str:
    return f"{int(n):,}".replace(",", ".")


def vestir_lista(texto: str) -> str:
    """Põe separador de milhar nos números que o LISTAGG cospe crus.

    O Oracle devolve `R$ 285623` porque ROUND não formata. Ninguém lê
    285623 como duzentos e oitenta e cinco mil na primeira passada — e a
    primeira passada é a única que a maioria dá.
    """
    texto = _REAIS.sub(lambda m: f"R$ {_milhar(m.group(1))}", texto)
    return _UNIDADES.sub(lambda m: f"{_milhar(m.group(1))} un", texto)
