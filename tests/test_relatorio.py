"""O relatório de acompanhamento não cobra ninguém — e essa diferença
precisa estar no texto, não só na intenção. Quem recebe tem que entender
em dois segundos que não há prazo para ele."""

import io
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nitronceo.acoes import Acao, Estado  # noqa: E402
from nitronceo.avaliador import Nivel  # noqa: E402
from nitronceo.config import RAIZ, carregar  # noqa: E402
from nitronceo.motor import Motor  # noqa: E402
from nitronceo.notificadores import Console  # noqa: E402
from nitronceo.relatorio import montar  # noqa: E402
from nitronceo.repositorio import Repositorio  # noqa: E402
from nitronceo.sankhya import FonteArquivo  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def _rodada(tmp_path):
    cfg = carregar()
    repo = Repositorio(tmp_path / "t.db")
    motor = Motor(cfg, FonteArquivo(FIXTURES), repo,
                  {"teams": Console(io.StringIO())}, raiz=RAIZ)
    return cfg, repo, motor.rodar(cobrar=False)


def test_relatorio_cobre_todas_as_areas_e_nomeia_os_donos(tmp_path):
    cfg, repo, rodada = _rodada(tmp_path)
    rel = montar(cfg, rodada.sinais, repo.acoes_em_aberto())

    # o quadro inteiro, não um indicador: quem acompanha vê todas as áreas
    for nome in ("Comercial", "Logística e Expedição", "Produção",
                 "Financeiro", "Compras", "PCP", "E-commerce",
                 "Projetos e Moldes"):
        assert nome in rel.corpo_md, f"{nome} sumiu do relatório"

    # e sabe de quem é cada uma
    assert "Alex Souza e Charles Silva" in rel.corpo_md
    assert "Rafael Francisco" in rel.corpo_md

    # o assunto já entrega o tamanho do problema, sem precisar abrir
    assert "21 fora da linha" in rel.assunto
    assert "21 cobranças abertas" in rel.assunto
    repo.fechar()


def test_deixa_claro_que_nao_e_cobranca(tmp_path):
    cfg, repo, rodada = _rodada(tmp_path)
    rel = montar(cfg, rodada.sinais, repo.acoes_em_aberto())

    assert "nada aqui espera resposta sua" in rel.corpo_md
    # e não repete o convite a responder que a cobrança faz
    assert "RESOLVIDO" not in rel.corpo_md
    assert "Responda neste e-mail" not in rel.corpo_md
    repo.fechar()


def test_dia_bom_cabe_em_quatro_linhas(tmp_path):
    """Relatório longo sobre dia normal ensina a não ler o relatório."""
    cfg, repo, rodada = _rodada(tmp_path)
    verdes = [s for s in rodada.sinais if s.nivel is Nivel.VERDE]

    rel = montar(cfg, verdes, [])

    assert "tudo no alvo" in rel.assunto
    assert "🟢" in rel.assunto
    assert len(rel.corpo_md.splitlines()) <= 6
    assert "Onde está fora da linha" not in rel.corpo_md
    repo.fechar()


def test_o_que_venceu_vem_antes_do_resto(tmp_path):
    cfg, repo, rodada = _rodada(tmp_path)
    agora = datetime.now()
    vencida = Acao(
        id="aaaaaaaaaaaa", kpi_id="emissao_ntrlog",
        titulo="NTR Log emitiu 2.6%", passos=["conciliar"], dono="logistica",
        nivel=Nivel.CRITICO, valor=2.6, unidade="percentual",
        estado=Estado.ABERTA, criada_em=agora - timedelta(hours=40),
        prazo=agora - timedelta(hours=16), contexto={}, escalonamentos=1,
    )
    rel = montar(cfg, rodada.sinais, [vencida])

    corpo = rel.corpo_md
    assert "## Passou do prazo" in corpo
    assert corpo.index("Passou do prazo") < corpo.index("Onde está fora")
    assert "venceu há 16h" in corpo
    assert "1ª escalada" in corpo
    assert "Expedição e Forla Silva" in corpo
    repo.fechar()


def test_kpi_que_nao_mediu_aparece_e_nao_conta_como_verde(tmp_path):
    from nitronceo.avaliador import Sinal

    cfg, repo, rodada = _rodada(tmp_path)
    quebrado = Sinal(
        kpi_id="faturamento_ritmo", titulo="Ritmo de faturamento",
        area="logistica", nivel=Nivel.VERDE, valor=None, unidade="percentual",
        dono="logistica", modo="ativo", medido_em=datetime.now(), linha={},
        erro="ORA-00942: tabela não existe",
    )
    rel = montar(cfg, [quebrado], [])

    # o assunto não pode sugerir dia tranquilo
    assert "não mediram" in rel.assunto
    assert "tudo no alvo" not in rel.assunto
    assert "1 não mediram hoje" in rel.corpo_md
    assert "não é indicador verde" in rel.corpo_md
    repo.fechar()


def test_erro_de_medicao_em_massa_nao_vira_dia_tranquilo(tmp_path):
    """O alarme que não toca porque a bateria acabou.

    Se o ERP cair e os 37 indicadores falharem, o relatório não pode sair
    como "tudo no alvo" — seria a pior mentira que este sistema conta.
    """
    from nitronceo.avaliador import Sinal

    cfg, repo, _ = _rodada(tmp_path)
    caidos = [
        Sinal(kpi_id=k["id"], titulo=k["titulo"], area=k["area"],
              nivel=Nivel.VERDE, valor=None, unidade=k["unidade"],
              dono=k["dono"], modo="ativo", medido_em=datetime.now(),
              linha={}, erro="ORA-12541: no listener")
        for k in cfg.matriz["kpis"]
    ]
    rel = montar(cfg, caidos, [])

    assert "tudo no alvo" not in rel.assunto
    assert "não mediram" in rel.assunto
    assert "está incompleto" in rel.corpo_md
    repo.fechar()


def test_a_leitura_do_renato_entra_quando_existe(tmp_path):
    cfg, repo, rodada = _rodada(tmp_path)
    rel = montar(cfg, rodada.sinais, repo.acoes_em_aberto(),
                 leitura="## Leitura cruzada\nA INJETORA 19 é a pior nos dois.")

    assert "A INJETORA 19 é a pior nos dois." in rel.corpo_md
    assert rel.corpo_md.index("INJETORA 19") < rel.corpo_md.index("Onde está fora")
    repo.fechar()


def test_lista_de_acompanhamento_nao_se_confunde_com_dono_de_cobranca():
    cfg = carregar()
    acompanham = {p.email for p in cfg.acompanhamento}

    assert acompanham == {
        "renato.fonseca@nitron.com.br",
        "ricardo.fonseca@nitron.com.br",
        "cristiane.alves@nitron.com.br",
    }
    # a Cristiane está nas duas pontas: acompanha o quadro inteiro E é dona
    # das cobranças de Compras. São coisas separadas, e ela recebe as duas.
    assert "cristiane.alves@nitron.com.br" in cfg.papel("compras").emails
    # o Ricardo Fonseca só acompanha: não é dono de papel nenhum
    donos = {e for papel in cfg.papeis.values() for e in papel.emails}
    assert "ricardo.fonseca@nitron.com.br" not in donos
