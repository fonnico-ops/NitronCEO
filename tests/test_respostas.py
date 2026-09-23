"""Quando a cobrança sai do e-mail do CEO, a pessoa responde no e-mail.

O risco que estes testes cercam é o pior do sistema: alguém responde, a
resposta fica na caixa de entrada, e a escada continua cobrando quem já
se manifestou. Basta acontecer duas vezes para o time aprender a ignorar
a cobrança."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nitronceo.acoes import Acao, Estado  # noqa: E402
from nitronceo.avaliador import Nivel  # noqa: E402
from nitronceo.repositorio import Repositorio  # noqa: E402
from nitronceo.respostas import (  # noqa: E402
    LeitorDeCaixa,
    acao_do_assunto,
    encerra,
    limpar,
    marcar,
)

ACAO_ID = "a1b2c3d4e5f6"


def _acao(prazo_horas=-2):
    agora = datetime.now()
    return Acao(
        id=ACAO_ID, kpi_id="emissao_ntrlog", titulo="NTR Log emitiu 2.6%",
        passos=["conciliar o mês"], dono="logistica", nivel=Nivel.CRITICO,
        valor=2.6, unidade="percentual", estado=Estado.ABERTA,
        criada_em=agora - timedelta(hours=12),
        prazo=agora + timedelta(hours=prazo_horas), contexto={},
    )


# ------------------------------------------------------------------ token


def test_token_sobrevive_ao_RE_do_outlook():
    assunto = f"⏰ COBRANÇA {marcar(ACAO_ID)}: NTR Log emitiu 2.6%"
    resposta = f"RE: {assunto}"
    encaminhado = f"ENC: RES: {assunto}"

    assert acao_do_assunto(assunto) == "a1b2c3d4"
    assert acao_do_assunto(resposta) == "a1b2c3d4"
    assert acao_do_assunto(encaminhado) == "a1b2c3d4"


def test_assunto_sem_token_nao_vira_resposta():
    # Uma nota fiscal ou pedido no assunto não pode ser confundido com ação.
    assert acao_do_assunto("RE: Pedido 123456 - urgente") is None
    assert acao_do_assunto("") is None


# ------------------------------------------------------------------ corpo


def test_corta_a_cobranca_citada_embaixo_da_resposta():
    bruto = (
        "<p>Conciliei com a NTR. Faltam 18 notas de agosto.</p>"
        "<div>De: Renato Fonseca &lt;renato.fonseca@nitron.com.br&gt;<br>"
        "Enviada em: segunda<br>NTR Log emitiu apenas 2.6% do frete...</div>"
    )
    texto = limpar(bruto)

    assert texto == "Conciliei com a NTR. Faltam 18 notas de agosto."
    assert "2.6%" not in texto, "a cobrança citada não é resposta"


def test_resposta_sem_citacao_volta_inteira():
    assert limpar("Já resolvi com o Forla.") == "Já resolvi com o Forla."


# -------------------------------------------------------------- encerrar


def test_so_encerra_quem_comeca_com_RESOLVIDO():
    assert encerra("RESOLVIDO. As 18 notas foram emitidas hoje.")
    assert encerra("resolvido")
    # a palavra no meio da frase não encerra — e a negativa muito menos
    assert not encerra("Isso não está resolvido ainda")
    assert not encerra("Vou ver amanhã")
    assert not encerra("")


# ------------------------------------------------------------ leitura fim


class GraphFalso:
    def __init__(self, mensagens):
        self.mensagens = mensagens
        self.pedidos = []

    def get(self, caminho):
        self.pedidos.append(caminho)
        return {"value": self.mensagens}


def _msg(assunto, corpo, de="forla.silva@nitron.com.br", mid="m1"):
    return {
        "id": mid, "internetMessageId": mid, "subject": assunto,
        "from": {"emailAddress": {"address": de}},
        "body": {"content": corpo},
        "receivedDateTime": datetime.now().isoformat(),
    }


def _repo(tmp_path):
    repo = Repositorio(tmp_path / "t.db")
    repo.salvar_acao(_acao())
    return repo


def test_resposta_parcial_registra_e_nao_encerra(tmp_path):
    repo = _repo(tmp_path)
    graph = GraphFalso([
        _msg(f"RE: ⏰ COBRANÇA {marcar(ACAO_ID)}: NTR Log",
             "Falei com a NTR, me retornam amanhã.")
    ])

    lidas = LeitorDeCaixa(graph, "renato.fonseca@nitron.com.br", repo).ler()

    assert len(lidas) == 1
    assert lidas[0].encerra is False
    # a ação continua aberta: "me retornam amanhã" não é solução
    assert repo.buscar_acao(ACAO_ID).estado is Estado.ABERTA
    # mas segura o lembrete, que foi o que a cobrança prometeu
    assert repo.respondeu_nas_ultimas(ACAO_ID, 24)
    repo.fechar()


def test_RESOLVIDO_encerra_a_cobranca(tmp_path):
    repo = _repo(tmp_path)
    graph = GraphFalso([
        _msg(f"RE: ⏰ COBRANÇA {marcar(ACAO_ID)}: NTR Log",
             "RESOLVIDO. As 18 notas de agosto saíram hoje.")
    ])

    lidas = LeitorDeCaixa(graph, "renato.fonseca@nitron.com.br", repo).ler()

    assert lidas[0].encerra is True
    assert repo.buscar_acao(ACAO_ID).estado is Estado.RESPONDIDA
    repo.fechar()


def test_mesma_resposta_nao_e_processada_duas_vezes(tmp_path):
    # A caixa é varrida inteira a cada rodada; sem dedupe por Message-Id a
    # mesma resposta entraria de novo toda vez.
    repo = _repo(tmp_path)
    graph = GraphFalso([
        _msg(f"RE: {marcar(ACAO_ID)} NTR Log", "Conciliando.", mid="mesmo-id")
    ])
    leitor = LeitorDeCaixa(graph, "renato.fonseca@nitron.com.br", repo)

    assert len(leitor.ler()) == 1
    assert len(leitor.ler()) == 0
    assert len(repo.respostas_de(ACAO_ID)) == 1
    repo.fechar()


def test_a_propria_cobranca_na_caixa_nao_e_resposta(tmp_path):
    # Sent Items e auto-encaminhamentos devolvem o e-mail do próprio CEO.
    repo = _repo(tmp_path)
    graph = GraphFalso([
        _msg(f"⏰ COBRANÇA {marcar(ACAO_ID)}: NTR Log", "Preciso de você...",
             de="renato.fonseca@nitron.com.br")
    ])

    assert LeitorDeCaixa(graph, "renato.fonseca@nitron.com.br", repo).ler() == []
    repo.fechar()


def test_resposta_para_acao_desconhecida_e_ignorada(tmp_path):
    repo = _repo(tmp_path)
    graph = GraphFalso([_msg("RE: [NTR-ffffffff] outra coisa", "oi")])

    assert LeitorDeCaixa(graph, "renato.fonseca@nitron.com.br", repo).ler() == []
    repo.fechar()
