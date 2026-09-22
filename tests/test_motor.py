import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nitronceo.config import RAIZ, carregar  # noqa: E402
from nitronceo.motor import Motor, pulso  # noqa: E402
from nitronceo.notificadores import Console  # noqa: E402
from nitronceo.repositorio import Repositorio  # noqa: E402
from nitronceo.sankhya import FonteArquivo  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def _motor(tmp_path):
    cfg = carregar()
    repo = Repositorio(tmp_path / "t.db")
    saida = io.StringIO()
    console = Console(saida)
    motor = Motor(cfg, FonteArquivo(FIXTURES), repo,
                  {"teams": console, "email": console}, raiz=RAIZ)
    return motor, repo, saida


def test_rodada_completa_sobre_dados_reais(tmp_path):
    motor, repo, _ = _motor(tmp_path)
    rodada = motor.rodar(cobrar=False)

    assert len(rodada.sinais) == 27
    assert not rodada.falhas

    texto = pulso(rodada, motor.cfg)
    assert "Pulso Nitron" in texto
    assert "R$ 9.728.499,68" in texto   # inadimplência formatada em pt-BR
    repo.fechar()


def test_kpi_em_sombra_mede_mas_nao_abre_acao(tmp_path):
    motor, repo, _ = _motor(tmp_path)
    rodada = motor.rodar(cobrar=False)

    sombra = {s.kpi_id for s in rodada.sinais if s.modo == "sombra"}
    abertas = {a.kpi_id for a in rodada.acoes_novas}

    # performance_representante está vermelho nos fixtures (26 abaixo da meta)
    # e mesmo assim não pode cobrar ninguém enquanto estiver em sombra.
    assert "performance_representante" in sombra
    assert not (sombra & abertas)
    repo.fechar()


def test_rodar_duas_vezes_no_mesmo_dia_nao_duplica_cobranca(tmp_path):
    motor, repo, _ = _motor(tmp_path)

    primeira = motor.rodar(cobrar=False)
    segunda = motor.rodar(cobrar=False)

    assert primeira.acoes_novas          # abriu na primeira
    assert not segunda.acoes_novas       # e não repetiu na segunda
    repo.fechar()


def test_resposta_encerra_a_acao(tmp_path):
    motor, repo, _ = _motor(tmp_path)
    rodada = motor.rodar(cobrar=False)
    acao = rodada.acoes_novas[0]
    antes = len(repo.acoes_em_aberto())

    assert repo.registrar_resposta(acao.id, "Plano enviado, protesto na quinta.")

    abertas = repo.acoes_em_aberto()
    assert len(abertas) == antes - 1
    assert acao.id not in {a.id for a in abertas}
    repo.fechar()


def test_reincidencia_e_contada_por_dia(tmp_path):
    motor, repo, _ = _motor(tmp_path)
    motor.rodar(cobrar=False)
    # Duas medições no mesmo dia contam como um dia, não dois.
    motor.rodar(cobrar=False)
    assert repo.dias_consecutivos_ruins("inadimplencia") == 1
    repo.fechar()
