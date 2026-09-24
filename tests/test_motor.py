import io
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nitronceo.acoes import Acao  # noqa: E402
from nitronceo.avaliador import Nivel  # noqa: E402
from nitronceo.config import RAIZ, carregar  # noqa: E402
from nitronceo.motor import Motor, pulso, renovar_prazo  # noqa: E402
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


def test_upn_do_teams_pode_diferir_do_email(tmp_path):
    """A Ana Julia recebe e-mail num endereço e existe no Teams em outro.

    Quando isso acontece e ninguém declara o `upn`, o Graph devolve 404 na
    mensagem direta e a cobrança não chega — sem erro visível.
    """
    from nitronceo.config import Papel, Pessoa
    from nitronceo.notificadores import Mensagem

    papel = Papel(
        chave="ecommerce", nome="E-commerce",
        pessoas=[Pessoa("Ana Julia", "ecommerce2@nitron.com.br",
                        upn="ecommerce@nitron.com.br")],
    )
    assert papel.emails == ["ecommerce2@nitron.com.br"]
    assert papel.upns == ["ecommerce@nitron.com.br"]

    msg = Mensagem("x", "y", destinatarios=papel.emails, upns=papel.upns)
    assert msg.para_teams == ["ecommerce@nitron.com.br"]

    # Sem `upn` declarado, o e-mail serve para os dois — que é o caso comum.
    simples = Papel(chave="pcp", nome="PCP",
                    pessoas=[Pessoa("Anderson", "anderson.lourenco@nitron.com.br")])
    assert simples.upns == simples.emails


def test_envio_que_falha_nao_derruba_as_outras_cobrancas(tmp_path):
    """Um UPN errado é 404 no Graph. Sem tratamento, a primeira pessoa mal
    cadastrada impediria as outras 36 cobranças de sair."""
    class CanalQuebrado:
        nome = "teams"

        def enviar(self, msg):
            raise RuntimeError("404 Not Found: users('ecommerce2@nitron.com.br')")

    cfg = carregar()
    repo = Repositorio(tmp_path / "t.db")
    motor = Motor(cfg, FonteArquivo(FIXTURES), repo,
                  {"teams": CanalQuebrado()}, raiz=RAIZ)
    rodada = motor.rodar(cobrar=False)

    assert len(rodada.sinais) == 37, "a medição não pode parar"
    assert rodada.acoes_novas, "as ações continuam sendo abertas"
    assert rodada.falhas_de_envio, "a falha tem que ficar registrada"
    assert "404" in rodada.falhas_de_envio[0][2]

    texto = pulso(rodada, motor.cfg)
    assert "NÃO chegaram no destinatário" in texto
    repo.fechar()


# --------------------------------------------------------------- prazo na saída

def _acao_com_prazo(criada: datetime, prazo: datetime) -> Acao:
    return Acao(
        id="aaaaaaaaaaaa", kpi_id="faturamento_ritmo", titulo="t", passos=["p"],
        dono="logistica", nivel=Nivel.CRITICO, valor=1.0, unidade="un",
        criada_em=criada, prazo=prazo,
    )


def test_renovar_prazo_nao_mexe_no_que_ainda_esta_de_pe():
    agora = datetime(2026, 9, 24, 14, 0)
    acao = _acao_com_prazo(datetime(2026, 9, 24, 13, 0),
                           datetime(2026, 9, 24, 17, 0))
    assert renovar_prazo(acao, agora) == datetime(2026, 9, 24, 17, 0)


def test_renovar_prazo_conta_a_janela_da_entrega():
    """Janela de 2h apurada às 8h, entregue às 14h: vence às 16h, não às 10h."""
    acao = _acao_com_prazo(datetime(2026, 9, 24, 8, 0),
                           datetime(2026, 9, 24, 10, 0))
    novo = renovar_prazo(acao, datetime(2026, 9, 24, 14, 0))
    assert novo == datetime(2026, 9, 24, 16, 0)


def test_renovar_prazo_nao_vence_de_madrugada():
    """Entregue às 19h22, 2h de janela: vence às 10h do dia seguinte."""
    acao = _acao_com_prazo(datetime(2026, 9, 24, 17, 0),
                           datetime(2026, 9, 24, 19, 0))
    novo = renovar_prazo(acao, datetime(2026, 9, 24, 19, 22))
    assert novo == datetime(2026, 9, 25, 10, 0)


def test_renovar_prazo_pula_o_fim_de_semana():
    """Sexta 19h com 2h de janela não vence sábado: vence segunda."""
    acao = _acao_com_prazo(datetime(2026, 9, 25, 17, 0),
                           datetime(2026, 9, 25, 19, 0))
    novo = renovar_prazo(acao, datetime(2026, 9, 25, 19, 30))
    assert novo == datetime(2026, 9, 28, 10, 0)


def test_disparar_agrupado_grava_o_prazo_renovado(tmp_path):
    """Não basta renovar na memória: a escada de cobrança lê do banco."""
    m, repo, _ = _motor(tmp_path)
    acao = _acao_com_prazo(datetime(2026, 9, 23, 17, 0),
                           datetime(2026, 9, 23, 19, 0))
    repo.salvar_acao(acao)
    m.disparar_agrupado([acao])

    gravada = repo.buscar_acao(acao.id)
    assert gravada is not None
    assert gravada.prazo > datetime.now()
    repo.fechar()
