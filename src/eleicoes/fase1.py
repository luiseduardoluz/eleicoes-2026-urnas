"""Orquestra a Fase 1 por UF (consolida, reconcilia, pareia, modela, grava) e junta as UFs numa visão nacional."""

from __future__ import annotations

import json
import time
from pathlib import Path

import polars as pl

from . import analise, consolida, reconcilia, relatorio, tse
from .consolida import STATUS_COM_BU


def _nomes_candidatos(cli: tse.Cliente, ele: tse.Eleicao, dados: Path) -> dict[int, str]:
    cache = dados / "raw" / f"{ele.turno}t" / "candidatos.json"
    if not cache.exists():
        p = cli.jws(ele.ciclo, str(ele.codigo), "dados", "br", f"br-c0001-{ele.e6}-u.jws")
        nomes = {}

        def andar(o):
            if isinstance(o, dict):
                if "n" in o and "nmu" in o:
                    nomes[o["n"]] = o["nmu"]
                for v in o.values():
                    andar(v)
            elif isinstance(o, list):
                for v in o:
                    andar(v)

        andar(p["carg"])
        cache.write_text(json.dumps(nomes, ensure_ascii=False))
    return {int(k): v for k, v in json.loads(cache.read_text()).items()}


def _integridade(dados: Path, turno: int) -> dict:
    urnas = pl.read_parquet(dados / "silver" / f"{turno}t" / "urnas.parquet")
    comp, div = reconcilia.reconciliar(dados, turno)
    votos = pl.read_parquet(dados / "silver" / f"{turno}t" / "votos.parquet")
    oficiais = reconcilia.candidatos_oficiais(dados, turno)
    recl = (votos.filter(~pl.col("nr_votavel").is_in(sorted(oficiais | {95, 96})) & (pl.col("qt_votos") > 0))
            .group_by("nr_votavel").agg(pl.col("qt_votos").sum()).sort("nr_votavel"))
    tot = comp.group_by("metrica").agg(pl.col("oficial").sum())
    get = lambda m: tot.filter(pl.col("metrica") == m)["oficial"].sum()
    return {
        "urnas_ok": urnas.filter(pl.col("status").is_in(STATUS_COM_BU)).height,
        "urnas_outras": urnas.filter(~pl.col("status").is_in(STATUS_COM_BU)).height,
        "zonas": comp.select("uf", "cd_municipio", "nr_zona").unique().height,
        "zonas_div": div.select("uf", "cd_municipio", "nr_zona").unique().height,
        "aptos": get("aptos"), "comparecimento": get("comparecimento"),
        "reclassificados": ", ".join(f"nº {n}: {q} votos" for n, q in recl.iter_rows()),
        "divergencias": div,
    }


def executar(cfg: dict, dados: Path, uf: str, log=print) -> Path:
    uf = uf.lower()
    for t in (1, 2):
        consolida.consolidar(dados, t, cfg["cargo"], [uf])
    integridade = {t: _integridade(dados, t) for t in (1, 2)}
    for t in (1, 2):
        log(f"[{uf}] integridade {t}T: {integridade[t]['zonas']} zonas, {integridade[t]['zonas_div']} com diferença")

    cli = tse.Cliente(cfg["base_url"], tse.VerificadorJws(cfg["jws"]["kid"], cfg["jws"]["x"]), 5, cfg["timeout_s"])
    ele_c = cli.jws("comum", "config", "ele-c.jws")
    eles = {t: tse.descobrir_eleicao(ele_c, cfg["ano"], t, cfg["cargo"]) for t in (1, 2)}
    nomes_cand = {**_nomes_candidatos(cli, eles[1], dados), **_nomes_candidatos(cli, eles[2], dados)}
    cs = json.loads((dados / "raw" / "2t" / uf / "cs.json").read_text())
    nomes_mun = {int(m["cd"]): m["nm"] for a in cs["abr"] for m in a["mu"]}

    def url_bu(turno: int, r: dict) -> str | None:
        h, arq = r[f"hash_bu_t{turno}"], r[f"arquivo_bu_t{turno}"]
        if not h:
            return None
        e = eles[turno]
        return cli.url(e.ciclo, "arquivo-urna", str(e.pleito), "dados", uf, f'{r["cd_municipio"]:05d}',
                       f'{r["nr_zona"]:04d}', f'{r["nr_secao"]:04d}', h, arq)

    par = analise.parear(dados, uf)
    log(f"[{uf}] {par.pareadas.height} urnas pareadas, {par.excluidas.height} fora; A={par.cand_a} B={par.cand_b}")
    res = analise.analisar(par)
    sens = analise.sensibilidade(par)
    tab = relatorio.tabela_urnas(par, res, nomes_mun, nomes_cand, url_bu)

    pasta = dados / "analise" / uf
    pasta.mkdir(parents=True, exist_ok=True)
    tab.write_csv(pasta / f"urnas_{uf}.csv")
    tab.write_parquet(pasta / f"urnas_{uf}.parquet")
    par.excluidas.select(*analise.CHAVE, "motivo_exclusao", "status_t1", "status_t2").write_csv(pasta / f"fora_do_pareamento_{uf}.csv")
    res.coeficientes.write_csv(pasta / f"transferencias_{uf}.csv")
    sens.write_csv(pasta / f"sensibilidade_{uf}.csv")
    for t in (1, 2):
        if integridade[t]["divergencias"].height:
            integridade[t]["divergencias"].write_csv(pasta / f"divergencias_integridade_{t}t.csv")
    gerado = time.strftime("%d/%m/%Y %H:%M")
    html_path = pasta / f"relatorio_{uf}.html"
    html_path.write_text(relatorio.gerar_html(uf, par, res, tab, sens, integridade, nomes_cand, gerado,
                                                          dados / "cache" / "plotly-2.35.2.min.js"))
    (pasta / "resumo.json").write_text(json.dumps({
        "uf": uf, "gerado": gerado, "pareadas": par.pareadas.height, "fora": par.excluidas.height,
        "sinalizadas_modelo": int(res.urnas["sinal_modelo"].sum()), "sinalizadas_local": int(res.urnas["sinal_local"].sum()),
        "lambda_modelo": res.lambda_modelo, "lambda_local": res.lambda_local, "variancia": res.variancia,
        "integridade": {t: {k: v for k, v in integridade[t].items() if k != "divergencias"} for t in (1, 2)},
        "eleicoes": {t: eles[t].__dict__ for t in (1, 2)},
    }, ensure_ascii=False, indent=1, default=str))
    return html_path


def resumo_brasil(dados: Path, ufs: list[str]) -> Path:
    """Junta as saídas por UF: uma linha por UF (resumo_brasil.csv) e todas as urnas sinalizadas."""
    linhas, sinalizadas = [], []
    for uf in ufs:
        pasta = dados / "analise" / uf
        if not (pasta / "resumo.json").exists():
            continue
        r = json.loads((pasta / "resumo.json").read_text())
        tab = pl.read_parquet(pasta / f"urnas_{uf}.parquet")
        s = tab.filter(pl.col("sinalizada"))
        sinalizadas.append(s)
        # saldo em votos das sinalizadas frente ao previsto, por finalista (residuo_pp_<número>)
        saldo = {f"saldo_votos_{c.removeprefix('residuo_pp_')}": round(float((s[c] * s["aptos_t2"] / 100).sum()))
                 for c in tab.columns if c.startswith("residuo_pp_") and c.removeprefix("residuo_pp_").isdigit()}
        integ = r["integridade"]
        linhas.append({
            "uf": uf.upper(), "pareadas": r["pareadas"], "fora": r["fora"], "sinalizadas": s.height,
            "pct_sinalizadas": round(100 * s.height / max(1, r["pareadas"]), 2),
            "sinal_modelo": r["sinalizadas_modelo"], "sinal_local": r["sinalizadas_local"],
            "lambda_modelo": round(r["lambda_modelo"], 3),
            **{f"zonas_{t}t": integ[t]["zonas"] for t in ("1", "2")},
            **{f"zonas_div_{t}t": integ[t]["zonas_div"] for t in ("1", "2")},
            **{f"urnas_sem_bu_{t}t": integ[t]["urnas_outras"] for t in ("1", "2")},
            **saldo,
        })
    pasta = dados / "analise" / "brasil"
    pasta.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(linhas).write_csv(pasta / "resumo_brasil.csv")
    if sinalizadas:
        pl.concat(sinalizadas, how="diagonal_relaxed").write_csv(pasta / "sinalizadas_brasil.csv")
    return pasta / "resumo_brasil.csv"
