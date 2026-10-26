"""Fatos curiosos do 2º turno, a partir dos BUs consolidados (uso: curiosidades_2t.py).

Lê data/silver/2t (o que estiver consolidado) e imprime: urnas unânimes e empates, comparecimento extremo,
brancos e nulos, tamanho das urnas, tipo de urna, horários de abertura e encerramento (inclusive a
concentração de encerramentos às 19h, efeito da prorrogação da votação), extremos por município, por UF e
no exterior. Os horários do BU são locais; a referência de cada município é a hora cheia de abertura mais
comum nele, que equivale às 8h de Brasília.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

RAIZ = Path(__file__).resolve().parents[1]
DADOS = RAIZ / "data"
SEL = ["uf", "nome", "nr_zona", "nr_secao", "aptos", "comparecimento", "v13", "v22", "v95", "v96"]


def carregar() -> pl.DataFrame:
    u = pl.read_parquet(DADOS / "silver" / "2t" / "urnas.parquet").filter(pl.col("status") == "ok")
    v = pl.read_parquet(DADOS / "silver" / "2t" / "votos.parquet")
    nomes = []
    for uf in u["uf"].unique():
        cs = json.loads((DADOS / "raw" / "2t" / uf / "cs.json").read_text())
        nomes += [{"uf": uf, "cd_municipio": int(m["cd"]), "nome": m["nm"]} for a in cs["abr"] for m in a["mu"]]
    k = ["uf", "cd_municipio", "nr_zona", "nr_secao"]
    w = v.pivot(on="nr_votavel", index=k, values="qt_votos", aggregate_function="sum").fill_null(0)
    w = w.rename({c: f"v{c}" for c in w.columns if c not in k})
    t = u.join(w, on=k, how="left").join(pl.DataFrame(nomes), on=["uf", "cd_municipio"], how="left").with_columns(
        (pl.col("v13") + pl.col("v22")).alias("validos"),
        (pl.col("comparecimento") / pl.col("aptos")).alias("comparec"),
        pl.col("abertura").str.strptime(pl.Datetime, "%Y%m%dT%H%M%S").alias("ab"),
        pl.col("encerramento").str.strptime(pl.Datetime, "%Y%m%dT%H%M%S").alias("enc"),
    )
    ref = t.group_by("uf", "cd_municipio").agg(pl.col("ab").dt.truncate("1h").mode().first().alias("ref"))
    return t.join(ref, on=["uf", "cd_municipio"]).with_columns(
        ((pl.col("enc") - pl.col("ref")).dt.total_minutes() + 8 * 60).alias("fecha_min_brasilia"),
        (pl.col("ab") - pl.col("ref")).dt.total_minutes().alias("atraso_abertura_min"),
    )


def main() -> None:
    pl.Config.set_tbl_rows(25), pl.Config.set_tbl_cols(20), pl.Config.set_tbl_width_chars(200)
    pl.Config.set_fmt_str_lengths(40), pl.Config.set_tbl_hide_dataframe_shape(True)
    t = carregar()
    print(f"UFs: {t['uf'].n_unique()} | urnas: {t.height:,}")

    print("\n== unanimidade (todos os válidos num só candidato), urnas com >= 50 válidos ==")
    un = t.filter((pl.col("validos") >= 50) & ((pl.col("v13") == 0) | (pl.col("v22") == 0)))
    print(un.group_by(pl.when(pl.col("v22") == 0).then(pl.lit("só 13")).otherwise(pl.lit("só 22")).alias("lado"))
          .agg(pl.len(), pl.col("validos").max()))
    print(un.sort("validos", descending=True).select(SEL).head(10))
    print("\n== empate exato 13 = 22 (>= 100 válidos):", t.filter((pl.col("v13") == pl.col("v22")) & (pl.col("validos") >= 100)).height, "urnas")

    print("\n== comparecimento ==")
    print("100% (aptos >= 50):")
    print(t.filter((pl.col("comparec") >= 1) & (pl.col("aptos") >= 50)).select(SEL))
    print("menor (aptos >= 100):")
    print(t.filter(pl.col("aptos") >= 100).sort("comparec").select(*SEL, pl.col("comparec").round(3)).head(8))

    print("\n== brancos + nulos, maiores proporções (comparecimento >= 100) ==")
    print(t.filter(pl.col("comparecimento") >= 100)
          .with_columns(((pl.col("v95") + pl.col("v96")) / pl.col("comparecimento")).round(3).alias("bn"))
          .sort("bn", descending=True).select(*SEL, "bn").head(8))

    print("\n== tipo de urna (4 = contingência) ==")
    print(t["tipo_urna"].value_counts().sort("tipo_urna"))
    print(t.filter(~pl.col("tipo_urna").is_in([1, 4])).select(*SEL, "abertura", "encerramento"))
    print("contingência por UF (%):", t.group_by("uf").agg((pl.col("tipo_urna") == 4).mean().mul(100).round(2).alias("pct"))
          .sort("pct", descending=True).head(6).rows())

    print("\n== encerramento (horário de Brasília equivalente; Brasil, sem o exterior) ==")
    br = t.filter(pl.col("uf") != "zz")
    faixas = br.with_columns((pl.col("fecha_min_brasilia") // 15 * 15).alias("faixa")) \
        .filter(pl.col("faixa") >= 17 * 60).group_by("faixa").len().sort("faixa")
    print([(f"{f // 60}h{f % 60:02d}", n) for f, n in faixas.rows()])
    as19 = br.filter(pl.col("fecha_min_brasilia").is_between(19 * 60, 19 * 60 + 15))
    print(f"encerradas entre 19h00 e 19h15: {as19.height:,} em {as19.select('uf', 'cd_municipio').n_unique()} municípios;"
          f" por UF: {as19.group_by('uf').len().sort('len', descending=True).head(6).rows()}")
    print("encerraram mais tarde:")
    print(t.sort("fecha_min_brasilia", descending=True).select(*SEL, "encerramento").head(5))
    print("maior atraso de abertura:")
    print(t.sort("atraso_abertura_min", descending=True).select(*SEL, "abertura", "atraso_abertura_min").head(6))

    print("\n== municípios ==")
    m = t.group_by("uf", "cd_municipio", "nome").agg(pl.col("aptos", "comparecimento", "v13", "v22").sum()).with_columns(
        (100 * pl.col("v13") / (pl.col("v13") + pl.col("v22"))).round(2).alias("pct13"),
        (100 * pl.col("comparecimento") / pl.col("aptos")).round(2).alias("comparec"),
        (pl.col("v13") - pl.col("v22")).abs().alias("dif"))
    cols = ["uf", "nome", "aptos", "v13", "v22", "pct13"]
    grandes = m.filter(pl.col("aptos") >= 1000)
    print("mais votos para o 13:", grandes.sort("pct13", descending=True).select(cols).head(5))
    print("mais votos para o 22:", grandes.sort("pct13").select(cols).head(5))
    print("menor diferença:", m.sort("dif", "aptos", descending=[False, True]).select(*cols, "dif").head(8))
    print("comparecimento, Brasil:", m.filter(pl.col("uf") != "zz").sort("comparec").select("uf", "nome", "aptos", "comparec").head(3),
          m.filter(pl.col("uf") != "zz").sort("comparec", descending=True).select("uf", "nome", "aptos", "comparec").head(3))

    print("\n== UFs ==")
    print(t.group_by("uf").agg(pl.col("aptos", "comparecimento", "v13", "v22").sum()).with_columns(
        (100 * pl.col("v13") / (pl.col("v13") + pl.col("v22"))).round(2).alias("pct13"),
        (100 * pl.col("comparecimento") / pl.col("aptos")).round(2).alias("comparec")).sort("pct13"))


if __name__ == "__main__":
    main()
