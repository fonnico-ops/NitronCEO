"""Uma mensagem por gestor, com tudo dele.

Este módulo nasceu de um erro medido em produção: na primeira rodada real,
Alex e Charles receberam cinco e-mails cada no mesmo minuto. Cinco
cobranças simultâneas não são cinco cobranças — são ruído, e ruído ensina
a filtrar o remetente.

O que o agrupamento NÃO pode fazer é diluir a responsabilidade: cada ponto
mantém token, prazo e escada próprios."""

import io
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nitronceo.acoes import Acao, Estado  # noqa: E402
from nitronceo.avaliador import Nivel  # noqa: E402
from nitronceo.config import RAIZ, carregar  # noqa: E402
from nitronceo.lote import agrupar, marcar_lote, montar  # noqa: E402
from nitronceo.motor import Motor  # noqa: E402
from nitronceo.notificadores import Console  # noqa: E402
from nitronceo.repositorio import Repositorio  # noqa: E402
from nitronceo.sankhya import FonteArquivo  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
PAINEL = "https://exemplo/painel"


def _rodada(tmp_path):
    cfg = carregar()
    repo = Repositorio(tmp_path / "t.db")
    saida = io.StringIO()
    motor = Motor(cfg, FonteArquivo(FIXTURES), repo, {"ghl": Console(saida)},
                  raiz=RAIZ, fallback="ghl")
    motor.notificadores = {}
    rodada = motor.rodar(cobrar=False)
    motor.notificadores = {"ghl": Console(saida)}
    return cfg, repo, motor, rodada, saida


# ------------------------------------------------------------ agrupamento


def test_um_lote_por_dono_em_vez_de_um_por_cobranca(tmp_path):
    cfg, repo, _, _, _ = _rodada(tmp_path)
    abertas = repo.acoes_em_aberto()
    lotes = agrupar(abertas, cfg, PAINEL)

    assert len(abertas) == 21
    assert len(lotes) == 8, "21 cobranças têm que virar 8 mensagens"
    assert sum(len(x.acoes) for x in lotes) == 21, "nenhuma pode se perder"
    # o mais carregado vem primeiro, para quem lê o log
    assert lotes[0].papel.quem == "Alex Souza e Charles Silva"
    assert len(lotes[0].acoes) == 5
    repo.fechar()


def test_cada_ponto_mantem_token_e_prazo_proprios(tmp_path):
    cfg, repo, _, _, _ = _rodada(tmp_path)
    producao = [a for a in repo.acoes_em_aberto() if a.dono == "gerente_producao"]
    lote = montar(cfg.papel("gerente_producao"), producao, cfg, PAINEL)

    for acao in producao:
        assert f"[NTR-{acao.id[:8]}]" in lote.corpo_md
        assert f"{acao.prazo:%d/%m às %H:%M}" in lote.corpo_md
    # e o assunto carrega o token do lote, não o de uma das ações
    assert f"[NTR-L-{lote.token}]" in lote.assunto
    repo.fechar()


def test_o_critico_vem_antes_do_vermelho(tmp_path):
    cfg, repo, _, _, _ = _rodada(tmp_path)
    producao = [a for a in repo.acoes_em_aberto() if a.dono == "gerente_producao"]
    lote = montar(cfg.papel("gerente_producao"), producao, cfg, PAINEL)

    posicoes = [
        lote.corpo_md.index(a.titulo) for a in lote.acoes
        if a.nivel is Nivel.CRITICO
    ]
    vermelhos = [
        lote.corpo_md.index(a.titulo) for a in lote.acoes
        if a.nivel is Nivel.VERMELHO
    ]
    assert max(posicoes) < min(vermelhos)
    repo.fechar()


def test_token_do_lote_e_estavel_para_as_mesmas_acoes(tmp_path):
    _, repo, _, _, _ = _rodada(tmp_path)
    acoes = repo.acoes_em_aberto()[:3]

    assert marcar_lote(acoes) == marcar_lote(list(reversed(acoes)))
    assert marcar_lote(acoes) != marcar_lote(acoes[:2])
    repo.fechar()


def test_lote_chama_a_pessoa_pelo_nome(tmp_path):
    cfg, repo, _, _, _ = _rodada(tmp_path)
    compras = [a for a in repo.acoes_em_aberto() if a.dono == "compras"]
    lote = montar(cfg.papel("compras"), compras, cfg, PAINEL)

    assert lote.corpo_md.startswith("Cristiane,")
    assert "um ponto da sua área" in lote.corpo_md  # singular quando é 1
    repo.fechar()


# ---------------------------------------------------------------- cadência


def test_primeira_vez_dispara(tmp_path):
    repo = Repositorio(tmp_path / "t.db")
    assert repo.deve_disparar(2) is True
    repo.fechar()


def test_a_cadencia_mora_no_banco_e_nao_no_cron(tmp_path):
    """`0 17 */2 * *` escorrega na virada do mês e ninguém percebe.

    O cron roda todo dia às 17h e pergunta aqui se hoje é dia.
    """
    repo = Repositorio(tmp_path / "t.db")
    repo.registrar_disparo(lotes=8, acoes=21)
    hoje = datetime.now()

    assert repo.deve_disparar(2, hoje) is False
    assert repo.deve_disparar(2, hoje + timedelta(days=1)) is False
    assert repo.deve_disparar(2, hoje + timedelta(days=2)) is True
    assert repo.deve_disparar(2, hoje + timedelta(days=9)) is True
    repo.fechar()


def test_disparo_registra_o_lote_para_a_resposta_achar_as_acoes(tmp_path):
    cfg, repo, motor, _, saida = _rodada(tmp_path)
    abertas = repo.acoes_em_aberto()
    lotes = motor.disparar_agrupado(abertas)

    lote = lotes[0]
    do_banco = set(repo.acoes_do_lote(lote.token))
    assert do_banco == {a.id for a in lote.acoes}
    # e o disparo ficou registrado, senão a cadência não avança
    assert repo.ultimo_disparo() is not None
    # uma mensagem por dono, não uma por cobrança
    assert saida.getvalue().count("   para:") == len(lotes)
    repo.fechar()


# ------------------------------------------------------- corpo com detalhe

def _acao_rica(**extra):
    base = dict(
        id="7b13ca5a89d0", kpi_id="liberacao_comercial",
        titulo="Pedido parado há 180 dias sem aprovação nem recusa",
        passos=["Libere ou recuse."], dono="diretor_comercial",
        nivel=Nivel.CRITICO, valor=180, unidade="contagem",
        criada_em=datetime(2026, 9, 24, 8, 0),
        prazo=datetime(2026, 9, 26, 17, 0),
        contexto={
            "PEDIDOS_TRAVADOS": 87, "VLR_TRAVADO": 505694.43,
            "DIAS_MAX": 180, "DIAS_MEDIO": 47.6, "PARADOS_MAIS_30D": 52,
            "LISTA": "KALUNGA — R$ 34174 (35d, Atraso) · MATOS — R$ 2085 (32d)",
        },
    )
    base.update(extra)
    return Acao(**base)


def _corpo(acao):
    cfg = carregar()
    return montar(cfg.papel(acao.dono), [acao], cfg, "https://painel",
                  datetime(2026, 9, 24, 17, 0)).corpo_md


def test_corpo_nao_vaza_nome_de_coluna_nem_float_cru():
    """O que saiu em 24/09/2026 foi `VLR_TRAVADO: 505694.43`.

    Nome de coluna e float cru são planilha, não cobrança: quem abre o
    e-mail não converte 505694.43 em meio milhão na primeira passada, e a
    primeira passada é a única que a maioria dá.
    """
    corpo = _corpo(_acao_rica())
    assert "VLR_TRAVADO" not in corpo
    assert "505694.43" not in corpo
    assert "R$ 505.694,43" in corpo


def test_corpo_traz_o_resumo_da_matriz():
    corpo = _corpo(_acao_rica())
    assert "87 pedidos" in corpo
    assert "52 deles já passaram de 30 dias" in corpo


def test_lista_do_sql_vira_bullets():
    corpo = _corpo(_acao_rica())
    assert "**Onde está concentrado:**" in corpo
    assert "- KALUNGA — R$ 34.174 (35d, Atraso)" in corpo
    assert "- MATOS — R$ 2.085 (32d)" in corpo


def test_lista_nao_e_quebrada_por_virgula():
    """`(35d, Atraso)` é um item só — quebrar na vírgula o partiria ao meio."""
    corpo = _corpo(_acao_rica())
    assert "- Atraso)" not in corpo


def test_sem_lista_o_corpo_segue_de_pe():
    acao = _acao_rica()
    acao.contexto.pop("LISTA")
    corpo = _corpo(acao)
    assert "Onde está concentrado" not in corpo
    assert "R$ 505.694,43" in corpo


def test_resumo_generico_nao_abre_com_denominador():
    """Sem molde na matriz, a frase não pode começar pela boa notícia.

    Num ponto sobre OS abertas, `FECHADAS_365D` é o universo, não o
    problema: abrir com ele contaria o que deu certo numa cobrança.
    """
    from nitronceo.lote import _resumo
    acao = _acao_rica(kpi_id="x", contexto={
        "FECHADAS_365D": 1804, "ABERTAS": 503, "COM_EQPTO_PARADO": 330,
    })
    kpi = {"metrica": "ABERTAS_VELHAS", "acao": {}}
    resumo = _resumo(acao, kpi)
    assert resumo.startswith("**503 abertas**")
    assert "1.804" in resumo
