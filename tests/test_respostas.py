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


def test_message_id_com_underline_nao_confunde_o_dedupe(tmp_path):
    """Message-Id do Exchange costuma ter `_`.

    Se o dedupe usasse LIKE, o `_` viraria coringa e duas respostas
    diferentes passariam por uma só — a segunda sumiria em silêncio.
    """
    repo = _repo(tmp_path)
    assert not repo.resposta_ja_lida("<AB_CD@nitron.com.br>")
    repo.gravar_resposta_email(
        "<AB_CD@nitron.com.br>", ACAO_ID, "x@y.z", "oi", False, datetime.now()
    )
    assert repo.resposta_ja_lida("<AB_CD@nitron.com.br>")
    # o `_` não pode casar com outro caractere
    assert not repo.resposta_ja_lida("<ABXCD@nitron.com.br>")
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


# ------------------------------------------------- respostas pelo GHL


class GhlFalso:
    """Devolve o que o GHL devolve de verdade — inclusive o formato pobre
    das mensagens `inbound`, que foi onde a primeira versão deste leitor
    quebrou em silêncio."""

    def __init__(self, mensagens, detalhes=None):
        self.mensagens = mensagens
        self.detalhes = detalhes or {}
        self.pedidos = []
        self.detalhes_pedidos = []

    def exportar_emails(self, desde, limite=100):
        self.pedidos.append((desde, limite))
        return self.mensagens

    def email_detalhe(self, email_message_id):
        self.detalhes_pedidos.append(email_message_id)
        return self.detalhes[email_message_id]


def _ghl_inbound(assunto, mid="g1", email_id="e1"):
    """Uma resposta como a listagem do GHL realmente a devolve.

    Conferido na conversa wAzlDQHslpBokdbBYue2 em 23/09/2026: a mensagem
    `inbound` NÃO traz `subject`, `body` nem `from` na raiz. O assunto vem
    em `meta.email.subject`, e o resto só existe no detalhe do e-mail.
    """
    return {
        "id": mid, "direction": "inbound", "type": 3,
        "contactId": "AEfhFMAW6yLwumd6TvWE",
        "conversationId": "wAzlDQHslpBokdbBYue2",
        "contentType": "text/html",
        "dateAdded": datetime.now().isoformat(),
        "messageType": "TYPE_EMAIL",
        "meta": {"email": {"messageIds": [email_id], "direction": "inbound",
                           "subject": assunto}},
    }


def _ghl_detalhe(corpo, de="Forla Silva <forla.silva@nitron.com.br>"):
    return {"body": corpo, "from": de,
            "to": ["renato.fonseca@nitron.com.br"], "direction": "inbound"}


def _ghl_outbound(assunto, corpo, mid="o1"):
    """A cobrança, como o GHL a devolve: com body e subject na raiz."""
    return {
        "id": mid, "direction": "outbound", "type": 3, "subject": assunto,
        "body": corpo, "from": "Nitron <marketing@nitron.com.br>",
        "contactId": "AEfhFMAW6yLwumd6TvWE",
        "conversationId": "wAzlDQHslpBokdbBYue2",
        "dateAdded": datetime.now().isoformat(), "messageType": "TYPE_EMAIL",
        "meta": {"email": {"messageIds": ["x1"], "subject": assunto}},
    }


def test_resposta_na_conversa_do_ghl_para_a_escada(tmp_path):
    from nitronceo.respostas import LeitorDoGHL

    repo = _repo(tmp_path)
    ghl = GhlFalso(
        [_ghl_inbound(f"RE: 🚨 {marcar(ACAO_ID)} NTR Log emitiu 2.6%")],
        {"e1": _ghl_detalhe("Conciliei com a NTR, faltam 18 notas de agosto.")},
    )

    lidas = LeitorDoGHL(ghl, repo).ler()

    assert len(lidas) == 1
    # o assunto veio de meta.email e o corpo do detalhe do e-mail
    assert ghl.detalhes_pedidos == ["e1"]
    assert lidas[0].de == "forla.silva@nitron.com.br"
    assert lidas[0].encerra is False
    # não encerra, mas segura o lembrete — igual ao caminho do Outlook
    assert repo.buscar_acao(ACAO_ID).estado is Estado.ABERTA
    assert repo.respondeu_nas_ultimas(ACAO_ID, 24)
    repo.fechar()


def test_a_propria_cobranca_na_conversa_nao_e_resposta(tmp_path):
    # Na conversa do GHL a cobrança aparece ao lado da resposta. Sem o
    # corte por direction ela entraria como se fosse retorno da pessoa.
    from nitronceo.respostas import LeitorDoGHL

    repo = _repo(tmp_path)
    ghl = GhlFalso([
        _ghl_outbound(f"🚨 {marcar(ACAO_ID)} NTR Log emitiu 2.6%",
                      "O que preciso de você: conciliar o mês...")
    ])

    assert LeitorDoGHL(ghl, repo).ler() == []
    assert ghl.detalhes_pedidos == [], "nem vale buscar o detalhe da própria"
    repo.fechar()


def test_RESOLVIDO_pelo_ghl_encerra_igual_ao_email(tmp_path):
    from nitronceo.respostas import LeitorDoGHL

    repo = _repo(tmp_path)
    ghl = GhlFalso(
        [_ghl_inbound(f"RE: {marcar(ACAO_ID)} NTR Log")],
        {"e1": _ghl_detalhe("RESOLVIDO. As 18 notas saíram hoje.")},
    )

    lidas = LeitorDoGHL(ghl, repo).ler()

    assert lidas[0].encerra is True
    assert repo.buscar_acao(ACAO_ID).estado is Estado.RESPONDIDA
    repo.fechar()


def test_dedupe_vale_entre_os_dois_canais(tmp_path):
    """Uma mesma resposta não pode entrar duas vezes, nem por canais
    diferentes: a tabela é uma só, com o id da mensagem como chave."""
    from nitronceo.respostas import LeitorDoGHL

    repo = _repo(tmp_path)
    ghl = GhlFalso(
        [_ghl_inbound(f"RE: {marcar(ACAO_ID)} NTR Log", mid="mesmo")],
        {"e1": _ghl_detalhe("Conciliando.")},
    )
    leitor = LeitorDoGHL(ghl, repo)

    assert len(leitor.ler()) == 1
    assert len(leitor.ler()) == 0
    assert len(repo.respostas_de(ACAO_ID)) == 1
    repo.fechar()


def test_assunto_da_inbound_vem_de_meta_email():
    """A regressão que este teste trava.

    A primeira versão do leitor procurava `msg["subject"]`. Nas mensagens
    `inbound` reais esse campo não existe — o assunto está em
    `meta.email.subject`. O leitor encontrava zero respostas e não
    reclamava, que é exatamente o modo de falhar que ele existe para
    impedir.
    """
    from nitronceo.respostas import assunto_de

    inbound = _ghl_inbound("RES: RESSALVA DA NF 137973 // NITRONPLAST")
    assert "subject" not in inbound, "a inbound real não tem subject na raiz"
    assert assunto_de(inbound) == "RES: RESSALVA DA NF 137973 // NITRONPLAST"

    outbound = _ghl_outbound("Relatório de Logística", "corpo")
    assert assunto_de(outbound) == "Relatório de Logística"
    assert assunto_de({}) == ""


def test_detalhe_que_falha_nao_derruba_as_outras_respostas(tmp_path):
    from nitronceo.respostas import LeitorDoGHL

    class GhlQuebrado(GhlFalso):
        def email_detalhe(self, email_message_id):
            raise RuntimeError("500 do GHL")

    repo = _repo(tmp_path)
    ghl = GhlQuebrado([_ghl_inbound(f"RE: {marcar(ACAO_ID)} NTR Log")])

    lidas = LeitorDoGHL(ghl, repo).ler()

    # a resposta é registrada sem corpo — e sem corpo não encerra nada,
    # que é o comportamento seguro.
    assert len(lidas) == 1
    assert lidas[0].encerra is False
    assert repo.buscar_acao(ACAO_ID).estado is Estado.ABERTA
    repo.fechar()


# ------------------------------------------- respostas a uma mensagem-lote


def _lote_com(repo, quantas=3):
    """Cria N ações e as registra como um lote entregue."""
    from nitronceo.lote import marcar_lote

    agora = datetime.now()
    acoes = []
    for n in range(quantas):
        acao = Acao(
            id=f"{n}{'a' * 11}", kpi_id=f"kpi{n}", titulo=f"Ponto {n}",
            passos=["fazer"], dono="gerente_producao", nivel=Nivel.VERMELHO,
            valor=1.0, unidade="numero", estado=Estado.ABERTA,
            criada_em=agora - timedelta(hours=5),
            prazo=agora + timedelta(hours=10), contexto={},
        )
        repo.salvar_acao(acao)
        acoes.append(acao)
    token = marcar_lote(acoes)
    repo.registrar_lote(token, [a.id for a in acoes], "gerente_producao")
    return token, acoes


def _repo_vazio(tmp_path):
    return Repositorio(tmp_path / "lote.db")


def test_resposta_ao_lote_alcanca_todas_as_cobrancas(tmp_path):
    """Quem respondeu não pode ser cobrado de novo por detalhe de formato."""
    from nitronceo.respostas import LeitorDoGHL, marcar_lote as marcar_l

    repo = _repo_vazio(tmp_path)
    token, acoes = _lote_com(repo, 3)
    ghl = GhlFalso(
        [_ghl_inbound(f"RE: 🚨 {marcar_l(token)} Produção: 3 pontos")],
        {"e1": _ghl_detalhe("Vi os três. Começo pelo setup amanhã cedo.")},
    )

    lidas = LeitorDoGHL(ghl, repo).ler()

    assert len(lidas) == 3, "os três pontos recebem o retorno"
    assert all(not r.encerra for r in lidas), "nenhum encerra sem RESOLVIDO"
    for acao in acoes:
        assert repo.respondeu_nas_ultimas(acao.id, 24)
        assert repo.buscar_acao(acao.id).estado is Estado.ABERTA
    repo.fechar()


def test_RESOLVIDO_com_token_encerra_so_aquele_ponto(tmp_path):
    from nitronceo.respostas import LeitorDoGHL, marcar_lote as marcar_l

    repo = _repo_vazio(tmp_path)
    token, acoes = _lote_com(repo, 3)
    alvo = acoes[1]
    ghl = GhlFalso(
        [_ghl_inbound(f"RE: {marcar_l(token)} Produção: 3 pontos")],
        {"e1": _ghl_detalhe(
            f"RESOLVIDO [NTR-{alvo.id[:8]}] — fechei as OS. Os outros dois "
            "seguem comigo."
        )},
    )

    LeitorDoGHL(ghl, repo).ler()

    assert repo.buscar_acao(alvo.id).estado is Estado.RESPONDIDA
    for outro in (acoes[0], acoes[2]):
        assert repo.buscar_acao(outro.id).estado is Estado.ABERTA
    repo.fechar()


def test_RESOLVIDO_solto_nao_fecha_lote_de_varios(tmp_path):
    """Uma palavra não pode encerrar cinco assuntos que a pessoa talvez
    nem tenha lido."""
    from nitronceo.respostas import LeitorDoGHL, marcar_lote as marcar_l

    repo = _repo_vazio(tmp_path)
    token, acoes = _lote_com(repo, 3)
    ghl = GhlFalso(
        [_ghl_inbound(f"RE: {marcar_l(token)} Produção: 3 pontos")],
        {"e1": _ghl_detalhe("RESOLVIDO")},
    )

    LeitorDoGHL(ghl, repo).ler()

    for acao in acoes:
        assert repo.buscar_acao(acao.id).estado is Estado.ABERTA
        assert repo.respondeu_nas_ultimas(acao.id, 24), "mas segura o lembrete"
    repo.fechar()


def test_RESOLVIDO_solto_fecha_lote_de_um_so(tmp_path):
    # Com um ponto só não há ambiguidade a resolver.
    from nitronceo.respostas import LeitorDoGHL, marcar_lote as marcar_l

    repo = _repo_vazio(tmp_path)
    token, acoes = _lote_com(repo, 1)
    ghl = GhlFalso(
        [_ghl_inbound(f"RE: {marcar_l(token)} 1 ponto")],
        {"e1": _ghl_detalhe("RESOLVIDO. Já corrigi.")},
    )

    LeitorDoGHL(ghl, repo).ler()
    assert repo.buscar_acao(acoes[0].id).estado is Estado.RESPONDIDA
    repo.fechar()


def test_token_de_lote_nao_e_confundido_com_token_de_acao():
    from nitronceo.respostas import acao_do_assunto, lote_do_assunto

    assunto = "RE: 🚨 [NTR-L-a1b2c3d4] Produção: 5 pontos fora da linha"
    # sem a checagem de lote antes, o NTR- casaria e a resposta iria para
    # uma ação inexistente de id "l-a1b2c3"
    assert acao_do_assunto(assunto) is None
    assert lote_do_assunto(assunto) == "a1b2c3d4"

    individual = "RE: 🔴 [NTR-e0db1019] setup"
    assert acao_do_assunto(individual) == "e0db1019"
    assert lote_do_assunto(individual) is None
