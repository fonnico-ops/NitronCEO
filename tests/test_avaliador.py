import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nitronceo.avaliador import Nivel, avaliar, classificar  # noqa: E402


INFERIOR = {"tipo": "limite_inferior", "verde": 100, "amarelo": 92, "vermelho": 85}
SUPERIOR = {"tipo": "limite_superior", "verde": 1.5, "amarelo": 3.0, "vermelho": 5.0}


def test_limite_inferior_usa_os_tres_cortes():
    assert classificar(INFERIOR, 107.7) is Nivel.VERDE
    assert classificar(INFERIOR, 100) is Nivel.VERDE
    assert classificar(INFERIOR, 95) is Nivel.AMARELO
    assert classificar(INFERIOR, 88) is Nivel.VERMELHO
    assert classificar(INFERIOR, 80) is Nivel.CRITICO


def test_limite_superior_inverte_a_ordem():
    assert classificar(SUPERIOR, 0.53) is Nivel.VERDE
    assert classificar(SUPERIOR, 2.0) is Nivel.AMARELO
    assert classificar(SUPERIOR, 4.0) is Nivel.VERMELHO
    assert classificar(SUPERIOR, 11.3) is Nivel.CRITICO


def _kpi(**extra):
    base = {
        "id": "x", "titulo": "X", "area": "a", "metrica": "V", "unidade": "percentual",
        "dono": "ceo", "modo": "ativo", "avaliacao": INFERIOR,
    }
    base.update(extra)
    return base


def test_metrica_nula_nao_vira_verde():
    # O alarme que não toca porque a bateria acabou é pior que alarme nenhum.
    sinal = avaliar(_kpi(), [{"V": None}])
    assert sinal.erro is not None
    assert sinal.notificavel is False


def test_consulta_vazia_nao_vira_verde():
    sinal = avaliar(_kpi(), [])
    assert sinal.erro is not None
    assert sinal.notificavel is False


def test_coluna_ausente_e_reportada():
    sinal = avaliar(_kpi(), [{"OUTRA": 1}])
    assert "V" in sinal.erro


def test_kpi_em_sombra_nunca_notifica():
    sinal = avaliar(_kpi(modo="sombra"), [{"V": 10}])
    assert sinal.nivel is Nivel.CRITICO
    assert sinal.notificavel is False
