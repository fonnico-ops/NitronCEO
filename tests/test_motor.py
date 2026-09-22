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

    assert len(rodada.sinais) == 37
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


def _motor_canais(tmp_path, canais, fallback=None):
    cfg = carregar()
    repo = Repositorio(tmp_path / "t.db")
    saida = io.StringIO()
    console = Console(saida)
    motor = Motor(
        cfg, FonteArquivo(FIXTURES), repo,
        {c: console for c in canais}, raiz=RAIZ, fallback=fallback,
    )
    return motor, repo, saida


def test_modo_so_email_nao_emudece_o_que_a_matriz_mandava_no_teams(tmp_path):
    # 35 dos 37 KPIs mandam o nível amarelo só pelo Teams, e dois mandam o
    # vermelho só por lá. Rodar sem Teams não pode significar que essas
    # cobranças deixam de existir — elas saem por e-mail.
    motor, repo, saida = _motor_canais(tmp_path, ["email"], fallback="email")
    rodada = motor.rodar(cobrar=False)

    enviadas = saida.getvalue().count("   para:")
    assert enviadas == len(rodada.acoes_novas), "alguma ação saiu sem mensagem"
    assert rodada.desvios, "o desvio de canal tem que ficar registrado"
    assert ("teams", "email") in set(rodada.desvios)

    texto = pulso(rodada, motor.cfg)
    assert "Cobranças que saíram por outro canal" in texto
    repo.fechar()


def test_sem_fallback_o_canal_ausente_e_silencio_declarado(tmp_path):
    # Sem fallback configurado o motor não inventa canal — mas também não
    # finge que enviou: a ação é aberta e nada sai.
    motor, repo, saida = _motor_canais(tmp_path, ["ghl"], fallback=None)
    rodada = motor.rodar(cobrar=False)

    assert rodada.acoes_novas
    assert saida.getvalue().count("   para:") == 0
    assert not rodada.desvios
    repo.fechar()


def test_com_teams_e_email_cada_canal_recebe_o_seu(tmp_path):
    motor, repo, saida = _motor_canais(tmp_path, ["teams", "email"], fallback="email")
    rodada = motor.rodar(cobrar=False)

    # mais mensagens que ações: os KPIs críticos vão pelos dois canais
    assert saida.getvalue().count("   para:") > len(rodada.acoes_novas)
    assert not rodada.desvios, "com os dois canais no ar não há desvio"
    repo.fechar()
