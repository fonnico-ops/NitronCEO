"""O canal GHL é onde o erro mais caro do sistema pode acontecer.

A conta da Nitron já envia e-mail interno por ali — o domínio está
verificado e há fluxo ativo para `expedicao2@`. O que a base NÃO garante é
que um e-mail corporativo corresponda a um funcionário: em 23/09/2026,
`cristiane.alves@nitron.com.br` resolvia para "Cristiane ATLETICO CLUBE",
o contato do cliente COOPERCOTIA, com tags da Nina e seguido pela Nina
Financeiro.

Mandar a cobrança de Compras para aquele id levaria assunto interno para a
conversa de um cliente. Estes testes existem para que isso seja impossível,
não improvável."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nitronceo.config import Papel, Pessoa  # noqa: E402
from nitronceo.notificadores import Mensagem  # noqa: E402
from nitronceo.notificadores.ghl import ContatoInvalido, GoHighLevel  # noqa: E402

# O contato real da expedição, conferido na base: sem tags, limpo.
EXPEDICAO = {
    "id": "AEfhFMAW6yLwumd6TvWE", "firstName": "Rubi",
    "email": "expedicao2@nitron.com.br", "tags": [],
}
# O contato real onde o e-mail da Cristiane está: um CLIENTE.
COOPERCOTIA = {
    "id": "fhnAHYNbq8Inlzb56DQL", "firstName": "Cristiane",
    "lastName": "ATLETICO CLUBE", "email": "cristiane.alves@nitron.com.br",
    "tags": ["sankhya-cliente", "nina-conversa", "nina-lead-rep"],
}


class _Resp:
    def __init__(self, corpo, status=200):
        self._corpo = corpo
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._corpo


class SessaoFalsa:
    def __init__(self, por_id=None, por_email=None):
        self.por_id = por_id or {}
        self.por_email = por_email or {}
        self.enviados = []

    def get(self, url, params=None, **kw):  # noqa: ARG002
        if "/contacts/lookup" in url:
            return _Resp({"contacts": self.por_email.get(params["email"], [])})
        cid = url.rsplit("/", 1)[-1]
        if cid not in self.por_id:
            return _Resp({}, status=404)
        return _Resp({"contact": self.por_id[cid]})

    def post(self, url, json=None, **kw):  # noqa: ARG002
        self.enviados.append(json)
        return _Resp({"conversationId": "c1"})


def _ghl(por_id=None, por_email=None):
    sessao = SessaoFalsa(por_id, por_email)
    return GoHighLevel(
        token="t", location="l",
        remetente="renato.fonseca@nitron.com.br", sessao=sessao,
    ), sessao


def _msg(*contatos):
    return Mensagem(
        assunto="⏰ COBRANÇA [NTR-a1b2c3d4]: gastos acima da média",
        corpo_md="**Gastos fora do padrão**\n\n- confira as naturezas",
        destinatarios=["cristiane.alves@nitron.com.br"],
        contatos_ghl=list(contatos),
    )


# ------------------------------------------------------- a trava principal


def test_contato_de_cliente_nunca_recebe_cobranca_interna():
    ghl, sessao = _ghl(por_id={COOPERCOTIA["id"]: COOPERCOTIA})

    with pytest.raises(ContatoInvalido, match="CLIENTE"):
        ghl.conferir(COOPERCOTIA["id"])

    assert ghl.enviar(_msg(COOPERCOTIA["id"])) is False
    assert not sessao.enviados, "nada pode ter saído para a conversa do cliente"


def test_a_tag_e_conferida_no_envio_e_nao_so_na_declaracao():
    # Um contato interno pode ganhar a tag sankhya-cliente numa sincronização
    # depois de já estar declarado no pessoas.yaml.
    virou_cliente = {**EXPEDICAO, "tags": ["sankhya-cliente"]}
    ghl, sessao = _ghl(por_id={EXPEDICAO["id"]: virou_cliente})

    assert ghl.enviar(_msg(EXPEDICAO["id"])) is False
    assert not sessao.enviados


def test_contato_interno_limpo_recebe():
    ghl, sessao = _ghl(por_id={EXPEDICAO["id"]: EXPEDICAO})

    assert ghl.enviar(_msg(EXPEDICAO["id"])) is True
    enviado = sessao.enviados[0]
    assert enviado["type"] == "Email"
    assert enviado["contactId"] == EXPEDICAO["id"]
    assert enviado["emailFrom"] == "renato.fonseca@nitron.com.br"
    assert "[NTR-a1b2c3d4]" in enviado["subject"]
    assert "<li>confira as naturezas</li>" in enviado["html"]


def test_sem_contato_declarado_o_canal_cala_em_vez_de_adivinhar():
    # A pessoa segue sendo cobrada por e-mail e Teams. O GHL não tenta
    # descobrir o contato sozinho — foi exatamente assim que a cobrança de
    # Compras quase foi para o cliente Coopercotia.
    ghl, sessao = _ghl()

    assert ghl.enviar(_msg()) is True
    assert not sessao.enviados


def test_contato_declarado_que_sumiu_da_base_e_erro_explicito():
    ghl, _ = _ghl(por_id={})
    with pytest.raises(ContatoInvalido, match="não existe mais"):
        ghl.conferir("id-que-foi-apagado")


# ------------------------------------------------------------ diagnóstico


def test_diagnostico_separa_quem_da_para_cobrar_de_quem_nao_da():
    ghl, _ = _ghl(por_email={
        "expedicao2@nitron.com.br": [EXPEDICAO],
        "cristiane.alves@nitron.com.br": [COOPERCOTIA],
        "anderson.lourenco@nitron.com.br": [],
    })

    laudo = {d["email"]: d for d in ghl.diagnosticar([
        "expedicao2@nitron.com.br",
        "cristiane.alves@nitron.com.br",
        "anderson.lourenco@nitron.com.br",
    ])}

    assert laudo["expedicao2@nitron.com.br"]["contato_id"] == EXPEDICAO["id"]
    # a Cristiane não ganha id nenhum, e o motivo fica explícito no laudo
    assert laudo["cristiane.alves@nitron.com.br"]["contato_id"] is None
    colisao = laudo["cristiane.alves@nitron.com.br"]["de_cliente"][0]
    assert colisao["nome"] == "Cristiane ATLETICO CLUBE"
    assert "sankhya-cliente" in colisao["tags"]
    # quem não existe na base simplesmente não tem contato
    assert laudo["anderson.lourenco@nitron.com.br"]["achados"] == 0


# ------------------------------------------------------ ligação com o papel


def test_papel_so_entrega_contatos_declarados():
    papel = Papel(
        chave="logistica", nome="Expedição",
        pessoas=[
            Pessoa("Expedição", "expedicao2@nitron.com.br",
                   ghl_contato=EXPEDICAO["id"]),
            Pessoa("Forla Silva", "forla.silva@nitron.com.br"),
        ],
    )

    assert papel.emails == [
        "expedicao2@nitron.com.br", "forla.silva@nitron.com.br"
    ]
    # o Forla ainda não tem contato: não entra na lista do GHL, e continua
    # sendo cobrado por e-mail como todo mundo.
    assert papel.contatos_ghl == [EXPEDICAO["id"]]


# --------------------------------------------------- o remetente e o CEO


def test_remetente_padrao_e_o_ceo():
    ghl, _ = _ghl()
    assert ghl.remetente == "renato.fonseca@nitron.com.br"


def test_lead_de_campanha_tambem_e_bloqueado():
    """O contato do próprio CEO tem o e-mail certo e a conversa errada.

    bnKA8BWCRaTeiBC2rjRs carrega `lead-puro`, está atribuído à Nina
    Financeiro e traz campos de um anúncio de Instagram. Escalada de
    cobrança não entra numa conversa de campanha.
    """
    lead = {
        "id": "bnKA8BWCRaTeiBC2rjRs", "firstName": "Renato",
        "email": "renato.fonseca@nitron.com.br", "tags": ["lead-puro"],
    }
    ghl, sessao = _ghl(por_id={lead["id"]: lead})

    assert ghl.enviar(_msg(lead["id"])) is False
    assert not sessao.enviados


def test_config_real_nao_declara_contato_poluido():
    """Trava de regressão sobre o pessoas.yaml de verdade.

    O CEO e a Compras não podem ganhar `ghl_contato` sem que alguém tenha
    resolvido a colisão — declarar qualquer um dos dois hoje mandaria
    cobrança para a conversa de um lead ou de um cliente.
    """
    from nitronceo.config import carregar

    cfg = carregar()
    assert cfg.papel("ceo").contatos_ghl == []
    assert cfg.papel("compras").contatos_ghl == []
    # e os resolvidos estão declarados
    assert cfg.papel("logistica").contatos_ghl == [
        "AEfhFMAW6yLwumd6TvWE", "FnMLfa8eSdSz8GmV9spD"
    ]
    assert cfg.papel("ecommerce").contatos_ghl == ["7OD3lOe5yue8AJUYAJvo"]
