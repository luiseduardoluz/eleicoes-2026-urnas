"""Teste de integridade nº 1: soma dos BUs por zona == total oficial assinado da zona.

Os dois lados vêm do TSE, mas por caminhos diferentes: os BUs individuais (arquivo-urna) e o
resultado totalizado (dados/…-u.jws). Qualquer diferença é um fato a explicar — primeiro como
possível erro do nosso pipeline, depois como dado.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from .consolida import NR_BRANCO, NR_NULO, STATUS_COM_BU

CHAVE_ZONA = ["uf", "cd_municipio", "nr_zona"]


def _zonas_oficiais(dados: Path, turno: int) -> pl.DataFrame:
    linhas = []
    for arq in sorted((dados / "bronze" / f"{turno}t").glob("*.zonas.jsonl")):
        for linha in arq.read_text().splitlines():
            z = json.loads(linha)
            base = {"uf": z["uf"], "cd_municipio": int(z["municipio"]), "nr_zona": int(z["zona"])}
            linhas.append({**base, "metrica": "aptos", "oficial": z["aptos"]})
            linhas.append({**base, "metrica": "comparecimento", "oficial": z["comparecimento"]})
            linhas.append({**base, "metrica": f"votavel_{NR_BRANCO}", "oficial": z["brancos"]})
            linhas.append({**base, "metrica": f"votavel_{NR_NULO}", "oficial": z["nulos"]})
            for n, q in z["candidatos"].items():
                linhas.append({**base, "metrica": f"votavel_{int(n)}", "oficial": q})
    return pl.DataFrame(linhas)


def _zonas_dos_bus(dados: Path, turno: int, oficiais: set[int]) -> pl.DataFrame:
    pasta = dados / "silver" / f"{turno}t"
    urnas = pl.read_parquet(pasta / "urnas.parquet").filter(pl.col("status").is_in(STATUS_COM_BU))
    votos = pl.read_parquet(pasta / "votos.parquet")
    ap = urnas.group_by(CHAVE_ZONA).agg(pl.col("aptos").sum(), pl.col("comparecimento").sum()).unpivot(
        index=CHAVE_ZONA, variable_name="metrica", value_name="bus"
    )
    vt = (
        votos.with_columns(reclassificar_nulos(pl.col("nr_votavel"), oficiais))
        .group_by([*CHAVE_ZONA, "nr_votavel"])
        .agg(pl.col("qt_votos").sum().alias("bus"))
        .select(*CHAVE_ZONA, ("votavel_" + pl.col("nr_votavel").cast(pl.String)).alias("metrica"), "bus")
    )
    return pl.concat([ap, vt])


def candidatos_oficiais(dados: Path, turno: int) -> set[int]:
    """Números que a totalização reconhece como candidatura no turno (união de todas as zonas)."""
    return {
        int(n)
        for arq in (dados / "bronze" / f"{turno}t").glob("*.zonas.jsonl")
        for linha in arq.read_text().splitlines()
        for n in json.loads(linha)["candidatos"]
    }


def reclassificar_nulos(nr: pl.Expr, oficiais: set[int]) -> pl.Expr:
    """Voto num número que a totalização não reconhece como candidatura conta como nulo
    (ex.: registro cancelado depois da carga da urna — a urna registra como nominal)."""
    validos = sorted(oficiais | {NR_BRANCO, NR_NULO})
    return pl.when(nr.is_in(validos)).then(nr).otherwise(pl.lit(NR_NULO)).alias("nr_votavel")


def reconciliar(dados: Path, turno: int) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Devolve (comparação completa, só divergências)."""
    bus = _zonas_dos_bus(dados, turno, candidatos_oficiais(dados, turno))
    oficial = _zonas_oficiais(dados, turno).filter(pl.col("uf").is_in(bus["uf"].unique().to_list()))
    comp = oficial.join(bus, on=[*CHAVE_ZONA, "metrica"], how="full", coalesce=True).with_columns(
        pl.col("oficial").fill_null(0), pl.col("bus").fill_null(0)
    ).with_columns((pl.col("bus") - pl.col("oficial")).alias("diferenca"))
    return comp, comp.filter(pl.col("diferenca") != 0)


def relatorio(dados: Path, turno: int) -> str:
    pasta = dados / "silver" / f"{turno}t"
    urnas = pl.read_parquet(pasta / "urnas.parquet")
    comp, div = reconciliar(dados, turno)
    status = urnas.group_by("status").len().sort("status")
    zonas = comp.select(CHAVE_ZONA).unique().height
    zonas_div = div.select(CHAVE_ZONA).unique().height
    tot = comp.group_by("metrica").agg(pl.col("oficial").sum(), pl.col("bus").sum()).sort("metrica")
    linhas = [
        f"# Fase 0 — {turno}º turno: integridade e reconciliação",
        "",
        f"UFs: {', '.join(sorted(urnas['uf'].unique().to_list()))}",
        "",
        "## Urnas por status",
        "",
        "| status | urnas |",
        "|---|---|",
        *[f"| {s} | {n:,} |" for s, n in status.iter_rows()],
        "",
        f"Seções representadas (principal + agregadas): {urnas['n_secoes'].sum():,}",
        "",
        "## Reconciliação: soma dos BUs × total oficial por zona",
        "",
        f"Zonas comparadas: {zonas:,} — **com divergência: {zonas_div:,}**",
        "",
        "| métrica | oficial | soma dos BUs | diferença |",
        "|---|---:|---:|---:|",
        *[f"| {m} | {o:,} | {b:,} | {b - o:+,} |" for m, o, b in tot.iter_rows()],
    ]
    votos = pl.read_parquet(pasta / "votos.parquet")
    oficiais = candidatos_oficiais(dados, turno)
    recl = (
        votos.filter(~pl.col("nr_votavel").is_in(sorted(oficiais | {NR_BRANCO, NR_NULO})))
        .group_by("nr_votavel").agg(pl.col("qt_votos").sum(), (pl.col("qt_votos") > 0).sum().alias("urnas"))
        .filter(pl.col("qt_votos") > 0)
    )
    if recl.height:
        linhas += ["", "## Votáveis do BU reclassificados como nulos",
                   "", "Presentes na urna, ausentes do resultado oficial (a totalização conta como nulo):", "",
                   "| nr_votavel | votos | urnas com voto |", "|---:|---:|---:|",
                   *[f"| {n} | {q:,} | {u:,} |" for n, q, u in recl.sort("nr_votavel").iter_rows()]]
    if div.height:
        linhas += ["", "## Divergências (até 30)", "", "```", str(div.head(30)), "```"]
    inc = urnas.filter(pl.col("status") != "ok")
    if inc.height:
        linhas += ["", "## Urnas fora de `ok` (até 30)", "", "```",
                   str(inc.select("uf", "cd_municipio", "nr_zona", "nr_secao", "status", "problemas").head(30)), "```"]
    return "\n".join(linhas) + "\n"
