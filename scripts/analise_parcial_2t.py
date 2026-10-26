"""Análise parcial só com o 2º turno, para as UFs já coletadas (uso: analise_parcial_2t.py ac al ...).

Complementa o `reconciliar --turno 2` (integridade BU × total oficial) com o que não depende do 1º turno:
  1. urnas irmãs: cada urna contra as OUTRAS urnas do mesmo local de votação (mesma camada da Fase 1,
     aplicada à composição do 2º turno em vez do resíduo do modelo de transferência);
  2. impressão digital comparecimento × votação (enchimento aparece como urnas com ~100% nos dois eixos);
  3. horários: abertura atrasada e encerramento antes das 17h de Brasília (referência por município,
     porque o BU traz a hora local e AC/AM/RR têm outros fusos);
  4. tipo de urna registrado no BU.
Saídas em data/analise/parcial_2t/.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import polars as pl

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from eleicoes import analise  # noqa: E402
from eleicoes.consolida import STATUS_COM_BU  # noqa: E402
from eleicoes.reconcilia import candidatos_oficiais  # noqa: E402

DADOS = RAIZ / "data"
SAIDA = DADOS / "analise" / "parcial_2t"
COMP = {"a": "v13", "b": "v22"}


def urnas_uf(uf: str, oficiais: set[int]) -> pl.DataFrame:
    c = analise._contagens(DADOS, 2, uf, oficiais).filter(pl.col("status").is_in(STATUS_COM_BU) & (pl.col("aptos") > 0))
    return c.with_columns(
        (pl.col("v13") / pl.col("aptos")).alias("a"),
        (pl.col("v22") / pl.col("aptos")).alias("b"),
        ((pl.col("v95") + pl.col("v96")) / pl.col("aptos")).alias("bn"),
        (pl.col("comparecimento") / pl.col("aptos")).alias("comparec"),
        (pl.col("v13") / (pl.col("v13") + pl.col("v22"))).alias("pct13_validos"),
        pl.col("abertura").str.strptime(pl.Datetime, "%Y%m%dT%H%M%S").alias("t_abre"),
        pl.col("encerramento").str.strptime(pl.Datetime, "%Y%m%dT%H%M%S").alias("t_fecha"),
    )


def irmas(df: pl.DataFrame) -> pl.DataFrame:
    """Camada local da Fase 1 sobre a composição do 2º turno: res_k = fração; var_k = τ² + φ·p(1−p)/n,
    com τ² e φ ajustados nos desvios em relação à mediana do local."""
    g = analise._codigos(df.select(pl.format("{}-{}-{}", "cd_municipio", "nr_zona", "nr_local")).to_series().to_numpy())
    tam = np.bincount(g)[g]
    n = df["aptos"].to_numpy().astype(float)
    cols = {"nr_local_t2": df["nr_local"]}
    for k in analise.NO_SCORE:
        x = df[k].to_numpy()
        r0 = x - analise._mediana_por_grupo(x, g)
        ok = tam >= analise.MIN_URNAS_LOCAL
        tau2, phi = analise._variancia(r0[ok], x[ok], n[ok])
        p = np.clip(x, 1e-4, 1 - 1e-4)
        cols[f"res_{k}"] = x
        cols[f"var_{k}"] = tau2 + phi * p * (1 - p) / n
        cols[f"desvio_votos_{k}"] = np.round(r0 * n)  # contra a mediana do local, em votos (para o saldo)
    out, lam = analise._camada_local(df.with_columns(**{k: pl.Series(v) for k, v in cols.items()}))
    print(f"  λ local = {lam:.3f}")
    return out


def horarios(df: pl.DataFrame) -> pl.DataFrame:
    """Referência = hora cheia mais comum de abertura no município (8h de Brasília no fuso local)."""
    ref = (df.group_by("cd_municipio").agg(pl.col("t_abre").dt.truncate("1h").mode().first().alias("ref_abre")))
    return df.join(ref, on="cd_municipio").with_columns(
        ((pl.col("t_abre") - pl.col("ref_abre")).dt.total_minutes()).alias("atraso_abertura_min"),
        ((pl.col("t_fecha") - pl.col("ref_abre")).dt.total_minutes() - 9 * 60).alias("fecha_vs_17h_min"),
    )


def main(ufs: list[str]) -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    oficiais = candidatos_oficiais(DADOS, 2)
    todas = []
    for uf in ufs:
        print(f"[{uf}]")
        todas.append(horarios(irmas(urnas_uf(uf, oficiais))))
    t = pl.concat(todas, how="diagonal_relaxed").with_columns(
        (pl.col("q_local") < analise.ALFA).fill_null(False).alias("sinal_irmas"))
    zs = np.column_stack([t[f"z_local_{k}"].fill_null(0).to_numpy() for k in analise.NO_SCORE])
    i = np.argmax(np.abs(zs), axis=1)
    t = t.with_columns(
        pl.Series("componente", np.array(["13", "22", "branco+nulo"])[i]),
        pl.Series("direcao", np.where(zs[np.arange(len(i)), i] > 0, "acima das irmãs", "abaixo das irmãs")),
    )

    resumo = t.group_by("uf").agg(
        pl.len().alias("urnas"),
        pl.col("aptos").sum(), pl.col("comparecimento").sum(),
        pl.col("elegivel_local").sum().alias("urnas_com_irmas"),
        pl.col("sinal_irmas").sum().alias("sinalizadas_irmas"),
        pl.col("desvio_votos_a").filter(pl.col("sinal_irmas")).sum().alias("saldo_votos_13_sinalizadas"),
        pl.col("desvio_votos_b").filter(pl.col("sinal_irmas")).sum().alias("saldo_votos_22_sinalizadas"),
        (pl.col("comparec") >= 0.95).sum().alias("comparec_95"),
        ((pl.col("comparec") >= 0.95) & (pl.max_horizontal("pct13_validos", 1 - pl.col("pct13_validos")) >= 0.95))
        .sum().alias("comparec_95_e_voto_95"),
        (pl.col("atraso_abertura_min") > 60).sum().alias("abriu_1h_atrasada"),
        (pl.col("fecha_vs_17h_min") < -5).sum().alias("fechou_antes_17h"),
        (pl.col("tipo_urna") != 1).sum().alias("tipo_urna_nao_1"),
    ).sort("uf").with_columns(
        (100 * pl.col("sinalizadas_irmas") / pl.col("urnas_com_irmas")).round(2).alias("pct_sinalizadas"))
    resumo.write_csv(SAIDA / "resumo_parcial_2t.csv")
    cols = ["uf", "cd_municipio", "nr_zona", "nr_secao", "nr_local", "urnas_no_local", "aptos", "comparecimento",
            "v13", "v22", "v95", "v96", "pct13_validos", "comparec", "z_local_a", "z_local_b", "z_local_bn",
            "q_local", "componente", "direcao", "desvio_votos_a", "desvio_votos_b", "tipo_urna",
            "abertura", "encerramento", "atraso_abertura_min", "fecha_vs_17h_min", "hash_bu", "arquivo_bu"]
    t.filter(pl.col("sinal_irmas")).sort("q_local").select(cols).write_csv(SAIDA / "sinalizadas_irmas_2t.csv")
    t.filter((pl.col("comparec") >= 0.95)).select(cols).write_csv(SAIDA / "comparecimento_95_2t.csv")
    t.filter((pl.col("atraso_abertura_min") > 60) | (pl.col("fecha_vs_17h_min") < -5)).select(cols) \
        .write_csv(SAIDA / "horarios_atipicos_2t.csv")
    t.select(cols + ["sinal_irmas"]).write_parquet(SAIDA / "urnas_2t.parquet")
    with pl.Config(tbl_cols=30, tbl_width_chars=250, tbl_rows=40):
        print(resumo)


if __name__ == "__main__":
    main([u.lower() for u in sys.argv[1:]])
