"""O GHL é o canal com o risco mais concreto do sistema: a location da
Nitron tem clientes cadastrados, não funcionários, e uma busca por
`cristiane.alves@nitron.com.br` lá resolve hoje para um contato de cliente.

Os testes abaixo existem para garantir que esse erro não é possível: o
notificador tem que recusar o envio em vez de acertar o alvo errado."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nitronceo.notificadores import Mensagem  # noqa: E402
from nitronceo.notificadores.ghl import ContatoAmbiguo, GoHighLevel  # noqa: E402


class _Resp:
    def __init__(self, corpo):
        self._corpo = corpo

    def raise_for_status(self):
        return None

    def json(self):
        return self._corpo


class SessaoFalsa:
    def __init__(self, contatos):
        self.contatos = contatos
        self.enviados = []

    def get(self, url, **kw):  # noqa: ARG002
        return _Resp({"contacts": self.contatos})

    def post(self, url, json=None, **kw):  # noqa: ARG002
        self.enviados.append(json)
        return _Resp({"conversationId": "c1"})


def _ghl(contatos):
    sessao = SessaoFalsa(contatos)
    return GoHighLevel(
        token="t", location="l", remetente="ceo-bot@nitron.com.br", sessao=sessao
    ), sessao


MSG = Mensagem(
    assunto="⏰ COBRANÇA",
    corpo_md="**Gastos acima da média**\n\n- confira as naturezas",
    destinatarios=["cristiane.alves@nitron.com.br"],
)


def test_contato_de_cliente_com_o_email_certo_nao_recebe_cobranca_interna():
    # Este é o caso real: o e-mail bate, mas o contato é de cliente.
    ghl, sessao = _ghl([
        {
            "id": "abc",
            "email": "cristiane.alves@nitron.com.br",
            "contactName": "Cristiane ATLETICO CLUBE",
            "tags": ["nina-conversa", "nina-lead-rep"],
        }
    ])

    with pytest.raises(ContatoAmbiguo, match="nitron-interno"):
        ghl.contato("cristiane.alves@nitron.com.br")

    assert ghl.enviar(MSG) is False
    assert not sessao.enviados, "nada pode ter saído"


def test_resultado_apenas_parecido_e_descartado():
    # A busca do GHL é frouxa: devolve semelhantes. Semelhante não serve.
    ghl, sessao = _ghl([
        {"id": "x", "email": "cristiane@outraempresa.com.br",
         "contactName": "Cristiane Souza", "tags": ["nitron-interno"]}
    ])

    with pytest.raises(ContatoAmbiguo, match="Nenhum contato"):
        ghl.contato("cristiane.alves@nitron.com.br")
    assert not sessao.enviados


def test_contato_interno_marcado_recebe():
    ghl, sessao = _ghl([
        {"id": "ok1", "email": "cristiane.alves@nitron.com.br",
         "contactName": "Cristiane Alves", "tags": ["nitron-interno"]}
    ])

    assert ghl.enviar(MSG) is True
    enviado = sessao.enviados[0]
    assert enviado["type"] == "Email"
    assert enviado["contactId"] == "ok1"
    assert enviado["emailFrom"] == "ceo-bot@nitron.com.br"
    assert "<li>confira as naturezas</li>" in enviado["html"]


def test_duplicata_interna_nao_e_resolvida_no_chute():
    ghl, _ = _ghl([
        {"id": "a", "email": "forla.silva@nitron.com.br",
         "contactName": "Forla", "tags": ["nitron-interno"]},
        {"id": "b", "email": "forla.silva@nitron.com.br",
         "contactName": "Forla S.", "tags": ["nitron-interno"]},
    ])

    with pytest.raises(ContatoAmbiguo, match="Deduplique"):
        ghl.contato("forla.silva@nitron.com.br")
