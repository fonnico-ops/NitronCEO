"""O markdown vira HTML porque nem o Graph nem o GHL renderizam markdown.

O que se testa aqui não é estética: é que o **negrito** sobreviva. No
corpo da cobrança o que está marcado é o número e o prazo, e a versão
anterior desta função apagava os asteriscos — entregando a frase inteira
no mesmo peso, com o `#` do título aparecendo cru para o CEO."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nitronceo.notificadores.base import Mensagem  # noqa: E402
from nitronceo.notificadores.graph import _html  # noqa: E402


def _conv(md: str) -> str:
    return _html(Mensagem("assunto", md, []))


def test_os_tres_niveis_de_titulo():
    html = _conv("# Um\n## Dois\n### Três")
    assert "<h1>Um</h1>" in html
    assert "<h2>Dois</h2>" in html
    assert "<h3>Três</h3>" in html
    # nenhum `#` pode vazar para o texto
    assert "#" not in html


def test_negrito_vira_strong_em_vez_de_sumir():
    html = _conv("**R$ 9.728.499,68** vencidos a receber")
    assert "<strong>R$ 9.728.499,68</strong>" in html
    assert "*" not in html


def test_negrito_dentro_de_item_de_lista():
    html = _conv("- **Claudia Ribeiro** — 4 cobranças")
    assert "<li><strong>Claudia Ribeiro</strong> — 4 cobranças</li>" in html


def test_italico_do_rodape():
    html = _conv("_Acompanhamento, não cobrança._")
    assert "<em>Acompanhamento, não cobrança.</em>" in html


def test_underline_no_meio_de_nome_de_coluna_nao_vira_italico():
    # Os números da apuração vêm com nomes tipo FRETE_PAGO_MES; tratá-los
    # como itálico comeria metade do nome da coluna.
    html = _conv("- FRETE_PAGO_MES: 842709.4\n- GAP_EMISSAO: 821142.28")
    assert "FRETE_PAGO_MES" in html
    assert "GAP_EMISSAO" in html
    assert "<em>" not in html


def test_regua_vira_hr():
    assert "<hr>" in _conv("antes\n\n---\n\ndepois")


def test_lista_fecha_sozinha_no_fim():
    html = _conv("- um\n- dois")
    assert html.count("<ul>") == 1 and html.count("</ul>") == 1


def test_relatorio_inteiro_nao_deixa_markdown_cru(tmp_path):
    """Trava de ponta a ponta sobre o relatório de verdade."""
    import io

    from nitronceo.config import RAIZ, carregar
    from nitronceo.motor import Motor
    from nitronceo.notificadores import Console
    from nitronceo.relatorio import montar
    from nitronceo.repositorio import Repositorio
    from nitronceo.sankhya import FonteArquivo

    cfg = carregar()
    repo = Repositorio(tmp_path / "t.db")
    motor = Motor(cfg, FonteArquivo(Path(__file__).parent / "fixtures"), repo,
                  {"teams": Console(io.StringIO())}, raiz=RAIZ)
    rodada = motor.rodar(cobrar=False)
    rel = montar(cfg, rodada.sinais, repo.acoes_em_aberto())

    html = _html(Mensagem(rel.assunto, rel.corpo_md, []))

    assert "<h1>Nitron — acompanhamento" in html
    assert "**" not in html, "negrito cru chegando no leitor"
    assert "\n# " not in html and html.count("<p>#") == 0
    repo.fechar()
