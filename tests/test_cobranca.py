import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nitronceo.acoes import Acao, Estado  # noqa: E402
from nitronceo.avaliador import Nivel  # noqa: E402
from nitronceo.cobranca import MAX_RODADAS, aplicar, proxima_cobranca  # noqa: E402
from nitronceo.config import Config  # noqa: E402

PESSOAS = {
    "papeis": {
        "ceo": {"nome": "CEO", "escalonar_para": None,
                "pessoas": [{"nome": "Renato", "email": "r@x"}]},
        "gerente": {"nome": "Gerência", "escalonar_para": "ceo",
                    "pessoas": [{"nome": "Gerente", "email": "g@x"}]},
        "pcp": {"nome": "PCP", "escalonar_para": "gerente",
                "pessoas": [{"nome": "Ana", "email": "a@x"},
                            {"nome": "Bruno", "email": "b@x"}]},
    }
}
CFG = Config(matriz={"kpis": []}, pessoas=PESSOAS)

CRIADA = datetime(2026, 9, 22, 8, 0)
PRAZO = CRIADA + timedelta(hours=4)


def _acao(**extra) -> Acao:
    base = dict(
        id="a1", kpi_id="k", titulo="T", passos=["p"], dono="pcp",
        nivel=Nivel.VERMELHO, valor=1.0, unidade="", criada_em=CRIADA, prazo=PRAZO,
    )
    base.update(extra)
    return Acao(**base)


def test_nao_cobra_antes_do_prazo():
    assert proxima_cobranca(_acao(), CFG, PRAZO - timedelta(minutes=1)) is None


def test_primeira_rodada_volta_para_o_dono():
    c = proxima_cobranca(_acao(), CFG, PRAZO + timedelta(minutes=1))
    assert c.destinatario == "pcp"
    assert c.escalada is False
    assert "Ana e Bruno" not in c.motivo   # a 1ª rodada fala com o dono, não sobre ele


def test_papel_com_duas_pessoas_cobra_as_duas():
    # O papel é o dono, não o indivíduo: dividir a cobrança entre os dois a
    # transformaria em cobrança de ninguém.
    pcp = CFG.papel("pcp")
    assert pcp.emails == ["a@x", "b@x"]
    assert pcp.quem == "Ana e Bruno"


def test_segunda_rodada_sobe_para_o_gestor():
    acao = _acao(escalonamentos=1)
    # rodada 1 vence em criada + 1.5 * janela = 08:00 + 6h
    assert proxima_cobranca(acao, CFG, CRIADA + timedelta(hours=5)) is None
    c = proxima_cobranca(acao, CFG, CRIADA + timedelta(hours=7))
    assert c.destinatario == "gerente"
    assert c.escalada is True
    assert c.urgente is True
    assert "Ana e Bruno" in c.motivo       # a escalada nomeia quem não respondeu


def test_terceira_rodada_chega_no_ceo():
    c = proxima_cobranca(_acao(escalonamentos=2), CFG, CRIADA + timedelta(hours=9))
    assert c.destinatario == "ceo"


def test_para_de_cobrar_depois_do_teto():
    # Cobrança infinita vira ruído; o silêncio passa a ser problema de gente.
    acao = _acao(escalonamentos=MAX_RODADAS)
    assert proxima_cobranca(acao, CFG, CRIADA + timedelta(days=5)) is None


def test_resposta_encerra_a_escada():
    acao = _acao(estado=Estado.RESPONDIDA)
    assert proxima_cobranca(acao, CFG, CRIADA + timedelta(days=5)) is None


def test_dono_sem_gestor_sobe_direto_ao_ceo():
    c = proxima_cobranca(
        _acao(dono="gerente", escalonamentos=1), CFG, CRIADA + timedelta(hours=7)
    )
    assert c.destinatario == "ceo"


def test_ceo_nao_cobra_a_si_mesmo():
    assert proxima_cobranca(
        _acao(dono="ceo", escalonamentos=1), CFG, CRIADA + timedelta(hours=7)
    ) is None


def test_aplicar_avanca_a_rodada():
    acao = _acao()
    c = proxima_cobranca(acao, CFG, PRAZO + timedelta(minutes=1))
    assert aplicar(acao, c) is Estado.VENCIDA
    assert acao.escalonamentos == 1
