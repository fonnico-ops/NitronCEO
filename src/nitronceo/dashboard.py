"""Gera o dashboard do pipeline de gestão como um arquivo HTML.

O dashboard não é um relatório do que aconteceu — é o estado do pipeline:
cada KPI medido, o julgamento, a ação que nasceu dele, de quem está a bola e
há quanto tempo.

Duas coisas acontecem na página, não só nela:
  - cada etapa do pipeline abre e mostra QUAIS indicadores estão nela;
  - cada cobrança abre o que foi pedido e recebe a RESPOSTA de quem foi
    cobrado, que fica gravada e aparece para todo mundo que abrir depois.

A resposta vive na base do artifact (capacidade `db`), não no HTML: quem
responde normalmente não é quem publica a página, e o texto precisa
sobreviver à próxima republicação. O `nitronceo importar` traz essas
respostas de volta para o banco local e encerra a cobrança.

A paleta de status foi validada nos dois temas com o validador do skill
dataviz. Nenhum estado é comunicado só por cor: todos carregam rótulo em
texto e espessura de faixa própria.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .acoes import Acao, Estado, formatar
from .avaliador import Nivel, Sinal
from .config import Config

AREAS = [
    ("comercial", "Comercial"),
    ("logistica", "Logística"),
    ("qualidade", "Qualidade"),
    ("producao", "Produção"),
    ("pcp", "PCP"),
    ("financeiro", "Financeiro"),
]

ROTULO_NIVEL = {
    Nivel.VERDE: "no alvo",
    Nivel.AMARELO: "atenção",
    Nivel.VERMELHO: "cobrando",
    Nivel.CRITICO: "crítico",
}

ROTULO_AREA = dict(AREAS)


@dataclass
class Etapa:
    chave: str
    nome: str
    nota: str
    explica: str
    itens: list[dict[str, str]] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.itens)


def _e(txt: Any) -> str:
    return html.escape(str(txt), quote=True)


def _valor(sinal: Sinal) -> str:
    if sinal.valor is None:
        return "—"
    txt = formatar(sinal.valor, sinal.unidade)
    if sinal.unidade == "reais":
        return f"R$ {txt}"
    if sinal.unidade == "percentual":
        return f"{txt}%"
    return txt


def _item(sinal: Sinal, por_id: dict[str, Any], cfg: Config) -> dict[str, str]:
    kpi = por_id[sinal.kpi_id]
    return {
        "titulo": sinal.titulo,
        "valor": _valor(sinal),
        "area": ROTULO_AREA.get(kpi["area"], kpi["area"]),
        "dono": cfg.papel(kpi["dono"]).nome,
        "nivel": sinal.nivel.value,
        "modo": sinal.modo,
    }


def _etapas(sinais: list[Sinal], acoes: list[Acao], por_id: dict[str, Any],
            cfg: Config) -> list[Etapa]:
    fora = [s for s in sinais if s.nivel.cobra and not s.erro]
    cobravel = [s for s in fora if s.notificavel]
    sombra = [s for s in fora if not s.notificavel]

    def de_acao(a: Acao) -> dict[str, str]:
        return {
            "titulo": a.titulo,
            "valor": f"prazo {a.prazo:%d/%m %H:%M}",
            "area": ROTULO_AREA.get(por_id[a.kpi_id]["area"], ""),
            "dono": cfg.papel(a.dono).nome,
            "nivel": a.nivel.value,
            "modo": "ativo",
        }

    return [
        Etapa("medido", "Medido", "KPIs na matriz",
              "Todo indicador da matriz foi consultado no Sankhya nesta rodada.",
              [_item(s, por_id, cfg) for s in sinais]),
        Etapa("fora", "Fora da linha", "vermelho ou crítico",
              "Cruzaram o limiar acordado com a área dona. Ainda não é cobrança: "
              "é julgamento.",
              [_item(s, por_id, cfg) for s in fora]),
        Etapa("cobravel", "Cobrável", f"{len(sombra)} em sombra",
              "Fora da linha E com dado confiável o bastante para cobrar alguém. "
              "Os que ficaram de fora estão em sombra — o dado de origem ainda "
              "não sustenta a cobrança.",
              [_item(s, por_id, cfg) for s in cobravel]),
        Etapa("acao", "Ação aberta", "com dono e prazo",
              "Viraram pedido concreto: o que fazer, quem faz, até quando.",
              [de_acao(a) for a in acoes]),
        Etapa("cobrado", "Cobrado", "prazo vencido",
              "O prazo passou sem resposta e o dono recebeu o lembrete.",
              [de_acao(a) for a in acoes if a.escalonamentos >= 1]),
        Etapa("escalado", "Escalado", "subiu de nível",
              "Subiu para o gestor do dono e, se continuar sem resposta, "
              "para o CEO.",
              [de_acao(a) for a in acoes if a.escalonamentos >= 2]),
        Etapa("respondido", "Respondido", "bola devolvida",
              "O dono respondeu na página. A cobrança para aqui.",
              [de_acao(a) for a in acoes if a.estado is Estado.RESPONDIDA]),
    ]


def _barra_status(sinais: list[Sinal]) -> str:
    ordem = [Nivel.CRITICO, Nivel.VERMELHO, Nivel.AMARELO, Nivel.VERDE]
    contagem = {n: sum(1 for s in sinais if s.nivel is n) for n in ordem}
    total = sum(contagem.values()) or 1
    segmentos = []
    for n in ordem:
        if not contagem[n]:
            continue
        pct = contagem[n] / total * 100
        segmentos.append(
            f'<div class="seg seg--{n.value}" style="flex:{pct:.4f}">'
            f'<span class="seg__n">{contagem[n]}</span></div>'
        )
    legenda = " ".join(
        f'<span class="chave"><i class="ponto ponto--{n.value}"></i>'
        f'{_e(ROTULO_NIVEL[n])} <b>{contagem[n]}</b></span>'
        for n in ordem if contagem[n]
    )
    return (
        f'<div class="barra" role="img" aria-label="Distribuição dos KPIs por '
        f'situação">{"".join(segmentos)}</div><div class="chaves">{legenda}</div>'
    )


def _grafico_gap(titulo: str, rotulos: list[str], valores: list[float],
                 fonte: str) -> str:
    """Barras horizontais de uma série. Rótulo direto em cada barra."""
    escala = max((abs(v) for v in valores), default=1) or 1
    linhas = []
    for rotulo, valor in zip(rotulos, valores):
        largura = abs(valor) / escala * 100
        classe = "barh--neg" if valor < 0 else "barh--pos"
        linhas.append(
            f'<div class="barh__linha">'
            f'<span class="barh__rot">{_e(rotulo)}</span>'
            f'<span class="barh__trilho">'
            f'<span class="barh__fill {classe}" style="width:{largura:.2f}%"></span>'
            f"</span>"
            f'<span class="barh__val">R$ {formatar(valor, "reais")}</span>'
            f"</div>"
        )
    return (
        f'<figure class="grafico"><figcaption class="grafico__tit">{_e(titulo)}'
        f"</figcaption>{''.join(linhas)}"
        f'<p class="grafico__fonte">{_e(fonte)}</p></figure>'
    )


def _linha_kpi(sinal: Sinal, kpi: dict[str, Any], cfg: Config,
               acao: Acao | None) -> str:
    papel = cfg.papel(kpi["dono"])
    sombra = (' <span class="tag tag--sombra">sombra</span>'
              if sinal.modo == "sombra" else "")
    if acao:
        marca = (f'<a class="tag tag--acao" href="#cob-{_e(acao.id)}">'
                 f'ação {_e(acao.id[:6])} ›</a>')
    elif sinal.erro:
        marca = '<span class="tag tag--erro">sem medição</span>'
    else:
        marca = ""
    detalhe = sinal.linha.get("LISTA") or ""
    detalhe_html = (
        f'<p class="kpi__detalhe">{_e(detalhe)}</p>'
        if detalhe and sinal.nivel.cobra else ""
    )
    return f"""
      <li class="kpi kpi--{sinal.nivel.value}">
        <div class="kpi__topo">
          <span class="kpi__nome">{_e(sinal.titulo)}{sombra}</span>
          <span class="kpi__valor">{_e(_valor(sinal))}</span>
        </div>
        <div class="kpi__base">
          <span class="kpi__estado">{_e(ROTULO_NIVEL[sinal.nivel])}</span>
          <span class="kpi__dono">{_e(papel.nome)}</span>
          {marca}
        </div>
        {detalhe_html}
      </li>"""


def _cobranca(acao: Acao, kpi: dict[str, Any], cfg: Config) -> str:
    papel = cfg.papel(acao.dono)
    passos = "".join(f"<li>{_e(p)}</li>" for p in acao.passos)

    numeros = [
        (k, v) for k, v in acao.contexto.items()
        if k != "LISTA" and not isinstance(v, str)
    ][:10]
    nums_html = "".join(
        f"<li><span>{_e(k.replace('_', ' ').lower())}</span>"
        f"<span class='mono'>{_e(v)}</span></li>"
        for k, v in numeros
    )
    lista = acao.contexto.get("LISTA")
    lista_html = (
        f'<p class="cob__h">Quem está na lista</p>'
        f'<p class="kpi__detalhe">{_e(lista)}</p>' if lista else ""
    )

    escada = (
        "ainda no prazo" if acao.escalonamentos == 0
        else f"{acao.escalonamentos}ª cobrança disparada"
    )
    return f"""
    <article class="cob" id="cob-{_e(acao.id)}" data-acao="{_e(acao.id)}">
      <button class="cob__cab" type="button" aria-expanded="false"
              aria-controls="corpo-{_e(acao.id)}">
        <span class="cob__tit">{_e(acao.titulo)}</span>
        <span class="cob__seta" aria-hidden="true">▾</span>
        <span class="cob__meta">
          <span class="tag tag--{acao.nivel.value}">{_e(ROTULO_NIVEL[acao.nivel])}</span>
          <span>{_e(papel.nome)}</span>
          <span class="mono">prazo {acao.prazo:%d/%m %H:%M}</span>
          <span>{_e(escada)}</span>
          <span class="mono" data-contador="{_e(acao.id)}"></span>
        </span>
      </button>
      <div class="cob__corpo" id="corpo-{_e(acao.id)}" hidden>
        <p class="cob__pergunta">{_e(kpi["pergunta"])}</p>

        <p class="cob__h">O que preciso de você</p>
        <ol class="cob__passos">{passos}</ol>

        <p class="cob__h">Números da apuração</p>
        <ul class="cob__nums">{nums_html}</ul>
        {lista_html}

        <p class="cob__base">Base do número:
          <span class="mono">{_e(kpi["sql"])}</span> ·
          apurado em {acao.criada_em:%d/%m/%Y %H:%M} ·
          SLA de {_e(kpi["acao"]["sla_resposta_horas"])}h</p>

        <div class="thread" data-thread="{_e(acao.id)}">
          <p class="cob__h">Respostas</p>
          <div data-lista="{_e(acao.id)}">
            <p class="thread__vazio">Carregando respostas…</p>
          </div>
        </div>
      </div>
    </article>"""


def gerar(cfg: Config, sinais: list[Sinal], acoes: list[Acao],
          cobrancas: int = 0, escaladas: int = 0) -> str:
    por_id = {k["id"]: k for k in cfg.matriz["kpis"]}
    acao_por_kpi = {a.kpi_id: a for a in acoes}
    agora = datetime.now()

    areas_cobrando = {por_id[a.kpi_id]["area"] for a in acoes}
    areas_medidas = {por_id[s.kpi_id]["area"] for s in sinais}

    blocos = []
    for chave, nome in AREAS:
        do_area = [s for s in sinais if por_id[s.kpi_id]["area"] == chave]
        if not do_area:
            continue
        ordem = {Nivel.CRITICO: 0, Nivel.VERMELHO: 1, Nivel.AMARELO: 2,
                 Nivel.VERDE: 3}
        do_area.sort(key=lambda s: (ordem[s.nivel], s.titulo))
        cobrando = sum(1 for s in do_area if s.nivel.cobra)
        itens = "".join(
            _linha_kpi(s, por_id[s.kpi_id], cfg, acao_por_kpi.get(s.kpi_id))
            for s in do_area
        )
        selo = (
            f'<span class="area__selo">{cobrando} cobrando</span>' if cobrando
            else '<span class="area__selo area__selo--ok">no alvo</span>'
        )
        blocos.append(
            f'<section class="area"><h3 class="area__tit">{_e(nome)}{selo}</h3>'
            f'<ul class="kpis">{itens}</ul></section>'
        )

    etapas = _etapas(sinais, acoes, por_id, cfg)
    etapas_html = "".join(
        f'<li><button class="etapa" type="button" aria-expanded="false"'
        f' aria-controls="gaveta" data-etapa="{_e(et.chave)}">'
        f'<span class="etapa__n">{et.n}</span>'
        f'<span class="etapa__nome">{_e(et.nome)}</span>'
        f'<span class="etapa__nota">{_e(et.nota)}</span>'
        f'<span class="etapa__seta" aria-hidden="true">▾</span>'
        f"</button></li>"
        for et in etapas
    )

    cobs_html = "".join(
        _cobranca(a, por_id[a.kpi_id], cfg)
        for a in sorted(acoes, key=lambda x: x.prazo)
    ) or '<p class="vazio">Nenhuma cobrança aberta.</p>'

    sombras_html = "".join(
        f'<li class="sombra"><b>{_e(k["titulo"])}</b>'
        f'<span>{_e(" ".join(k["observacao"].split())[:190])}…</span></li>'
        for k in cfg.matriz["kpis"] if k["modo"] == "sombra"
    )

    fluxo = next((s for s in sinais if s.kpi_id == "fluxo_caixa_critico"), None)
    ntr = next((s for s in sinais if s.kpi_id == "emissao_ntrlog"), None)
    graficos = []
    if fluxo and not fluxo.erro:
        graficos.append(_grafico_gap(
            "Fluxo de caixa — compromissos a vencer",
            ["D0–D7", "D8–D30"],
            [float(fluxo.linha.get("SALDO_D0_D7", 0)),
             float(fluxo.linha.get("SALDO_D8_D30", 0))],
            "TGFFIN, títulos em aberto e não-provisão. Não inclui saldo "
            "bancário de abertura.",
        ))
    if ntr and not ntr.erro:
        graficos.append(_grafico_gap(
            "NTR Log — frete pago contra nota emitida",
            ["Frete pago pela Nitron", "Emitido pela NTR Log"],
            [float(ntr.linha.get("FRETE_PAGO_MES", 0)),
             float(ntr.linha.get("EMITIDO_NTRLOG", 0))],
            "Mês fechado. Natureza 9010107 contra emissão da CODEMP 3.",
        ))

    dados = {
        "etapas": {et.chave: {"nome": et.nome, "explica": et.explica,
                              "itens": et.itens} for et in etapas},
        "acoes": {a.id: {"titulo": a.titulo, "dono": cfg.papel(a.dono).nome}
                  for a in acoes},
    }

    return f"""<title>Pipeline Nitron</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
:root {{
  color-scheme: light;
  --ground:#F2F1EC; --surface:#FCFCFB; --surface-2:#F7F6F1;
  --ink:#17191A; --ink-2:#44474A; --muted:#6D706C; --hair:#DEDCD4;
  --accent:#0B4F5C; --accent-soft:#E4EEF0;
  --verde:#00805F; --ambar:#A88700; --crimson:#C22A55;
  --passo:clamp(14px,2.2vw,22px);
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    color-scheme: dark;
    --ground:#121311; --surface:#1B1D1A; --surface-2:#212320;
    --ink:#EDEBE4; --ink-2:#C2C0B8; --muted:#95988F; --hair:#2E312D;
    --accent:#4FB5C4; --accent-soft:#16302F;
    --verde:#17A08F; --ambar:#A28A18; --crimson:#DB5C80;
  }}
}}
:root[data-theme="dark"] {{
  color-scheme: dark;
  --ground:#121311; --surface:#1B1D1A; --surface-2:#212320;
  --ink:#EDEBE4; --ink-2:#C2C0B8; --muted:#95988F; --hair:#2E312D;
  --accent:#4FB5C4; --accent-soft:#16302F;
  --verde:#17A08F; --ambar:#A28A18; --crimson:#DB5C80;
}}

* {{ box-sizing:border-box; }}
body {{
  margin:0; background:var(--ground); color:var(--ink);
  font:400 15px/1.55 "IBM Plex Sans","Segoe UI",system-ui,sans-serif;
  -webkit-font-smoothing:antialiased;
}}
.pagina {{ max-width:1120px; margin:0 auto; padding-block:var(--passo) 56px;
  padding-left:16px; padding-right:16px; }}
h1,h2,h3 {{ font-family:"Archivo","Segoe UI",system-ui,sans-serif;
  text-wrap:balance; margin:0; letter-spacing:-.012em; }}
.mono, .kpi__valor, .etapa__n, .tabela .mono {{
  font-family:"IBM Plex Mono",ui-monospace,monospace;
  font-variant-numeric:tabular-nums; }}
.sr {{ position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); }}

/* cabeçalho */
.topo {{ display:flex; flex-wrap:wrap; gap:12px 24px; align-items:baseline;
  justify-content:space-between; padding-bottom:16px;
  border-bottom:2px solid var(--accent); }}
.topo h1 {{ font-size:clamp(25px,4.2vw,36px); font-weight:700; }}
.topo__sub {{ color:var(--muted); font-size:13.5px; max-width:52ch; margin:6px 0 0; }}
.carimbo {{ font-family:"IBM Plex Mono",monospace; font-size:12px;
  color:var(--muted); text-align:right; }}

/* tiles */
.tiles {{ display:grid; gap:12px; margin-top:var(--passo);
  grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); }}
.tile {{ background:var(--surface); border:1px solid var(--hair);
  border-radius:3px; padding:16px 18px; }}
.tile--destaque {{ border-left:4px solid var(--accent); }}
.tile__rot {{ font-size:11px; letter-spacing:.09em; text-transform:uppercase;
  color:var(--muted); font-weight:600; }}
.tile__n {{ font-family:"Archivo",sans-serif; font-weight:700;
  font-size:clamp(27px,4.4vw,38px); line-height:1.1; margin-top:6px;
  font-variant-numeric:tabular-nums; }}
.tile__nota {{ font-size:12.5px; color:var(--muted); margin-top:4px; }}
.tile__de {{ font-family:"IBM Plex Sans",sans-serif; font-size:15px;
  font-weight:500; color:var(--muted); margin-left:7px; }}

/* pipeline */
.secao {{ margin-top:34px; }}
.secao__tit {{ font-size:12px; letter-spacing:.11em; text-transform:uppercase;
  color:var(--accent); font-weight:700; margin-bottom:12px;
  font-family:"IBM Plex Sans",sans-serif; }}
.trilho {{ list-style:none; margin:0; padding:0; display:grid; gap:2px;
  grid-template-columns:repeat(auto-fit,minmax(128px,1fr)); }}
.etapa {{ background:var(--surface); border:1px solid var(--hair);
  padding:13px 14px; display:flex; flex-direction:column; gap:2px; position:relative; }}
.etapa::after {{ content:""; position:absolute; right:-1px; top:50%;
  width:7px; height:7px; border-top:1px solid var(--accent);
  border-right:1px solid var(--accent); transform:translate(50%,-50%) rotate(45deg);
  background:var(--ground); z-index:1; }}
.etapa:last-child::after {{ display:none; }}
.etapa__n {{ font-size:23px; font-weight:600; color:var(--accent); line-height:1.1; }}
.etapa__nome {{ font-size:13px; font-weight:600; }}
.etapa__nota {{ font-size:11.5px; color:var(--muted); }}

/* barra de status */
.barra {{ display:flex; height:32px; border-radius:2px; overflow:hidden; gap:2px; }}
.seg {{ display:flex; align-items:center; justify-content:center; min-width:26px; }}
.seg__n {{ font-family:"IBM Plex Mono",monospace; font-size:12.5px;
  font-weight:500; color:#fff; }}
.seg--verde {{ background:var(--verde); }}
.seg--amarelo {{ background:var(--ambar); }}
.seg--vermelho {{ background:var(--crimson); }}
.seg--critico {{ background:var(--crimson);
  background-image:repeating-linear-gradient(135deg,transparent 0 5px,rgba(0,0,0,.34) 5px 10px); }}
.chaves {{ display:flex; flex-wrap:wrap; gap:8px 18px; margin-top:9px;
  font-size:12.5px; color:var(--ink-2); }}
.chave {{ display:inline-flex; align-items:center; gap:6px; }}
.ponto {{ width:9px; height:9px; border-radius:50%; display:inline-block; }}
.ponto--verde {{ background:var(--verde); }}
.ponto--amarelo {{ background:var(--ambar); }}
.ponto--vermelho {{ background:var(--crimson); }}
.ponto--critico {{ background:var(--crimson); border-radius:2px;
  outline:2px solid var(--crimson); outline-offset:1px; }}

/* áreas */
.areas {{ display:grid; gap:14px; align-items:start;
  grid-template-columns:repeat(auto-fit,minmax(310px,1fr)); }}
.area {{ background:var(--surface); border:1px solid var(--hair); border-radius:3px; }}
.area__tit {{ font-size:13px; font-weight:700; letter-spacing:.055em;
  text-transform:uppercase; padding:12px 16px; border-bottom:1px solid var(--hair);
  display:flex; justify-content:space-between; align-items:center; gap:10px; }}
.area__selo {{ font-family:"IBM Plex Sans",sans-serif; font-size:10.5px;
  font-weight:600; letter-spacing:.04em; text-transform:none;
  color:var(--crimson); }}
.area__selo--ok {{ color:var(--verde); }}
.kpis {{ list-style:none; margin:0; padding:0; }}
.kpi {{ padding:11px 16px 11px 19px; border-bottom:1px solid var(--hair);
  border-left:3px solid transparent; }}
.kpi:last-child {{ border-bottom:none; }}
.kpi--verde {{ border-left-color:var(--verde); }}
.kpi--amarelo {{ border-left-color:var(--ambar); }}
.kpi--vermelho {{ border-left-color:var(--crimson); }}
.kpi--critico {{ border-left-color:var(--crimson); border-left-width:7px;
  background:var(--surface-2); }}
.kpi__topo {{ display:flex; justify-content:space-between; align-items:baseline;
  gap:12px; }}
.kpi__nome {{ font-size:14px; font-weight:500; }}
.kpi__valor {{ font-size:14px; font-weight:500; white-space:nowrap; }}
.kpi__base {{ display:flex; flex-wrap:wrap; align-items:center; gap:6px 10px;
  margin-top:3px; font-size:11.5px; color:var(--muted); }}
.kpi__estado {{ font-weight:600; text-transform:uppercase; letter-spacing:.05em;
  font-size:10.5px; }}
.kpi--vermelho .kpi__estado, .kpi--critico .kpi__estado {{ color:var(--crimson); }}
.kpi--amarelo .kpi__estado {{ color:var(--ambar); }}
.kpi--verde .kpi__estado {{ color:var(--verde); }}
.kpi__dono::before {{ content:"›"; margin-right:5px; opacity:.55; }}
.kpi__detalhe {{ margin:7px 0 0; font-size:11.5px; line-height:1.45;
  color:var(--ink-2); background:var(--surface-2); padding:7px 9px;
  border-radius:2px; }}

/* etiquetas */
.tag {{ font-size:10.5px; font-weight:600; padding:1px 6px; border-radius:2px;
  border:1px solid var(--hair); color:var(--ink-2); white-space:nowrap; }}
.tag--sombra {{ border-style:dashed; color:var(--muted); font-weight:500; }}
.tag--acao {{ border-color:var(--accent); color:var(--accent);
  background:var(--accent-soft); font-family:"IBM Plex Mono",monospace; }}
.tag--erro {{ border-style:dotted; color:var(--muted); }}
.tag--vermelho, .tag--critico {{ border-color:var(--crimson); color:var(--crimson); }}
.tag--amarelo {{ border-color:var(--ambar); color:var(--ambar); }}
.tag--verde {{ border-color:var(--verde); color:var(--verde); }}

/* gráficos */
.graficos {{ display:grid; gap:14px;
  grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); }}
.grafico {{ margin:0; background:var(--surface); border:1px solid var(--hair);
  border-radius:3px; padding:16px 18px; }}
.grafico__tit {{ font-size:13px; font-weight:600; margin-bottom:14px; }}
.barh__linha {{ display:grid; grid-template-columns:minmax(78px,auto) 1fr auto;
  align-items:center; gap:10px; margin-bottom:10px; }}
.barh__rot {{ font-size:12px; color:var(--ink-2); }}
.barh__trilho {{ background:var(--surface-2); height:16px; border-radius:2px;
  display:block; }}
.barh__fill {{ display:block; height:100%; border-radius:0 2px 2px 0; }}
.barh__fill.barh--neg {{ background:var(--crimson); }}
.barh__fill.barh--pos {{ background:var(--accent); }}
.barh__val {{ font-family:"IBM Plex Mono",monospace; font-size:12px;
  font-variant-numeric:tabular-nums; white-space:nowrap; }}
.grafico__fonte {{ font-size:11px; color:var(--muted); margin:12px 0 0;
  line-height:1.45; }}

/* tabela */
.tabela-wrap {{ overflow-x:auto; background:var(--surface);
  border:1px solid var(--hair); border-radius:3px; }}
.tabela {{ border-collapse:collapse; width:100%; min-width:660px; font-size:13px; }}
.tabela th {{ text-align:left; font-size:10.5px; letter-spacing:.08em;
  text-transform:uppercase; color:var(--muted); font-weight:600;
  padding:11px 14px; border-bottom:1px solid var(--hair); }}
.tabela td {{ padding:11px 14px; border-bottom:1px solid var(--hair);
  vertical-align:top; }}
.tabela tr:last-child td {{ border-bottom:none; }}
.vazio {{ color:var(--muted); font-size:13.5px; }}

/* sombras */
.sombras {{ list-style:none; margin:0; padding:0; display:grid; gap:9px; }}
.sombra {{ background:var(--surface); border:1px dashed var(--hair);
  border-radius:3px; padding:12px 15px; display:grid; gap:3px; }}
.sombra b {{ font-size:13.5px; font-weight:600; }}
.sombra span {{ font-size:12px; color:var(--muted); line-height:1.5; }}

.rodape {{ margin-top:40px; padding-top:16px; border-top:1px solid var(--hair);
  font-size:11.5px; color:var(--muted); line-height:1.6; }}

@media (max-width:520px) {{
  .etapa::after {{ display:none; }}
  .kpi__topo {{ flex-direction:column; gap:1px; }}
}}
@media (prefers-reduced-motion:reduce) {{ * {{ animation:none !important;
  transition:none !important; }} }}

/* --- pipeline clicável --- */
.etapa {{ cursor:pointer; text-align:left; font:inherit; color:inherit;
  width:100%; transition:background .12s; }}
.etapa:hover {{ background:var(--surface-2); }}
.etapa[aria-expanded="true"] {{ background:var(--accent-soft);
  border-color:var(--accent); }}
.etapa:focus-visible, .cob__cab:focus-visible, .resp__enviar:focus-visible {{
  outline:2px solid var(--accent); outline-offset:2px; }}
.etapa__seta {{ position:absolute; right:10px; bottom:9px; font-size:10px;
  color:var(--muted); }}
.gaveta {{ margin-top:2px; background:var(--surface); border:1px solid var(--accent);
  border-radius:0 0 3px 3px; padding:15px 17px; }}
.gaveta__tit {{ font-size:12.5px; font-weight:600; margin:0 0 3px; }}
.gaveta__nota {{ font-size:12px; color:var(--muted); margin:0 0 12px;
  max-width:74ch; line-height:1.5; }}
.gaveta__lista {{ list-style:none; margin:0; padding:0; display:grid; gap:1px;
  background:var(--hair); border:1px solid var(--hair); border-radius:2px; }}
.gaveta__item {{ background:var(--surface); padding:8px 12px; display:flex;
  flex-wrap:wrap; gap:4px 12px; align-items:baseline; font-size:12.5px; }}
.gaveta__item b {{ font-weight:500; flex:1 1 190px; }}
.gaveta__item .mono {{ font-size:12px; }}
.gaveta__item span.area {{ font-size:10.5px; letter-spacing:.05em;
  text-transform:uppercase; color:var(--muted); }}
.gaveta__vazio {{ font-size:12.5px; color:var(--muted); margin:0; }}
.secao__nota {{ font-size:12.5px; color:var(--ink-2); margin:-4px 0 12px;
  max-width:74ch; line-height:1.55; }}

/* --- cobranças com detalhe e respostas --- */
.cobs {{ display:grid; gap:10px; }}
.cob {{ background:var(--surface); border:1px solid var(--hair); border-radius:3px;
  border-left:3px solid var(--crimson); overflow:hidden; }}
.cob--respondida {{ border-left-color:var(--verde); }}
.cob__cab {{ width:100%; background:none; border:0; font:inherit; color:inherit;
  text-align:left; padding:13px 16px; cursor:pointer; display:grid;
  grid-template-columns:1fr auto; gap:4px 14px; align-items:center; }}
.cob__cab:hover {{ background:var(--surface-2); }}
.cob__tit {{ font-size:14px; font-weight:500; }}
.cob__meta {{ grid-column:1/-1; display:flex; flex-wrap:wrap; gap:5px 12px;
  font-size:11.5px; color:var(--muted); align-items:center; }}
.cob__seta {{ font-size:11px; color:var(--muted); }}
.cob__corpo {{ border-top:1px solid var(--hair); padding:15px 16px 17px;
  background:var(--surface-2); }}
.cob__pergunta {{ margin:0 0 12px; font-size:13px; font-style:italic;
  color:var(--ink-2); }}
.cob__h {{ font-size:10.5px; letter-spacing:.09em; text-transform:uppercase;
  color:var(--muted); font-weight:600; margin:14px 0 6px; }}
.cob__h:first-of-type {{ margin-top:0; }}
.cob__passos {{ margin:0; padding-left:19px; display:grid; gap:4px;
  font-size:13px; }}
.cob__nums {{ list-style:none; margin:0; padding:0; display:grid; gap:2px;
  font-size:12.5px; }}
.cob__nums li {{ display:flex; justify-content:space-between; gap:14px;
  padding:3px 0; border-bottom:1px dotted var(--hair); }}
.cob__nums li:last-child {{ border-bottom:none; }}
.cob__base {{ font-size:11.5px; color:var(--muted); margin:14px 0 0;
  padding-top:10px; border-top:1px solid var(--hair); line-height:1.6; }}

/* --- thread de respostas --- */
.thread {{ margin-top:16px; padding-top:14px; border-top:1px solid var(--hair); }}
.thread__vazio {{ font-size:12.5px; color:var(--muted); margin:0; }}
.resp {{ display:grid; grid-template-columns:auto 1fr; gap:3px 10px;
  padding:10px 0; border-bottom:1px solid var(--hair); }}
.resp:last-of-type {{ border-bottom:none; }}
.resp__av {{ width:26px; height:26px; border-radius:50%; grid-row:1/3;
  background:var(--surface-2); }}
.resp__quem {{ font-size:12.5px; font-weight:600; display:flex;
  flex-wrap:wrap; gap:8px; align-items:baseline; }}
.resp__quando {{ font-family:"IBM Plex Mono",monospace; font-size:11px;
  font-weight:400; color:var(--muted); }}
.resp__txt {{ font-size:13px; margin:0; white-space:pre-wrap;
  overflow-wrap:anywhere; }}
.resp__selo {{ font-size:10px; font-weight:600; letter-spacing:.04em;
  color:var(--verde); border:1px solid var(--verde); border-radius:2px;
  padding:0 5px; }}
.resp__form {{ margin-top:12px; display:grid; gap:9px; }}
.resp__form textarea {{ width:100%; min-height:76px; resize:vertical;
  font:inherit; font-size:13px; padding:9px 11px; border-radius:3px;
  border:1px solid var(--hair); background:var(--surface); color:var(--ink); }}
.resp__form textarea:focus-visible {{ outline:2px solid var(--accent);
  outline-offset:-1px; border-color:var(--accent); }}
.resp__linha {{ display:flex; flex-wrap:wrap; gap:10px 14px; align-items:center; }}
.resp__enviar {{ font:inherit; font-size:13px; font-weight:600; cursor:pointer;
  padding:8px 17px; border-radius:3px; border:1px solid var(--accent);
  background:var(--accent); color:var(--surface); }}
.resp__enviar:hover {{ filter:brightness(1.12); }}
.resp__enviar[disabled] {{ opacity:.5; cursor:default; filter:none; }}
.resp__check {{ display:inline-flex; align-items:center; gap:6px;
  font-size:12.5px; color:var(--ink-2); cursor:pointer; }}
.resp__aviso {{ font-size:12px; color:var(--muted); margin:8px 0 0; }}
.resp__erro {{ font-size:12.5px; color:var(--crimson); margin:0; }}</style>

<div class="pagina">
  <header class="topo">
    <div>
      <h1>Pipeline de gestão</h1>
      <p class="topo__sub">Cada indicador medido, julgado e — quando sai da linha —
        transformado em cobrança com dono e prazo. Clique em uma etapa para ver
        o que está nela; abra uma cobrança para responder.</p>
    </div>
    <div class="carimbo">Apurado em {agora:%d/%m/%Y %H:%M}<br>Grupo Nitron ·
      CODEMP {_e(cfg.matriz['recorte_padrao']['codemp'])}</div>
  </header>

  <div class="tiles">
    <div class="tile tile--destaque">
      <div class="tile__rot">Cobranças abertas</div>
      <div class="tile__n">{len(acoes)}</div>
      <div class="tile__nota">aguardando resposta de um dono</div>
    </div>
    <div class="tile">
      <div class="tile__rot">Áreas cobrando</div>
      <div class="tile__n">{len(areas_cobrando)}<span class="tile__de">de
        {len(areas_medidas)}</span></div>
      <div class="tile__nota">áreas com pelo menos uma cobrança aberta</div>
    </div>
    <div class="tile">
      <div class="tile__rot">KPIs na matriz</div>
      <div class="tile__n">{len(sinais)}</div>
      <div class="tile__nota">{sum(1 for s in sinais if s.modo == "ativo")} cobram ·
        {sum(1 for s in sinais if s.modo == "sombra")} em sombra</div>
    </div>
  </div>

  <section class="secao">
    <h2 class="secao__tit">Do número à resposta — clique numa etapa</h2>
    <ol class="trilho">{etapas_html}</ol>
    <div class="gaveta" id="gaveta" hidden></div>
  </section>

  <section class="secao">
    <h2 class="secao__tit">Situação dos {len(sinais)} indicadores</h2>
    {_barra_status(sinais)}
  </section>

  <section class="secao">
    <h2 class="secao__tit">Onde está o dinheiro parado</h2>
    <div class="graficos">{"".join(graficos)}</div>
  </section>

  <section class="secao">
    <h2 class="secao__tit">Cobranças abertas — abra para responder</h2>
    <div class="cobs">{cobs_html}</div>
  </section>

  <section class="secao">
    <h2 class="secao__tit">Painel por área</h2>
    <div class="areas">{"".join(blocos)}</div>
  </section>

  <section class="secao">
    <h2 class="secao__tit">Em sombra — medem, mas ainda não cobram</h2>
    <p class="secao__nota">Sombra é o indicador que roda, grava e aparece aqui,
      mas <b>não manda mensagem para ninguém</b>. Fica assim quando o dado de
      origem ainda não sustenta uma cobrança — um alerta errado custa mais caro
      que um alerta ausente. Nenhum depende de código: falta dado ou falta
      acordo.</p>
    <ul class="sombras">{sombras_html}</ul>
  </section>

  <p class="rodape">
    Faturamento ancorado em <span class="mono">TGFTOP.ATUALCOM='C'</span> com
    <span class="mono">AD_INSEREDASH='S'</span>; filtro de TOP por subquery em
    <span class="mono">CODTIPOPER</span>, nunca por join na
    <span class="mono">TGFTOP</span>, que é versionada. Devolução exclui a TOP 2203
    (consignação). Saldo de estoque exclui o <span class="mono">CODLOCAL 1080000</span>,
    que é conta de contrapartida. A metodologia de cada número está no cabeçalho do
    <span class="mono">.sql</span> correspondente.
  </p>
</div>

<script>
const DADOS = {json.dumps(dados, ensure_ascii=False)};
// --- gaveta do pipeline -------------------------------------------------
const gaveta = document.getElementById("gaveta");
const botoesEtapa = [...document.querySelectorAll("[data-etapa]")];

function fecharEtapas() {{
  botoesEtapa.forEach(b => b.setAttribute("aria-expanded", "false"));
  gaveta.hidden = true;
}}

function abrirEtapa(chave, botao) {{
  const et = DADOS.etapas[chave];
  if (!et) return;
  botoesEtapa.forEach(b => b.setAttribute("aria-expanded",
    b === botao ? "true" : "false"));

  const lista = et.itens.length
    ? `<ul class="gaveta__lista">${{et.itens.map(i => `
        <li class="gaveta__item">
          <i class="ponto ponto--${{i.nivel}}" aria-hidden="true"></i>
          <b>${{esc(i.titulo)}}${{i.modo === "sombra"
            ? ' <span class="tag tag--sombra">sombra</span>' : ""}}</b>
          <span class="mono">${{esc(i.valor)}}</span>
          <span class="area">${{i.dono && i.dono.toLowerCase() !== i.area.toLowerCase()
            ? esc(i.area) + " › " + esc(i.dono) : esc(i.area)}}</span>
        </li>`).join("")}}</ul>`
    : `<p class="gaveta__vazio">Nada nesta etapa agora.</p>`;

  gaveta.innerHTML =
    `<p class="gaveta__tit">${{esc(et.nome)}} — ${{et.itens.length}}</p>` +
    `<p class="gaveta__nota">${{esc(et.explica)}}</p>` + lista;
  gaveta.hidden = false;
}}

function esc(t) {{
  const d = document.createElement("div");
  d.textContent = t == null ? "" : String(t);
  return d.innerHTML;
}}

botoesEtapa.forEach(b => b.addEventListener("click", () => {{
  if (b.getAttribute("aria-expanded") === "true") fecharEtapas();
  else abrirEtapa(b.dataset.etapa, b);
}}));

// --- abrir/fechar cobrança ---------------------------------------------
document.querySelectorAll(".cob__cab").forEach(cab => {{
  cab.addEventListener("click", () => {{
    const corpo = document.getElementById(cab.getAttribute("aria-controls"));
    const abrir = cab.getAttribute("aria-expanded") !== "true";
    cab.setAttribute("aria-expanded", String(abrir));
    corpo.hidden = !abrir;
    cab.querySelector(".cob__seta").textContent = abrir ? "▴" : "▾";
  }});
}});

// Se a URL aponta para uma cobrança, abre ela.
if (location.hash.startsWith("#cob-")) {{
  const alvo = document.querySelector(location.hash + " .cob__cab");
  if (alvo) alvo.click();
}}

// --- respostas ----------------------------------------------------------
// Vivem na base do artifact: quem responde não é quem publica a página, e o
// texto precisa sobreviver à próxima republicação.
(async () => {{
  // `claude` só existe dentro do viewer do artifact. Fora dele — arquivo
  // aberto direto, exportação, preview — a página tem que continuar legível
  // em vez de morrer num ReferenceError.
  const usar = n => Promise.resolve(window.claude?.use?.(n) ?? null);
  const db = await usar("db");
  const user = await usar("user");
  const threads = [...document.querySelectorAll("[data-thread]")];
  if (!threads.length) return;

  if (!db) {{
    threads.forEach(t => {{
      const alvo = t.querySelector("[data-lista]");
      alvo.textContent = "";
      const p = document.createElement("p");
      p.className = "resp__aviso";
      p.textContent = "As respostas aparecem na versão publicada da página. " +
        "Nesta cópia o histórico não carrega.";
      alvo.appendChild(p);
    }});
    return;
  }}

  const podeEscrever = await (user?.can("data.write") ?? Promise.resolve(null));
  const eu = user ? await user.me() : null;
  let porAcao = new Map();

  function quando(iso) {{
    const d = new Date(iso);
    return isNaN(d) ? "" : d.toLocaleString("pt-BR",
      {{ day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }});
  }}

  async function pintar() {{
    const ids = [...new Set([...porAcao.values()].flat()
      .map(r => r.autorId).filter(Boolean))];
    const perfis = user && ids.length ? await user.profiles(ids) : {{}};

    for (const thread of threads) {{
      const acaoId = thread.dataset.thread;
      const alvo = thread.querySelector("[data-lista]");
      const lista = (porAcao.get(acaoId) || [])
        .slice().sort((a, b) => (a.criadoEm || "").localeCompare(b.criadoEm || ""));

      alvo.textContent = "";
      if (!lista.length) {{
        const p = document.createElement("p");
        p.className = "thread__vazio";
        p.textContent = "Ninguém respondeu ainda.";
        alvo.appendChild(p);
      }}

      for (const r of lista) {{
        const perfil = perfis[r.autorId];
        const bloco = document.createElement("div");
        bloco.className = "resp";

        const av = document.createElement("img");
        av.className = "resp__av";
        av.alt = "";
        if (perfil) av.src = perfil.avatarUrl;
        bloco.appendChild(av);

        const quem = document.createElement("div");
        quem.className = "resp__quem";
        const nome = document.createElement("span");
        nome.textContent = (perfil && perfil.name) || "Alguém";
        quem.appendChild(nome);
        const data = document.createElement("span");
        data.className = "resp__quando";
        data.textContent = quando(r.criadoEm);
        quem.appendChild(data);
        if (r.encerra) {{
          const selo = document.createElement("span");
          selo.className = "resp__selo";
          selo.textContent = "ENCERROU A COBRANÇA";
          quem.appendChild(selo);
        }}
        bloco.appendChild(quem);

        const txt = document.createElement("p");
        txt.className = "resp__txt";
        txt.textContent = r.texto || "";
        bloco.appendChild(txt);

        alvo.appendChild(bloco);
      }}

      // Contador no cabeçalho, para ver sem abrir.
      const contador = document.querySelector(`[data-contador="${{CSS.escape(acaoId)}}"]`);
      if (contador) {{
        contador.textContent = lista.length
          ? `${{lista.length}} resposta${{lista.length > 1 ? "s" : ""}}` : "";
      }}
      const artigo = document.querySelector(`[data-acao="${{CSS.escape(acaoId)}}"]`);
      if (artigo) artigo.classList.toggle("cob--respondida",
        lista.some(r => r.encerra));
    }}
  }}

  function montarFormulario(thread) {{
    const acaoId = thread.dataset.thread;
    const form = document.createElement("form");
    form.className = "resp__form";

    const area = document.createElement("textarea");
    area.id = "resp-" + acaoId;
    area.placeholder =
      "O que foi feito, o que falta e até quando. Se o gargalo é de outra " +
      "área, diga qual.";
    area.setAttribute("aria-label", "Sua resposta a esta cobrança");
    form.appendChild(area);

    const linha = document.createElement("div");
    linha.className = "resp__linha";

    const botao = document.createElement("button");
    botao.type = "submit";
    botao.className = "resp__enviar";
    botao.textContent = "Responder";
    linha.appendChild(botao);

    const rotulo = document.createElement("label");
    rotulo.className = "resp__check";
    const check = document.createElement("input");
    check.type = "checkbox";
    check.id = "encerra-" + acaoId;
    rotulo.appendChild(check);
    rotulo.appendChild(document.createTextNode("isto encerra a cobrança"));
    linha.appendChild(rotulo);

    const erro = document.createElement("p");
    erro.className = "resp__erro";
    erro.hidden = true;
    linha.appendChild(erro);

    form.appendChild(linha);

    form.addEventListener("submit", async ev => {{
      ev.preventDefault();
      const texto = area.value.trim();
      if (!texto) return;
      botao.disabled = true;
      erro.hidden = true;
      try {{
        await db.collection("respostas").add({{
          acaoId,
          texto,
          autorId: eu?.id || null,
          encerra: check.checked,
          criadoEm: new Date().toISOString(),
        }});
        area.value = "";
        check.checked = false;
      }} catch (e) {{
        erro.hidden = false;
        erro.textContent = e && e.code === "invalid_argument"
          ? "Você tem acesso de leitura nesta página — peça edição para responder."
          : "Não consegui gravar agora. Tente de novo em instantes.";
        if (e && e.code === "invalid_argument") form.remove();
      }} finally {{
        botao.disabled = false;
      }}
    }});

    thread.appendChild(form);
  }}

  if (podeEscrever !== false) threads.forEach(montarFormulario);
  else threads.forEach(t => {{
    const p = document.createElement("p");
    p.className = "resp__aviso";
    p.textContent = "Você está como leitor nesta página e não pode responder.";
    t.appendChild(p);
  }});

  // Uma assinatura para todas as cobranças — não uma por thread.
  db.collection("respostas").onSnapshot(
    snap => {{
      porAcao = new Map();
      snap.docs.forEach(d => {{
        const r = d.data();
        if (!r || !r.acaoId) return;
        if (!porAcao.has(r.acaoId)) porAcao.set(r.acaoId, []);
        porAcao.get(r.acaoId).push(r);
      }});
      pintar();
    }},
    () => {{
      threads.forEach(t => {{
        const alvo = t.querySelector("[data-lista]");
        alvo.innerHTML =
          '<p class="resp__aviso">Perdi a conexão com as respostas. ' +
          'Recarregue a página.</p>';
      }});
    }},
  );
}})();

</script>
"""
