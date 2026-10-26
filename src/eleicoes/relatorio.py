"""Saídas da Fase 1 para uma UF: CSV/Parquet por urna e relatório HTML autocontido."""

from __future__ import annotations

import html
import json
import math
from pathlib import Path

import numpy as np
import polars as pl
from scipy import stats

from .analise import ALFA, Pareamento, Resultado

UFS = {"ac": "Acre", "al": "Alagoas", "am": "Amazonas", "ap": "Amapá", "ba": "Bahia", "ce": "Ceará",
       "df": "Distrito Federal", "es": "Espírito Santo", "go": "Goiás", "ma": "Maranhão", "mg": "Minas Gerais",
       "ms": "Mato Grosso do Sul", "mt": "Mato Grosso", "pa": "Pará", "pb": "Paraíba", "pe": "Pernambuco",
       "pi": "Piauí", "pr": "Paraná", "rj": "Rio de Janeiro", "rn": "Rio Grande do Norte", "ro": "Rondônia",
       "rr": "Roraima", "rs": "Rio Grande do Sul", "sc": "Santa Catarina", "se": "Sergipe", "sp": "São Paulo",
       "to": "Tocantins", "zz": "Exterior"}
PLOTLY_URL = "https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"


def _plotly(cache: Path) -> str:
    """Plotly embutido no HTML, para o relatório abrir offline. Baixado uma vez e guardado em cache."""
    if not cache.exists():
        import urllib.request
        cache.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(PLOTLY_URL, timeout=60) as r:
            cache.write_bytes(r.read())
    return cache.read_text(encoding="utf-8").replace("</script>", "<\\/script>")


def _fmt(n, casas=0) -> str:
    if n is None or (isinstance(n, float) and math.isnan(n)):
        return "—"
    s = f"{n:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(x, casas=1) -> str:
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else _fmt(100 * x, casas) + "%"


def _q(x) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    return "< 0,0001" if x < 1e-4 else _fmt(x, 4)


def tabela_urnas(par: Pareamento, res: Resultado, nomes_mun: dict[int, str], nomes_cand: dict[int, str],
                 url_bu) -> pl.DataFrame:
    a, b = par.cand_a, par.cand_b
    rot = {"CAND_A": f"{a} {nomes_cand.get(a, '')}".strip(), "CAND_B": f"{b} {nomes_cand.get(b, '')}".strip()}
    u = res.urnas
    out = u.select(
        "uf", pl.col("cd_municipio").replace_strict(nomes_mun, default="?").alias("municipio"),
        "cd_municipio", pl.col("nr_zona").alias("zona"), pl.col("nr_secao").alias("secao"),
        pl.col("nr_local_t2").alias("local"), pl.col("secoes_agregadas_t2").alias("secoes_agregadas"),
        "urnas_no_local",
        pl.col("aptos_t1"), pl.col("comparecimento_t1"), pl.col("a_t1").alias(f"votos_{a}_1t"),
        pl.col("b_t1").alias(f"votos_{b}_1t"), pl.col("elim_t1").alias("votos_eliminados_1t"),
        pl.col("bn_t1").alias("brancos_nulos_1t"),
        pl.col("aptos_t2"), pl.col("comparecimento_t2"), pl.col("a_t2").alias(f"votos_{a}_2t"),
        pl.col("b_t2").alias(f"votos_{b}_2t"), pl.col("bn_t2").alias("brancos_nulos_2t"),
        *[(100 * pl.col(f"f_{k}_t1")).round(2).alias(f"pct_aptos_{n}_1t") for k, n in
          (("a", a), ("b", b), ("elim", "eliminados"), ("bn", "brancos_nulos"), ("abst", "abstencao"))],
        *[(100 * pl.col(f"f_{k}_t2")).round(2).alias(f"pct_aptos_{n}_2t") for k, n in
          (("a", a), ("b", b), ("bn", "brancos_nulos"), ("abst", "abstencao"))],
        *[(100 * pl.col(f"prev_{k}_t2")).round(2).alias(f"pct_previsto_{n}_2t") for k, n in
          (("a", a), ("b", b), ("bn", "brancos_nulos"), ("abst", "abstencao"))],
        *[(100 * pl.col(f"res_{k}")).round(2).alias(f"residuo_pp_{n}") for k, n in
          (("a", a), ("b", b), ("bn", "brancos_nulos"), ("abst", "abstencao"))],
        *[pl.col(f"z_{k}").round(2).alias(f"z_{n}") for k, n in
          (("a", a), ("b", b), ("bn", "brancos_nulos"), ("abst", "abstencao"))],
        pl.col("d2_modelo").round(2), "p_modelo", "q_modelo",
        pl.col("d2_local").round(2), "p_local", "q_local",
        "sinal_modelo", "sinal_local",
        pl.col("componente_principal").replace(rot).alias("componente_principal"), "direcao",
        "inversao", "quase_unanime_2t", "local_mudou", "urna_trocada",
        pl.col("abertura_t2"), pl.col("encerramento_t2"),
        pl.struct("cd_municipio", "nr_zona", "nr_secao", "hash_bu_t1", "arquivo_bu_t1")
        .map_elements(lambda r: url_bu(1, r), return_dtype=pl.String).alias("link_bu_1t"),
        pl.struct("cd_municipio", "nr_zona", "nr_secao", "hash_bu_t2", "arquivo_bu_t2")
        .map_elements(lambda r: url_bu(2, r), return_dtype=pl.String).alias("link_bu_2t"),
    )
    return out.with_columns((pl.col("sinal_modelo") | pl.col("sinal_local")).alias("sinalizada")).sort(
        ["sinalizada", "p_modelo"], descending=[True, False]
    )


def _hist2d(x: np.ndarray, y: np.ndarray, bins: int = 40) -> dict:
    h, xe, ye = np.histogram2d(x, y, bins=bins, range=[[0, 1], [0, 1]])
    return {"z": h.T.tolist(), "x": ((xe[:-1] + xe[1:]) / 2).tolist(), "y": ((ye[:-1] + ye[1:]) / 2).tolist()}


def gerar_html(uf: str, par: Pareamento, res: Resultado, tab: pl.DataFrame, sens: pl.DataFrame,
               integridade: dict[int, dict], nomes_cand: dict[int, str], gerado_em: str, cache_plotly: Path) -> str:
    a, b = par.cand_a, par.cand_b
    na, nb = nomes_cand.get(a, str(a)), nomes_cand.get(b, str(b))
    u = res.urnas
    n = u.height
    s_mod, s_loc = int(u["sinal_modelo"].sum()), int(u["sinal_local"].sum())
    s_any = int((u["sinal_modelo"] | u["sinal_local"]).sum())
    exc = par.excluidas.group_by("motivo_exclusao").len().sort("len", descending=True)
    zonas_div = integridade[1]["zonas_div"] + integridade[2]["zonas_div"]
    texto_integridade = ("e nela a soma dos BUs bate exatamente com o total oficial em todas as zonas, nos dois turnos."
                         if zonas_div == 0 else
                         f"e nela <strong>{zonas_div} zona(s) têm diferença</strong> entre os BUs e o total oficial (ver seção 1).")

    # --- dados dos gráficos
    val1 = (u["a_t1"] + u["b_t1"] + u["elim_t1"]).to_numpy()
    val2 = (u["a_t2"] + u["b_t2"]).to_numpy()
    xb = np.where(val1 > 0, u["b_t1"].to_numpy() / np.maximum(val1, 1), np.nan)
    yb = np.where(val2 > 0, u["b_t2"].to_numpy() / np.maximum(val2, 1), np.nan)
    flag = (u["sinal_modelo"] | u["sinal_local"]).to_numpy()
    nomes = dict(zip(tab["cd_municipio"].to_list(), tab["municipio"].to_list()))
    rot = [f"{nomes.get(m, m)} · zona {z} · seção {s}" for m, z, s in
           zip(u["cd_municipio"].to_list(), u["nr_zona"].to_list(), u["nr_secao"].to_list())]
    d2 = np.sort(u["d2_modelo"].to_numpy() / res.lambda_modelo)
    qs = stats.chi2.ppf((np.arange(1, len(d2) + 1) - 0.5) / len(d2), 3)
    passo = max(1, len(d2) // 2000)
    comp1 = (u["comparecimento_t1"] / u["aptos_t1"]).to_numpy()
    comp2 = (u["comparecimento_t2"] / u["aptos_t2"]).to_numpy()
    dados = {
        "scatter": {"x": np.round(xb, 4).tolist(), "y": np.round(yb, 4).tolist(), "f": flag.astype(int).tolist(),
                    "t": rot, "aptos": u["aptos_t2"].to_list()},
        "prev": {"x": np.round(u["prev_b_t2"].to_numpy(), 4).tolist(), "y": np.round(u["f_b_t2"].to_numpy(), 4).tolist()},
        "qq": {"x": qs[::passo].round(3).tolist(), "y": d2[::passo].round(3).tolist()},
        "k1": _hist2d(np.nan_to_num(xb), comp1), "k2": _hist2d(np.nan_to_num(yb), comp2),
        "na": na, "nb": nb,
    }

    # --- tabelas
    def linha(cels, th=False):
        tag = "th" if th else "td"
        return "<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cels) + "</tr>"

    integ_rows = []
    for t in (1, 2):
        i = integridade[t]
        integ_rows.append(linha([f"{t}º turno", _fmt(i["urnas_ok"]), _fmt(i["urnas_outras"]), _fmt(i["zonas"]),
                                 f'<strong>{_fmt(i["zonas_div"])}</strong>', _fmt(i["aptos"]), _fmt(i["comparecimento"]),
                                 i["reclassificados"] or "—"]))
    coef = res.coeficientes
    nome_comp = {"a": f"{a} {na}", "b": f"{b} {nb}", "bn": "brancos + nulos", "abst": "abstenção"}
    coef_rows = [linha([nome_comp[r["componente_2t"]], *[_fmt(r[c], 2) for c in ("de_a_1t", "de_b_1t", "de_elim_1t", "de_bn_1t")]])
                 for r in coef.iter_rows(named=True)]
    sens_rows = [linha([html.escape(r["cenario"].replace("_", " ")), f'{r["intensidade_pp_aptos"]} p.p.',
                        _pct(r["detectadas_modelo"], 0), _pct(r["detectadas_modelo_ou_local"], 0),
                        _pct(r["sinalizadas_nao_alvo"], 1)]) for r in sens.iter_rows(named=True)]
    exc_rows = [linha([html.escape(m), _fmt(c)]) for m, c in exc.iter_rows()] or [linha(["—", "0"])]

    top = tab.filter(pl.col("sinalizada")).head(150)
    top_rows = []
    for r in top.iter_rows(named=True):
        links = " ".join(f'<a href="{html.escape(r[k])}">{k[-2:].upper()}</a>' for k in ("link_bu_1t", "link_bu_2t") if r[k])
        top_rows.append(linha([
            html.escape(r["municipio"]), r["zona"], r["secao"], r["local"], _fmt(r["aptos_t2"]),
            f'{_fmt(r[f"pct_aptos_{a}_1t"], 1)} → {_fmt(r[f"pct_aptos_{a}_2t"], 1)} <span class="mut">({_fmt(r[f"pct_previsto_{a}_2t"], 1)})</span>',
            f'{_fmt(r[f"pct_aptos_{b}_1t"], 1)} → {_fmt(r[f"pct_aptos_{b}_2t"], 1)} <span class="mut">({_fmt(r[f"pct_previsto_{b}_2t"], 1)})</span>',
            f'{_fmt(r["pct_aptos_brancos_nulos_1t"], 1)} → {_fmt(r["pct_aptos_brancos_nulos_2t"], 1)}',
            f'{_fmt(r["pct_aptos_abstencao_1t"], 1)} → {_fmt(r["pct_aptos_abstencao_2t"], 1)}',
            f'{html.escape(r["componente_principal"])}<br><span class="mut">{r["direcao"]}</span>',
            _q(r["q_modelo"]), _q(r["q_local"]), links,
        ]))

    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Urnas {UFS.get(uf, uf.upper())} 2026</title>
<script>{_plotly(cache_plotly)}</script>
<style>
:root {{ color-scheme: light; --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --hi:#eb6834; --base:#b9b8b1; --seq0:#cde2fb; --seq1:#2a78d6; --seq2:#0d366b;
  --ring:rgba(11,11,11,.10); }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ color-scheme: dark; --page:#0d0d0d; --surface:#1a1a19;
  --ink:#f0efec; --ink2:#c3c2b7; --muted:#898781; --grid:#2c2c2a; --axis:#383835; --hi:#d95926; --base:#5c5b56;
  --seq0:#1a2a40; --seq1:#3987e5; --seq2:#cde2fb; --ring:rgba(255,255,255,.10); }} }}
:root[data-theme="dark"] {{ color-scheme: dark; --page:#0d0d0d; --surface:#1a1a19; --ink:#f0efec; --ink2:#c3c2b7;
  --muted:#898781; --grid:#2c2c2a; --axis:#383835; --hi:#d95926; --base:#5c5b56; --seq0:#1a2a40; --seq1:#3987e5;
  --seq2:#cde2fb; --ring:rgba(255,255,255,.10); }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:var(--page); color:var(--ink); font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }}
main {{ max-width:1180px; margin:0 auto; padding:24px 16px 64px; }}
h1 {{ font-size:26px; margin:0 0 4px; }} h2 {{ font-size:19px; margin:40px 0 8px; }}
p, li {{ color:var(--ink2); max-width:80ch; }} .mut {{ color:var(--muted); font-size:13px; }}
.aviso {{ border:1px solid var(--ring); border-left:4px solid var(--hi); background:var(--surface); padding:12px 16px; border-radius:8px; margin:16px 0; }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; margin:20px 0; }}
.tile {{ background:var(--surface); border:1px solid var(--ring); border-radius:10px; padding:14px 16px; }}
.tile b {{ display:block; font-size:28px; font-weight:600; }} .tile span {{ color:var(--ink2); font-size:13px; }}
.card {{ background:var(--surface); border:1px solid var(--ring); border-radius:10px; padding:12px; margin:12px 0; }}
.grid2 {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(340px,1fr)); gap:12px; }}
.plot {{ width:100%; height:440px; }} .plot.sm {{ height:340px; }}
.tw {{ overflow-x:auto; }}
table {{ border-collapse:collapse; width:100%; font-size:13px; font-variant-numeric:tabular-nums; }}
th, td {{ text-align:left; padding:6px 8px; border-bottom:1px solid var(--grid); vertical-align:top; }}
th {{ color:var(--ink2); font-weight:600; position:sticky; top:0; background:var(--surface); }}
a {{ color:var(--seq1); }}
</style></head>
<body><main>
<h1>{UFS.get(uf, uf.upper())}: urnas no 1º × 2º turno — Presidente 2026</h1>
<div class="mut">Gerado em {gerado_em} a partir dos Boletins de Urna publicados pelo TSE (resultados.tse.jus.br).</div>

<div class="aviso"><strong>Como ler.</strong> Uma urna sinalizada tem um <em>desvio não explicado pelo modelo</em>.
Isso não é indício de fraude por si: desvios grandes têm muitas explicações benignas (perfil local, mobilização,
remanejamento, urna pequena). O que pode demonstrar erro ou manipulação é a seção de integridade — {texto_integridade} Resultado <strong>preliminar</strong>: o modelo ainda não foi congelado num
conjunto de desenvolvimento, e não há eleição anterior como base de comparação.</div>

<div class="tiles">
 <div class="tile"><b>{_fmt(n)}</b><span>urnas pareadas 1º × 2º turno</span></div>
 <div class="tile"><b>{_fmt(par.excluidas.height)}</b><span>urnas fora do pareamento</span></div>
 <div class="tile"><b>{_fmt(s_any)}</b><span>urnas sinalizadas ({_pct(s_any / max(n, 1))}) — q &lt; {_fmt(ALFA, 2)}</span></div>
 <div class="tile"><b>{_fmt(s_mod)} · {_fmt(s_loc)}</b><span>pelo modelo · pelas urnas irmãs do local</span></div>
 <div class="tile"><b>{_fmt(integridade[1]["zonas_div"] + integridade[2]["zonas_div"])}</b><span>zonas com BU ≠ total oficial (2 turnos)</span></div>
</div>

<h2>1. Integridade: soma dos BUs × total oficial por zona</h2>
<p>Teste exato. Cada BU foi baixado individualmente, com assinatura verificada, e somado por zona; a soma é comparada
ao resultado totalizado que o TSE publica para a zona (também assinado). Qualquer diferença seria um fato a explicar.</p>
<div class="card tw"><table>
{linha(["turno", "urnas lidas (ok)", "urnas sem BU / outras", "zonas", "zonas com diferença", "aptos", "comparecimento", "números reclassificados como nulo"], True)}
{"".join(integ_rows)}
</table></div>

<h2>2. Mudança por urna: {b} {html.escape(nb)} nos votos válidos</h2>
<p>Cada ponto é uma urna. Eixo x: participação de {b} {html.escape(nb)} nos votos válidos do 1º turno; eixo y: no 2º turno.
Em <span style="color:var(--hi)">laranja</span>, as urnas sinalizadas. Uma urna longe da nuvem não é, sozinha,
sinalizada: o modelo compara com o esperado para urnas com composição parecida no mesmo município.</p>
<div class="card"><div id="g_scatter" class="plot"></div></div>

<div class="grid2">
 <div class="card"><div class="mut">Fração dos aptos em {b} {html.escape(nb)}, 2º turno: observado × previsto pelo modelo.
 Na diagonal, a urna fez o esperado.</div><div id="g_prev" class="plot sm"></div></div>
 <div class="card"><div class="mut">Calibração: quantis do score (D², já recalibrado, λ = {_fmt(res.lambda_modelo, 2)})
 contra a distribuição χ² de referência. O centro na diagonal indica escala correta; a cauda acima mostra os desvios.</div>
 <div id="g_qq" class="plot sm"></div></div>
</div>

<h2>3. Impressão digital comparecimento × votação</h2>
<p>Densidade de urnas por comparecimento (y) e participação de {b} {html.escape(nb)} nos válidos (x). Enchimento de urna
costuma aparecer como uma mancha separada no canto de comparecimento e votação próximos de 100% (Klimek et al., 2012).</p>
<div class="grid2"><div class="card"><div class="mut">1º turno</div><div id="g_k1" class="plot sm"></div></div>
<div class="card"><div class="mut">2º turno</div><div id="g_k2" class="plot sm"></div></div></div>

<h2>4. Urnas sinalizadas</h2>
<p>Ordenadas pela força do desvio no modelo. Valores em % dos aptos, 1º → 2º turno; entre parênteses, o previsto
para o 2º turno. “Componente” é onde o desvio é maior. Links: BU oficial de cada turno (arquivo binário do TSE).
Até 150 linhas aqui; todas as urnas estão no CSV.</p>
<div class="card tw" style="max-height:640px;overflow:auto"><table>
{linha(["município", "zona", "seção", "local", "aptos", f"{a} {html.escape(na)}", f"{b} {html.escape(nb)}", "brancos+nulos", "abstenção", "componente", "q modelo", "q local", "BU"], True)}
{"".join(top_rows) or linha(["nenhuma urna sinalizada"] + [""] * 12)}
</table></div>

<h2>5. Taxas médias de transferência</h2>
<p>Coeficientes do modelo robusto (com efeito fixo de município): quanto 1 ponto de cada grupo do 1º turno contribui,
em média, para cada componente do 2º turno, relativo à abstenção do 1º turno (categoria de referência).</p>
<div class="card tw"><table>
{linha(["2º turno ↓ / 1º turno →", f"{a} {html.escape(na)}", f"{b} {html.escape(nb)}", "eliminados", "brancos+nulos"], True)}
{"".join(coef_rows)}
</table></div>

<h2>6. Sensibilidade: o que este método consegue detectar</h2>
<p>Perturbamos artificialmente {_fmt(sens["urnas_alvo"][0])} urnas reais (2%) com mecanismos conhecidos, rodamos tudo de
novo e medimos quantas foram sinalizadas. Intensidade em pontos percentuais dos aptos da urna.</p>
<div class="card tw"><table>
{linha(["cenário", "intensidade", "detectadas (modelo)", "detectadas (modelo ou local)", "sinalizadas entre as não perturbadas"], True)}
{"".join(sens_rows)}
</table></div>

<h2>7. Fora do pareamento</h2>
<div class="card tw"><table>{linha(["motivo", "urnas"], True)}{"".join(exc_rows)}</table></div>

<h2>8. Método e limitações</h2>
<ul>
<li><strong>Unidade</strong>: urna (seção principal + agregadas). Composição em fração dos aptos: {a}, {b}, eliminados, brancos+nulos, abstenção.</li>
<li><strong>Modelo</strong>: regressão robusta (Huber) por componente do 2º turno sobre a composição do 1º, pesos = aptos, efeito fixo de município pela mediana. Variância com sobredispersão (τ² + φ·p(1−p)/n), escala calibrada pelo centro da distribuição.</li>
<li><strong>Score</strong>: distância de Mahalanobis dos resíduos ({a}, {b}, brancos+nulos), comparada a χ²₃; urnas irmãs: mesmo cálculo contra a mediana das outras urnas do local (locais com ≥ 3 urnas).</li>
<li><strong>Múltiplas comparações</strong>: Benjamini-Hochberg; q &lt; {_fmt(ALFA, 2)} significa que, se o modelo estiver bem especificado, até ~5% das sinalizadas seriam alarmes falsos.</li>
<li><strong>Caudas pesadas</strong>: a distribuição real dos resíduos tem mais casos extremos que a normal, então parte das sinalizações reflete limites do modelo, não anomalias.</li>
<li><strong>Sem base histórica</strong>: sem eleição anterior no pipeline, a taxa de sinalização não pode ser comparada à de outros anos.</li>
<li><strong>Falácia ecológica</strong>: o modelo estima transferências agregadas e não identifica o comportamento de nenhum eleitor.</li>
<li>Votos em números sem candidatura oficial foram contados como nulos, igual à totalização do TSE.</li>
</ul>
</main>
<script>
const D = {json.dumps(dados, ensure_ascii=False)};
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
function base(xt, yt) {{
  const ax = t => ({{title: {{text: t, font: {{size: 12, color: css('--ink2')}}}}, gridcolor: css('--grid'), linecolor: css('--axis'),
    zerolinecolor: css('--axis'), tickfont: {{color: css('--muted'), size: 11}}, tickformat: '.0%'}});
  return {{paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', margin: {{l: 56, r: 12, t: 12, b: 48}},
    xaxis: ax(xt), yaxis: ax(yt), font: {{family: 'system-ui, -apple-system, sans-serif', color: css('--ink')}},
    hoverlabel: {{bgcolor: css('--surface'), bordercolor: css('--axis'), font: {{color: css('--ink')}}}},
    legend: {{orientation: 'h', y: 1.06, font: {{color: css('--ink2')}}}}}};
}}
const cfg = {{displaylogo: false, responsive: true}};
function desenhar() {{
  const S = D.scatter, idx = f => S.f.map((v, i) => v === f ? i : -1).filter(i => i >= 0);
  const pts = (ii, nome, cor, tam) => ({{type: 'scattergl', mode: 'markers', name: nome,
    x: ii.map(i => S.x[i]), y: ii.map(i => S.y[i]), text: ii.map(i => S.t[i] + ' · ' + S.aptos[i] + ' aptos'),
    hovertemplate: '%{{text}}<br>1º turno: %{{x:.1%}} · 2º turno: %{{y:.1%}}<extra></extra>',
    marker: {{size: tam, color: cor, opacity: ii.length > 2000 ? 0.45 : 0.95, line: {{width: 1, color: css('--surface')}}}}}});
  Plotly.react('g_scatter', [pts(idx(0), 'sem sinalização', css('--base'), 5), pts(idx(1), 'sinalizadas', css('--hi'), 8)],
    base('1º turno — ' + D.nb + ' nos válidos', '2º turno — ' + D.nb + ' nos válidos'), cfg);
  const P = D.prev, flagP = S.f;
  Plotly.react('g_prev', [
    {{type: 'scattergl', mode: 'markers', x: P.x, y: P.y, text: S.t, hovertemplate: '%{{text}}<br>previsto %{{x:.1%}} · observado %{{y:.1%}}<extra></extra>',
      marker: {{size: 4, color: flagP.map(f => f ? css('--hi') : css('--base')), opacity: 0.6}}, showlegend: false}},
    {{type: 'scatter', mode: 'lines', x: [0, 1], y: [0, 1], line: {{color: css('--axis'), width: 1}}, hoverinfo: 'skip', showlegend: false}}],
    base('previsto', 'observado'), cfg);
  const lq = base('quantil χ² de referência', 'quantil observado'); lq.xaxis.tickformat = ''; lq.yaxis.tickformat = '';
  const mx = Math.max(...D.qq.x);
  Plotly.react('g_qq', [
    {{type: 'scatter', mode: 'lines', x: [0, mx], y: [0, mx], line: {{color: css('--axis'), width: 1}}, hoverinfo: 'skip', showlegend: false}},
    {{type: 'scattergl', mode: 'markers', x: D.qq.x, y: D.qq.y, marker: {{size: 4, color: css('--seq1')}},
      hovertemplate: 'referência %{{x:.2f}} · observado %{{y:.2f}}<extra></extra>', showlegend: false}}], lq, cfg);
  for (const k of ['k1', 'k2']) {{
    const H = D[k], l = base(D.nb + ' nos válidos', 'comparecimento');
    Plotly.react('g_' + k, [{{type: 'heatmap', x: H.x, y: H.y, z: H.z, colorscale: [[0, css('--seq0')], [0.5, css('--seq1')], [1, css('--seq2')]],
      zsmooth: false, hovertemplate: 'válidos %{{x:.0%}} · comparecimento %{{y:.0%}}: %{{z}} urnas<extra></extra>',
      colorbar: {{thickness: 10, tickfont: {{color: css('--muted'), size: 10}}, outlinewidth: 0}}}}], l, cfg);
  }}
}}
desenhar();
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', desenhar);
</script>
</body></html>
"""
