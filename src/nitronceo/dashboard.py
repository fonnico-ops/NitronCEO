"""Gera o dashboard do pipeline de gestão como um arquivo HTML.

O dashboard não é um relatório do que aconteceu — é o estado do pipeline:
cada KPI medido, o julgamento, a ação que nasceu dele, de quem está a bola e
há quanto tempo. Quem abre isto tem que saber em dez segundos o que está
parado e com quem.

A paleta de status foi validada nos dois temas com o validador do skill
dataviz (banda de luminosidade, piso de croma, separação para daltonismo,
piso de visão normal e contraste). Nenhum estado é comunicado só por cor:
todos carregam rótulo em texto e espessura de faixa própria.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
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


@dataclass
class Etapa:
    nome: str
    n: int
    nota: str


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


def _etapas(sinais: list[Sinal], acoes: list[Acao], cobrancas: int,
            escaladas: int) -> list[Etapa]:
    medidos = len(sinais)
    fora = sum(1 for s in sinais if s.nivel.cobra and not s.erro)
    cobrando = sum(1 for s in sinais if s.nivel.cobra and s.notificavel)
    respondidas = sum(1 for a in acoes if a.estado is Estado.RESPONDIDA)
    return [
        Etapa("Medido", medidos, "KPIs na matriz"),
        Etapa("Fora da linha", fora, "vermelho ou crítico"),
        Etapa("Cobrável", cobrando, f"{fora - cobrando} em sombra"),
        Etapa("Ação aberta", len(acoes), "com dono e prazo"),
        Etapa("Cobrado", cobrancas, "prazo vencido"),
        Etapa("Escalado", escaladas, "subiu de nível"),
        Etapa("Respondido", respondidas, "bola devolvida"),
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
    sombra = ' <span class="tag tag--sombra">sombra</span>' if sinal.modo == "sombra" else ""
    if acao:
        marca = (
            f'<span class="tag tag--acao">ação {_e(acao.id[:6])} · '
            f'{acao.prazo:%d/%m %H:%M}</span>'
        )
    elif sinal.erro:
        marca = f'<span class="tag tag--erro">sem medição</span>'
    else:
        marca = ""
    detalhe = sinal.linha.get("LISTA") or ""
    detalhe_html = (
        f'<p class="kpi__detalhe">{_e(detalhe)}</p>' if detalhe and sinal.nivel.cobra else ""
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
        ordem = {Nivel.CRITICO: 0, Nivel.VERMELHO: 1, Nivel.AMARELO: 2, Nivel.VERDE: 3}
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

    etapas_html = "".join(
        f'<li class="etapa"><span class="etapa__n">{et.n}</span>'
        f'<span class="etapa__nome">{_e(et.nome)}</span>'
        f'<span class="etapa__nota">{_e(et.nota)}</span></li>'
        for et in _etapas(sinais, acoes, cobrancas, escaladas)
    )

    if acoes:
        linhas_acao = "".join(
            f"<tr><td class='mono'>{_e(a.id[:6])}</td>"
            f"<td>{_e(a.titulo)}</td>"
            f"<td>{_e(cfg.papel(a.dono).nome)}</td>"
            f"<td class='mono'>{a.prazo:%d/%m %H:%M}</td>"
            f"<td><span class='tag tag--{a.nivel.value}'>"
            f"{_e(ROTULO_NIVEL[a.nivel])}</span></td>"
            f"<td class='mono'>{a.escalonamentos}</td></tr>"
            for a in sorted(acoes, key=lambda x: x.prazo)
        )
        tabela = f"""
    <div class="tabela-wrap">
      <table class="tabela">
        <caption class="sr">Ações abertas com dono, prazo e rodada de cobrança</caption>
        <thead><tr><th>ID</th><th>Cobrança</th><th>Dono</th><th>Prazo</th>
          <th>Nível</th><th>Rodada</th></tr></thead>
        <tbody>{linhas_acao}</tbody>
      </table>
    </div>"""
    else:
        tabela = '<p class="vazio">Nenhuma ação aberta.</p>'

    sombras = [
        k for k in cfg.matriz["kpis"] if k["modo"] == "sombra"
    ]
    sombras_html = "".join(
        f'<li class="sombra"><b>{_e(k["titulo"])}</b>'
        f'<span>{_e(" ".join(k["observacao"].split())[:190])}…</span></li>'
        for k in sombras
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
            "TGFFIN, títulos em aberto e não-provisão. Não inclui saldo bancário "
            "de abertura.",
        ))
    if ntr and not ntr.erro:
        graficos.append(_grafico_gap(
            "NTR Log — frete pago contra nota emitida",
            ["Frete pago pela Nitron", "Emitido pela NTR Log"],
            [float(ntr.linha.get("FRETE_PAGO_MES", 0)),
             float(ntr.linha.get("EMITIDO_NTRLOG", 0))],
            "Mês fechado. Natureza 9010107 contra emissão da CODEMP 3.",
        ))

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
</style>

<div class="pagina">
  <header class="topo">
    <div>
      <h1>Pipeline de gestão</h1>
      <p class="topo__sub">Cada indicador medido, julgado e — quando sai da linha —
        transformado em cobrança com dono e prazo.</p>
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
    <h2 class="secao__tit">Do número à resposta</h2>
    <ol class="trilho">{etapas_html}</ol>
  </section>

  <section class="secao">
    <h2 class="secao__tit">Situação dos 23 indicadores</h2>
    {_barra_status(sinais)}
  </section>

  <section class="secao">
    <h2 class="secao__tit">Onde está o dinheiro parado</h2>
    <div class="graficos">{"".join(graficos)}</div>
  </section>

  <section class="secao">
    <h2 class="secao__tit">Painel por área</h2>
    <div class="areas">{"".join(blocos)}</div>
  </section>

  <section class="secao">
    <h2 class="secao__tit">Cobranças abertas</h2>
    {tabela}
  </section>

  <section class="secao">
    <h2 class="secao__tit">Em sombra — medem, mas ainda não cobram</h2>
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
"""
