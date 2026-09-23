"""O Renato é a parte não-determinística do sistema, e por isso a parte que
mais precisa de teste em volta: o que se verifica aqui não é o que o modelo
responde — isso muda —, e sim que o material chega inteiro até ele, que o
prefixo caro fica marcado para cache, e que a falha dele nunca derruba a
cobrança."""

import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nitronceo.analista import (  # noqa: E402
    Renato,
    SemCredencial,
    montar_dossie,
)
from nitronceo.config import RAIZ, carregar  # noqa: E402
from nitronceo.motor import Motor  # noqa: E402
from nitronceo.notificadores import Console  # noqa: E402
from nitronceo.repositorio import Repositorio  # noqa: E402
from nitronceo.sankhya import FonteArquivo  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


class _Uso:
    input_tokens = 900
    cache_read_input_tokens = 41000
    output_tokens = 700


class _Bloco:
    type = "text"

    def __init__(self, texto):
        self.text = texto


class _Resposta:
    def __init__(self, texto):
        self.content = [_Bloco(texto)]
        self.usage = _Uso()


class _Fluxo:
    def __init__(self, resposta):
        self._resposta = resposta

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def get_final_message(self):
        return self._resposta


class ClienteFalso:
    """Guarda a chamada para inspeção e devolve um texto fixo."""

    def __init__(self, texto="## O que mudou\nNada saiu da linha.", erro=None):
        self.texto = texto
        self.erro = erro
        self.chamadas = []
        self.messages = self

    def stream(self, **kwargs):
        self.chamadas.append(kwargs)
        if self.erro:
            raise self.erro
        return _Fluxo(_Resposta(self.texto))


def _rodada(tmp_path):
    cfg = carregar()
    repo = Repositorio(tmp_path / "t.db")
    saida = io.StringIO()
    motor = Motor(
        cfg, FonteArquivo(FIXTURES), repo,
        {"teams": Console(saida), "email": Console(saida)}, raiz=RAIZ,
    )
    return cfg, repo, motor.rodar(cobrar=False)


# ------------------------------------------------------------------ dossiê


def test_dossie_traz_todos_os_sinais_com_dono_e_detalhe(tmp_path):
    cfg, repo, rodada = _rodada(tmp_path)
    texto = montar_dossie(rodada.sinais, repo.acoes_em_aberto(), cfg)

    assert "# Dossiê da rodada" in texto
    # um sinal por linha, os 37 presentes
    assert texto.count("\n- ") >= 37
    # o nível vem em rótulo legível, não no enum
    assert "-> CRÍTICO" in texto
    # o dono vem por nome, que é como o CEO pensa nele
    assert "Expedição e Forla Silva" in texto
    # o contexto numérico sobe junto: é nele que estão os nomes próprios
    assert "PCT_COBERTURA=2.6" in texto
    repo.fechar()


def test_dossie_marca_sombra_para_o_modelo_nao_cobrar_a_partir_dela(tmp_path):
    cfg, repo, rodada = _rodada(tmp_path)
    texto = montar_dossie(rodada.sinais, repo.acoes_em_aberto(), cfg)

    for linha in texto.splitlines():
        if "Performance por representante" in linha:
            assert "SOMBRA" in linha
            break
    else:
        pytest.fail("o KPI em sombra sumiu do dossiê")
    repo.fechar()


def test_dossie_registra_reincidencia_so_a_partir_de_tres_dias(tmp_path):
    cfg, repo, rodada = _rodada(tmp_path)
    historico = {"setup_maquinas": 5, "devolucoes": 2}
    texto = montar_dossie(rodada.sinais, [], cfg, historico)

    assert "setup_maquinas: 5 dias" in texto
    assert "devolucoes" not in texto.split("## Cobranças")[0].split(
        "## Reincidência"
    )[-1]
    repo.fechar()


# ------------------------------------------------------------ conhecimento


def test_conhecimento_carrega_persona_e_marca_o_cache():
    renato = Renato(carregar(), cliente=ClienteFalso())
    blocos = renato.conhecimento()

    assert len(blocos) >= 3
    # a persona vem primeiro: é ela que define quem está falando
    assert "Renato é o gestor do Grupo Nitron" in blocos[0]["text"]
    # os achados de dados entram inteiros — são as armadilhas conhecidas
    assert any("CODLOCAL 1080000" in b["text"] for b in blocos)
    # o marcador de cache fica no último bloco, cobrindo todo o prefixo
    assert blocos[-1]["cache_control"] == {"type": "ephemeral"}
    assert not any("cache_control" in b for b in blocos[:-1])


def test_conhecimento_traz_os_papeis_vigentes_do_yaml():
    renato = Renato(carregar(), cliente=ClienteFalso())
    quadro = renato.conhecimento()[-1]["text"]

    assert "cristiane.alves@nitron.com.br" in quadro
    assert "escala para: ceo" in quadro
    assert "em sombra" in quadro


# ---------------------------------------------------------------- chamada


def test_leitura_usa_opus_com_pensamento_adaptativo(tmp_path):
    cfg, repo, rodada = _rodada(tmp_path)
    cliente = ClienteFalso()
    leitura = Renato(cfg, cliente=cliente).leitura(rodada.sinais, [], {})

    chamada = cliente.chamadas[0]
    assert chamada["model"] == "claude-opus-5"
    assert chamada["thinking"] == {"type": "adaptive"}
    assert chamada["output_config"] == {"effort": "high"}
    # o dossiê vai na mensagem, não no sistema: ele muda a cada rodada e
    # invalidaria o cache do prefixo se subisse junto com a persona.
    assert "Dossiê da rodada" in chamada["messages"][0]["content"]
    assert not any("Dossiê" in b["text"] for b in chamada["system"])

    assert leitura.tokens_cache == 41000
    assert "41000/41900" in leitura.custo_em_cache
    repo.fechar()


def test_sem_credencial_nao_e_tratado_como_bug():
    renato = Renato(carregar())
    with pytest.raises(SemCredencial):
        _ = renato.cliente


# ------------------------------------------------- redator dentro do motor


def _motor_com_redator(tmp_path, redator):
    cfg = carregar()
    repo = Repositorio(tmp_path / "t.db")
    saida = io.StringIO()
    console = Console(saida)
    motor = Motor(
        cfg, FonteArquivo(FIXTURES), repo,
        {"teams": console, "email": console}, raiz=RAIZ, redator=redator,
    )
    return motor, repo, saida


def test_texto_do_renato_entra_na_cobranca_com_o_rodape_do_sistema(tmp_path):
    class Redator:
        def texto_cobranca(self, acao, sinal, kpi):
            return "Corpo escrito pelo Renato."

    motor, repo, saida = _motor_com_redator(tmp_path, Redator())
    motor.rodar(cobrar=False)
    texto = saida.getvalue()

    assert "Corpo escrito pelo Renato." in texto
    # prazo, link, token e procedência são fato do sistema: não podem
    # depender de o modelo ter lembrado deles.
    assert "Responda neste e-mail" in texto
    assert "Base do número:" in texto
    # o token do assunto é o que amarra a resposta de volta na ação
    assert "[NTR-" in texto
    repo.fechar()


def test_redator_que_falha_nao_impede_a_cobranca(tmp_path):
    class RedatorQuebrado:
        def texto_cobranca(self, acao, sinal, kpi):
            raise RuntimeError("limite de taxa atingido")

    motor, repo, saida = _motor_com_redator(tmp_path, RedatorQuebrado())
    rodada = motor.rodar(cobrar=False)

    assert rodada.acoes_novas, "a cobrança tinha que sair assim mesmo"
    assert "O que preciso de você" in saida.getvalue()  # voltou ao template
    assert rodada.falhas_de_redacao
    assert "limite de taxa" in rodada.falhas_de_redacao[0][1]
    repo.fechar()


def test_redator_vazio_tambem_cai_no_template(tmp_path):
    class RedatorMudo:
        def texto_cobranca(self, acao, sinal, kpi):
            return ""

    motor, repo, saida = _motor_com_redator(tmp_path, RedatorMudo())
    motor.rodar(cobrar=False)

    assert "O que preciso de você" in saida.getvalue()
    repo.fechar()


# --------------------------------------------------- leitura dentro do painel


def test_painel_mostra_a_leitura_separada_dos_numeros(tmp_path):
    from nitronceo.analista import Leitura
    from nitronceo.dashboard import gerar

    cfg, repo, rodada = _rodada(tmp_path)
    leitura = Leitura(
        texto=(
            "## O que mudou\n"
            "A INJETORA 19 <piorou> em setup **e** em ciclo.\n"
            "- setup mediano em 47 min\n"
            "- ciclo 28% acima do padrão"
        ),
        modelo="claude-opus-5",
    )
    html = gerar(cfg, rodada.sinais, repo.acoes_em_aberto(), 0, 0, leitura)

    assert "Leitura do Renato" in html
    assert "<h3>O que mudou</h3>" in html
    assert "<strong>e</strong>" in html
    assert "<li>setup mediano em 47 min</li>" in html
    # texto vindo do modelo é escapado antes de virar HTML
    assert "&lt;piorou&gt;" in html
    # e o leitor precisa saber onde termina a apuração e começa a opinião
    assert "a leitura é dele" in html
    repo.fechar()


def test_painel_sem_leitura_continua_igual(tmp_path):
    from nitronceo.dashboard import gerar

    cfg, repo, rodada = _rodada(tmp_path)
    html = gerar(cfg, rodada.sinais, repo.acoes_em_aberto())

    assert "Leitura do Renato" not in html
    assert "Pipeline de gestão" in html
    repo.fechar()
