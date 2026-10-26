"""Votos sem biometria no fim do dia, a partir da saída de logs_urnas.py (uso: analise_logs.py <rótulo> <uf>).

1. Perfil por hora no estado: fração de cada tipo de habilitação, 1º × 2º turno.
2. Urna a urna: votos sem biometria na última hora frente ao esperado pela taxa da própria urna no resto do
   dia (cauda superior binomial; q-valor de Benjamini-Hochberg entre as urnas).
3. Efeito no resultado: o excesso no fim do dia contra a variação do comparecimento e o resíduo do modelo
   1º × 2º turno (Fase 1, data/analise/<uf>/urnas_<uf>.parquet).
Saídas em data/analise/logs/<rótulo>/: fim_do_dia.csv (uma linha por urna e turno) e perfil_horas.csv.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import polars as pl
from scipy import stats

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from eleicoes.analise import ALFA, benjamini_hochberg  # noqa: E402

SEM_BIO = ("mesario", "nao_associada", "dado_pessoal", "sem_bio_cadastrada")


def main(rotulo: str, uf: str) -> None:
    pasta = RAIZ / "data" / "analise" / "logs" / rotulo
    u = pl.read_csv(pasta / "urnas.csv", schema_overrides={"municipio": pl.String})
    h = pl.read_parquet(pasta / "horas.parquet")
    pl.Config.set_tbl_rows(40), pl.Config.set_tbl_cols(20), pl.Config.set_tbl_width_chars(230)

    ok = u.filter(pl.col("votos_log") == pl.col("comparecimento_bu"))
    print(f"urnas×turno: {u.height} | log confere com o BU: {ok.height} | não confere: {u.height - ok.height}"
          f" (tipo de urna: {u.filter(pl.col('votos_log') != pl.col('comparecimento_bu'))['tipo_urna'].value_counts().rows()})")

    # 1. perfil por hora
    perfil = (h.group_by("turno", "hora").agg(
        pl.col("votos").sum().alias("votos"),
        *[pl.col("votos").filter(pl.col("tipo") == t).sum().alias(t) for t in ("biometrica", *SEM_BIO)])
        .with_columns((100 * (1 - pl.col("biometrica") / pl.col("votos"))).round(1).alias("pct_sem_bio"),
                      (100 * pl.col("nao_associada") / pl.col("votos")).round(2).alias("pct_nao_assoc"))
        .sort("turno", "hora"))
    perfil.write_csv(pasta / "perfil_horas.csv")
    print("\n-- perfil por hora (votos e % sem biometria) --")
    print(perfil.select("turno", "hora", "votos", "pct_sem_bio", "pct_nao_assoc").pivot(on="turno", index="hora", values=["votos", "pct_sem_bio", "pct_nao_assoc"]).sort("hora"))

    # 2. teste por urna: última hora × resto do dia
    t = ok.with_columns(
        pl.sum_horizontal(*SEM_BIO).alias("sem_bio"),
        pl.sum_horizontal(*[f"{s}_ultima_hora" for s in SEM_BIO]).alias("sem_bio_fim"),
    ).with_columns(
        (pl.col("votos_log") - pl.col("votos_ultima_hora")).alias("votos_resto"),
        (pl.col("sem_bio") - pl.col("sem_bio_fim")).alias("sem_bio_resto"),
    ).with_columns(
        ((pl.col("sem_bio_resto") + 0.5) / (pl.col("votos_resto") + 1)).alias("taxa_resto"),  # suavizada
    ).with_columns(
        (pl.col("sem_bio_fim") - pl.col("votos_ultima_hora") * pl.col("taxa_resto")).alias("excesso_fim"),
    )
    p = stats.binom.sf(t["sem_bio_fim"].to_numpy() - 1, t["votos_ultima_hora"].to_numpy(), t["taxa_resto"].to_numpy())
    p = np.where(t["votos_ultima_hora"].to_numpy() > 0, p, 1.0)
    t = t.with_columns(pl.Series("p_fim", p))
    t = pl.concat([g.with_columns(pl.Series("q_fim", benjamini_hochberg(g["p_fim"].to_numpy())))
                   for g in t.partition_by("turno", maintain_order=True)])
    t = t.with_columns((pl.col("q_fim") < ALFA).alias("sinal_fim"))

    # 3. efeito no resultado (só 2º turno, urnas pareadas na Fase 1)
    f1 = pl.read_parquet(RAIZ / "data" / "analise" / uf / f"urnas_{uf}.parquet").select(
        pl.col("cd_municipio").cast(pl.String).str.zfill(5).alias("municipio"), "zona", "secao", pl.col("municipio").alias("nome"),
        "residuo_pp_13", "residuo_pp_22", "residuo_pp_abstencao", "sinal_modelo",
        (pl.col("pct_aptos_abstencao_1t") - pl.col("pct_aptos_abstencao_2t")).alias("queda_abstencao_pp"))
    t = t.join(f1, on=["municipio", "zona", "secao"], how="left")
    t.write_csv(pasta / "fim_do_dia.csv")

    for turno in (1, 2):
        x = t.filter(pl.col("turno") == turno)
        print(f"\n-- {turno}º turno: urnas com excesso de votos sem biometria na última hora (q < {ALFA}): "
              f"{x['sinal_fim'].sum()} de {x.height} | excesso total {x['excesso_fim'].clip(lower_bound=0).sum():.0f} votos"
              f" (positivo) | líquido {x['excesso_fim'].sum():+.0f}")
    x2 = t.filter(pl.col("turno") == 2)
    s = x2.filter(pl.col("sinal_fim"))
    print("\n-- 2º turno: urnas sinalizadas no fim do dia --")
    print(s.sort("q_fim").select("nome", "zona", "secao", "votos_log", "votos_ultima_hora", "sem_bio_fim", pl.col("taxa_resto").mul(100).round(1).alias("taxa_resto_%"),
                                 pl.col("excesso_fim").round(1), "maior_sequencia_sem_bio_ultima_hora", "nao_associada_ultima_hora", "mesario_ultima_hora",
                                 pl.col("q_fim").round(5), pl.col("queda_abstencao_pp").round(1), pl.col("residuo_pp_13").round(1), pl.col("residuo_pp_22").round(1), "sinal_modelo").head(30))
    # as mesmas urnas no 1º turno
    t1 = t.filter(pl.col("turno") == 1).select("municipio", "zona", "secao", pl.col("sinal_fim").alias("sinal_fim_1t"))
    s = s.join(t1, on=["municipio", "zona", "secao"], how="left")
    print(f"sinalizadas no 2º turno que também eram no 1º: {s['sinal_fim_1t'].sum()} de {s.height}")

    # efeito: correlação entre excesso no fim do dia e resíduos / comparecimento
    y = x2.drop_nulls(["residuo_pp_13", "excesso_fim"]).with_columns((pl.col("excesso_fim") / pl.col("votos_log") * 100).alias("excesso_pp"))
    for col in ("queda_abstencao_pp", "residuo_pp_13", "residuo_pp_22"):
        r, pv = stats.spearmanr(y["excesso_pp"], y[col])
        print(f"Spearman(excesso no fim do dia, {col}) = {r:+.3f} (p = {pv:.2g}, n = {y.height})")
    g = y.group_by("sinal_fim").agg(pl.len(), pl.col("queda_abstencao_pp").mean().round(2), pl.col("residuo_pp_13").mean().round(2),
                                    pl.col("residuo_pp_22").mean().round(2), pl.col("sinal_modelo").mean().round(4))
    print(g)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
