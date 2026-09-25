import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nitronceo.numeros import (  # noqa: E402
    e_base, formatar_numero, frase, rotulo_de, unidade_de, vestir_lista,
)


# ------------------------------------------------------------------ unidade

def test_unidade_vem_do_prefixo_da_coluna():
    assert unidade_de("VLR_TRAVADO") == "reais"
    assert unidade_de("META_DIA") == "reais"
    assert unidade_de("SALDO_D0_D7") == "reais"
    assert unidade_de("PCT_PROJECAO_META") == "percentual"
    assert unidade_de("HORAS_PARADAS") == "horas"
    assert unidade_de("MEDIANA_MIN") == "minutos"
    assert unidade_de("DIAS_MEDIO") == "dias"
    assert unidade_de("PEDIDOS_TRAVADOS") == "contagem"


def test_coluna_que_mente_sobre_o_tipo_tem_unidade_forcada():
    """`QUEDA_ACIMA_50PCT` termina em PCT mas conta produtos.

    Sem o override sairia "70,0%" — um percentual que ninguém mediu, na
    mensagem que o diretor comercial usa para decidir.
    """
    assert unidade_de("QUEDA_ACIMA_50PCT") == "contagem"
    assert frase("QUEDA_ACIMA_50PCT", 70) == "70 produtos caíram mais de 50%"


def test_saldo_nao_positivo_conta_itens_nao_reais():
    assert unidade_de("SALDO_NAO_POSITIVO") == "contagem"
    assert "R$" not in frase("SALDO_NAO_POSITIVO", 59)


# ---------------------------------------------------------------- formatação

def test_numero_sai_no_padrao_brasileiro():
    assert formatar_numero(505694.43, "reais") == "R$ 505.694,43"
    assert formatar_numero(186.8, "percentual") == "186,8%"
    assert formatar_numero(773.4, "horas") == "773,4h"
    assert formatar_numero(115.8, "minutos") == "116 min"
    assert formatar_numero(304723, "contagem") == "304.723"


def test_dia_fracionado_nao_vira_dia_inteiro():
    """Mediana de 0,8 dia é "fecha no mesmo dia" — 1 dia seria outra coisa."""
    assert formatar_numero(0.8, "dias") == "0,8 dias"
    assert formatar_numero(1, "dias") == "1 dia"
    assert formatar_numero(180, "dias") == "180 dias"


def test_valor_ausente_nao_inventa_numero():
    assert formatar_numero(None, "reais") == "—"


# -------------------------------------------------------------------- rótulo

def test_rotulo_nao_repete_a_unidade_que_o_numero_ja_diz():
    assert frase("HORAS_PARADAS", 773.4) == "773,4h paradas"
    assert "horas horas" not in frase("HORAS_PERDIDAS", 711.8)


def test_todas_as_colunas_das_fixtures_tem_rotulo_legivel():
    """Nenhum nome de coluna pode vazar cru para a caixa de entrada."""
    import json
    fixtures = Path(__file__).parent / "fixtures"
    for arquivo in fixtures.glob("*.json"):
        for linha in json.loads(arquivo.read_text()):
            for coluna in linha:
                r = rotulo_de(coluna)
                assert r == r.lower() or any(c.isupper() for c in r)
                assert "_" not in r, f"{coluna} vazou como {r!r}"


# --------------------------------------------------------------------- bases

def test_denominador_e_marcado_como_base():
    assert e_base("FECHADAS_365D")
    assert e_base("OS_JANELA")
    assert not e_base("ABERTAS_VELHAS")


# --------------------------------------------------------------------- lista

def test_lista_do_oracle_ganha_separador_de_milhar():
    cru = "LIXEIRA (052/B): R$ 285623 -> R$ 135219 (47%)"
    assert vestir_lista(cru) == "LIXEIRA (052/B): R$ 285.623 -> R$ 135.219 (47%)"


def test_vestir_lista_nao_mexe_no_que_ja_esta_formatado():
    ja = "CESTO: 253.036 un, R$ 502.074"
    assert vestir_lista(ja) == ja


def test_vestir_lista_preserva_numeros_curtos():
    assert vestir_lista("INJETORA 3: 547 min (3 trocas)") == \
        "INJETORA 3: 547 min (3 trocas)"
