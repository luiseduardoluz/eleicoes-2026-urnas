"""Fase 1 — pareamento 1º × 2º turno por urna, modelo de transferência e sinalização (SPEC §6–8).

Resultado por urna: resíduo de cada componente do 2º turno (A, B, branco+nulo, abstenção) frente
a (i) um modelo de transferência robusto com efeito fixo de município e (ii) as urnas irmãs do mesmo
local; score de Mahalanobis calibrado pelo centro da distribuição; q-valor de Benjamini-Hochberg.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import polars as pl
import statsmodels.api as sm
from scipy import stats

from .consolida import NR_BRANCO, NR_NULO
from .reconcilia import candidatos_oficiais

CHAVE = ["uf", "cd_municipio", "nr_zona", "nr_secao"]
COMPONENTES = ("a", "b", "bn", "abst")  # composição do 2º turno, em fração dos aptos
NO_SCORE = ("a", "b", "bn")             # abstenção = 1 − soma: fica fora do score (seria redundante)
ALFA = 0.05
MIN_URNAS_LOCAL = 3
MAX_VARIACAO_APTOS = 0.10  # acima disso a urna sai do pareamento (eleitorado_mudou)
MEDIANA_QUI2_3 = stats.chi2.ppf(0.5, 3)


# ---------------------------------------------------------------- pareamento

def _contagens(dados: Path, turno: int, uf: str, oficiais: set[int]) -> pl.DataFrame:
    pasta = dados / "silver" / f"{turno}t"
    urnas = pl.read_parquet(pasta / "urnas.parquet").filter(pl.col("uf") == uf)
    votos = pl.read_parquet(pasta / "votos.parquet").filter(pl.col("uf") == uf)
    reconhecidos = sorted(oficiais | {NR_BRANCO, NR_NULO})
    largo = (
        votos.with_columns(
            pl.when(pl.col("nr_votavel").is_in(reconhecidos)).then(pl.col("nr_votavel"))
            .otherwise(pl.lit(NR_NULO)).alias("nr_votavel")  # número sem candidatura = nulo (SPEC §2)
        )
        .group_by([*CHAVE, "nr_votavel"]).agg(pl.col("qt_votos").sum())
        .pivot(on="nr_votavel", index=CHAVE, values="qt_votos").fill_null(0)
    )
    largo = largo.rename({c: f"v{c}" for c in largo.columns if c not in CHAVE})
    return urnas.join(largo, on=CHAVE, how="left")


@dataclass
class Pareamento:
    pareadas: pl.DataFrame
    excluidas: pl.DataFrame
    cand_a: int
    cand_b: int
    eliminados: list[int]


def parear(dados: Path, uf: str) -> Pareamento:
    of1, of2 = candidatos_oficiais(dados, 1), candidatos_oficiais(dados, 2)
    if len(of2) != 2:
        raise ValueError(f"esperava 2 candidatos no 2º turno, achei {sorted(of2)}")
    a, b = sorted(of2)
    elim = sorted(of1 - {a, b})

    def turno(t: int, oficiais: set[int], com_elim: bool) -> pl.DataFrame:
        df = _contagens(dados, t, uf, oficiais)
        col = lambda n: pl.col(f"v{n}") if f"v{n}" in df.columns else pl.lit(0)
        exprs = [
            col(a).fill_null(0).alias("a"), col(b).fill_null(0).alias("b"),
            (col(NR_BRANCO).fill_null(0) + col(NR_NULO).fill_null(0)).alias("bn"),
        ]
        if com_elim:
            exprs.append(pl.sum_horizontal([col(n).fill_null(0) for n in elim]).alias("elim"))
        meta = ["nr_local", "secoes_agregadas", "status", "aptos", "comparecimento", "numero_urna",
                "tipo_urna", "abertura", "encerramento", "hash_bu", "arquivo_bu"]
        out = df.select(*CHAVE, *meta, *exprs).with_columns(
            pl.col("secoes_agregadas").list.sort().list.join(",").alias("secoes_agregadas")
        )
        return out.rename({c: f"{c}_t{t}" for c in out.columns if c not in CHAVE})

    df = turno(1, of1, True).join(turno(2, of2, False), on=CHAVE, how="full", coalesce=True)
    df = df.with_columns(
        pl.when(pl.col("status_t1").is_null()).then(pl.lit("sem_par_1t"))
        .when(pl.col("status_t2").is_null()).then(pl.lit("sem_par_2t"))
        .when(pl.col("status_t1") != "ok").then(pl.lit("1t_") + pl.col("status_t1"))
        .when(pl.col("status_t2") != "ok").then(pl.lit("2t_") + pl.col("status_t2"))
        .when(pl.col("secoes_agregadas_t1") != pl.col("secoes_agregadas_t2")).then(pl.lit("agregacao_mudou"))
        .when((pl.col("aptos_t1") <= 0) | (pl.col("aptos_t2") <= 0)).then(pl.lit("sem_aptos"))
        # Eleitorado diferente entre turnos (ex.: voto em trânsito, pedido por turno): composição não é comparável
        .when((pl.col("aptos_t2") / pl.col("aptos_t1") - 1).abs() > MAX_VARIACAO_APTOS).then(pl.lit("eleitorado_mudou"))
        .otherwise(None).alias("motivo_exclusao"),
        (pl.col("nr_local_t1") != pl.col("nr_local_t2")).alias("local_mudou"),
        (pl.col("numero_urna_t1") != pl.col("numero_urna_t2")).alias("urna_trocada"),
    )
    pareadas = df.filter(pl.col("motivo_exclusao").is_null())
    for t, comps in ((1, ("a", "b", "bn", "elim")), (2, ("a", "b", "bn"))):
        pareadas = pareadas.with_columns(
            *[(pl.col(f"{c}_t{t}") / pl.col(f"aptos_t{t}")).alias(f"f_{c}_t{t}") for c in comps],
            (1 - pl.col(f"comparecimento_t{t}") / pl.col(f"aptos_t{t}")).alias(f"f_abst_t{t}"),
        )
    return Pareamento(pareadas, df.filter(pl.col("motivo_exclusao").is_not_null()), a, b, elim)


# ---------------------------------------------------------------- modelo

def _codigos(valores: np.ndarray) -> np.ndarray:
    return np.unique(valores, return_inverse=True)[1]


def _centrar(m: np.ndarray, g: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Subtrai a média ponderada do grupo (efeito fixo de município)."""
    soma_w = np.bincount(g, weights=w)
    if m.ndim == 1:
        return m - (np.bincount(g, weights=w * m) / soma_w)[g]
    return np.column_stack([_centrar(m[:, j], g, w) for j in range(m.shape[1])])


def _mediana_por_grupo(x: np.ndarray, g: np.ndarray) -> np.ndarray:
    df = pl.DataFrame({"g": g, "x": x})
    med = df.group_by("g").agg(pl.col("x").median())
    return df.join(med, on="g", how="left")["x_right"].to_numpy()


def _variancia(r: np.ndarray, p: np.ndarray, n: np.ndarray) -> tuple[float, float]:
    """Var(r) = τ² + φ·p(1−p)/n, ajustado por mínimos quadrados ponderados iterados em r²
    (com r² winsorizado no p99 do valor padronizado, para os desvios não ditarem a escala)."""
    p = np.clip(p, 1e-4, 1 - 1e-4)
    u = p * (1 - p) / n
    tau2, phi = (1.4826 * np.median(np.abs(r - np.median(r)))) ** 2 / 2, 1.0
    for _ in range(20):
        v = tau2 + phi * u
        z2 = r**2 / v
        r2 = np.minimum(z2, np.quantile(z2, 0.99)) * v
        sw = 1 / v
        coef, *_ = np.linalg.lstsq(np.column_stack([np.ones_like(u), u]) * sw[:, None], r2 * sw, rcond=None)
        tau2, phi = max(coef[0], 1e-10), max(coef[1], 0.0)
    return tau2, phi


def _mahalanobis(z: np.ndarray) -> tuple[np.ndarray, float, np.ndarray]:
    """D² com correlação estimada em z winsorizado; λ = mediana(D²)/mediana(χ²₃) recalibra o centro
    (nos dois sentidos — é o nulo empírico; o valor de λ vai para o relatório)."""
    corr = np.corrcoef(np.clip(z, -4, 4).T)
    d2 = np.einsum("ij,jk,ik->i", z, np.linalg.inv(corr), z)
    lam = float(np.median(d2) / MEDIANA_QUI2_3)
    return d2, lam, stats.chi2.sf(d2 / lam, 3)


def benjamini_hochberg(p: np.ndarray) -> np.ndarray:
    q = np.full_like(p, np.nan, dtype=float)
    ok = ~np.isnan(p)
    pv = p[ok]
    ordem = np.argsort(pv)
    m = len(pv)
    ajust = pv[ordem] * m / np.arange(1, m + 1)
    ajust = np.minimum.accumulate(ajust[::-1])[::-1]
    saida = np.empty(m)
    saida[ordem] = np.minimum(ajust, 1)
    q[ok] = saida
    return q


@dataclass
class Resultado:
    urnas: pl.DataFrame
    coeficientes: pl.DataFrame
    lambda_modelo: float
    lambda_local: float
    variancia: dict = field(default_factory=dict)


def modelar(p: pl.DataFrame) -> Resultado:
    X = p.select("f_a_t1", "f_b_t1", "f_elim_t1", "f_bn_t1").to_numpy()  # abstenção_t1: referência
    g = _codigos(p["cd_municipio"].to_numpy())
    w = p["aptos_t2"].to_numpy().astype(float)
    n = w
    Xc, sw = _centrar(X, g, w), np.sqrt(w)
    cols, coefs, variancia = {}, [], {}
    for k in COMPONENTES:
        y = p[f"f_{k}_t2"].to_numpy()
        fit = sm.RLM(_centrar(y, g, w) * sw, Xc * sw[:, None], M=sm.robust.norms.HuberT()).fit()
        beta = fit.params
        base = y - X @ beta
        pred = X @ beta + _mediana_por_grupo(base, g)  # efeito fixo robusto (mediana do município)
        r = y - pred
        tau2, phi = _variancia(r, pred, n)
        pc = np.clip(pred, 1e-4, 1 - 1e-4)
        var = tau2 + phi * pc * (1 - pc) / n
        z = r / np.sqrt(var)
        # Nulo empírico: a forma da variância vem do modelo; a escala, do centro da distribuição de z.
        escala = 1.4826 * np.median(np.abs(z - np.median(z)))
        cols[f"prev_{k}_t2"], cols[f"res_{k}"] = pred, r
        cols[f"var_{k}"], cols[f"z_{k}"] = var * escala**2, z / escala
        variancia[k] = {"tau2": tau2, "phi": phi, "escala_z": escala}
        coefs.append({"componente_2t": k, **dict(zip(("de_a_1t", "de_b_1t", "de_elim_1t", "de_bn_1t"), beta))})

    z = np.column_stack([cols[f"z_{k}"] for k in NO_SCORE])
    d2, lam, pval = _mahalanobis(z)
    cols.update(d2_modelo=d2, p_modelo=pval, q_modelo=benjamini_hochberg(pval))
    out = p.with_columns(*[pl.Series(k, v) for k, v in cols.items()])
    out, lam_local = _camada_local(out)
    return Resultado(out, pl.DataFrame(coefs), lam, lam_local, variancia)


def _camada_local(df: pl.DataFrame) -> tuple[pl.DataFrame, float]:
    """Camada 3: resíduo da urna contra a mediana das OUTRAS urnas do mesmo local (leave-one-out)."""
    grupos = df.select("cd_municipio", "nr_zona", "nr_local_t2").to_numpy()
    _, g = np.unique(grupos, axis=0, return_inverse=True)
    g = g.ravel()
    tam = np.bincount(g)[g]
    elegivel = tam >= MIN_URNAS_LOCAL
    res = {k: df[f"res_{k}"].to_numpy() for k in NO_SCORE}
    var = {k: df[f"var_{k}"].to_numpy() for k in NO_SCORE}
    z3 = {k: np.full(df.height, np.nan) for k in NO_SCORE}
    ordem = np.argsort(g, kind="stable")
    limites = np.flatnonzero(np.diff(g[ordem])) + 1
    for idx in np.split(ordem, limites):
        m = len(idx)
        if m < MIN_URNAS_LOCAL:
            continue
        for k in NO_SCORE:
            r, v = res[k][idx], var[k][idx]
            for j in range(m):
                outros = np.delete(np.arange(m), j)
                d = r[j] - np.median(r[outros])
                vd = v[j] + (np.pi / 2) * v[outros].mean() / (m - 1)
                z3[k][idx[j]] = d / np.sqrt(vd)
    for k in NO_SCORE:
        zk = z3[k][elegivel]
        if zk.size:
            z3[k][elegivel] = zk / (1.4826 * np.median(np.abs(zk - np.median(zk))))
    p3 = np.full(df.height, np.nan)
    d23 = np.full(df.height, np.nan)
    lam = 1.0
    if elegivel.any():
        zz = np.column_stack([z3[k][elegivel] for k in NO_SCORE])
        d2, lam, pv = _mahalanobis(zz)
        d23[elegivel], p3[elegivel] = d2, pv
    return df.with_columns(
        *[pl.Series(f"z_local_{k}", z3[k]) for k in NO_SCORE],
        pl.Series("urnas_no_local", tam), pl.Series("elegivel_local", elegivel),
        pl.Series("d2_local", d23), pl.Series("p_local", p3),
        pl.Series("q_local", benjamini_hochberg(p3)),
    ), lam


def classificar(df: pl.DataFrame) -> pl.DataFrame:
    zs = ["z_a", "z_b", "z_bn", "z_abst"]
    nomes = pl.Series([["CAND_A", "CAND_B", "branco+nulo", "abstenção"][i] for i in
                       np.argmax(np.abs(df.select(zs).to_numpy()), axis=1)])
    sinal = np.sign(df.select(zs).to_numpy()[np.arange(df.height), np.argmax(np.abs(df.select(zs).to_numpy()), axis=1)])
    return df.with_columns(
        (pl.col("q_modelo") < ALFA).alias("sinal_modelo"),
        (pl.col("q_local") < ALFA).fill_null(False).alias("sinal_local"),
        pl.Series("componente_principal", nomes),
        pl.Series("direcao", np.where(sinal > 0, "acima do esperado", "abaixo do esperado")),
        (pl.when(pl.col("a_t1") >= pl.col("b_t1")).then(pl.lit("A")).otherwise(pl.lit("B"))
         != pl.when(pl.col("a_t2") >= pl.col("b_t2")).then(pl.lit("A")).otherwise(pl.lit("B"))).alias("inversao"),
        (pl.max_horizontal("a_t2", "b_t2") / (pl.col("a_t2") + pl.col("b_t2")) > 0.95).alias("quase_unanime_2t"),
    )


def analisar(par: Pareamento) -> Resultado:
    res = modelar(par.pareadas)
    res.urnas = classificar(res.urnas)
    return res


# ---------------------------------------------------------------- sensibilidade (injeção sintética)

def _recalcular(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        *[(pl.col(f"{c}_t2") / pl.col("aptos_t2")).alias(f"f_{c}_t2") for c in ("a", "b", "bn")],
        (1 - pl.col("comparecimento_t2") / pl.col("aptos_t2")).alias("f_abst_t2"),
    )


def injetar(df: pl.DataFrame, cenario: str, intensidade: float, alvo: np.ndarray) -> pl.DataFrame:
    """Perturba o 2º turno das urnas `alvo` (máscara) com um mecanismo conhecido."""
    a, b, bn = (df[f"{c}_t2"].to_numpy().copy() for c in ("a", "b", "bn"))
    comp, aptos = df["comparecimento_t2"].to_numpy().copy(), df["aptos_t2"].to_numpy()
    q = np.round(intensidade * aptos).astype(int)
    if cenario == "troca_A_para_B":
        mv = np.minimum(q, a); a = a - mv * alvo; b = b + mv * alvo
    elif cenario == "troca_B_para_A":
        mv = np.minimum(q, b); b = b - mv * alvo; a = a + mv * alvo
    elif cenario == "enchimento_B":   # votos de ausentes, todos para B
        mv = np.minimum(q, aptos - comp); b = b + mv * alvo; comp = comp + mv * alvo
    elif cenario == "anulacao":       # válidos convertidos em nulo, proporcionalmente
        val = a + b
        mv = np.minimum(q, val)
        ma = np.where(val > 0, np.round(mv * a / np.maximum(val, 1)), 0).astype(int)
        a = a - ma * alvo; b = b - (mv - ma) * alvo; bn = bn + mv * alvo
    else:
        raise ValueError(cenario)
    return _recalcular(df.with_columns(pl.Series("a_t2", a), pl.Series("b_t2", b), pl.Series("bn_t2", bn),
                                       pl.Series("comparecimento_t2", comp)))


def sensibilidade(par: Pareamento, frac_alvo: float = 0.02, semente: int = 2026,
                  cenarios=("troca_A_para_B", "troca_B_para_A", "enchimento_B", "anulacao"),
                  intensidades=(0.02, 0.05, 0.10, 0.20)) -> pl.DataFrame:
    rng = np.random.default_rng(semente)
    base = par.pareadas
    alvo = np.zeros(base.height, dtype=bool)
    # 2% das urnas: pouco o bastante para a perturbação não deformar o próprio ajuste do modelo
    alvo[rng.choice(base.height, size=max(1, round(frac_alvo * base.height)), replace=False)] = True
    linhas = []
    for c in cenarios:
        for x in intensidades:
            r = modelar(injetar(base, c, x, alvo)).urnas
            sm_ = (r["q_modelo"] < ALFA).to_numpy()
            sl = (r["q_local"] < ALFA).fill_null(False).to_numpy()
            linhas.append({
                "cenario": c, "intensidade_pp_aptos": round(100 * x),
                "detectadas_modelo": float(sm_[alvo].mean()),
                "detectadas_modelo_ou_local": float((sm_ | sl)[alvo].mean()),
                "sinalizadas_nao_alvo": float((sm_ | sl)[~alvo].mean()),
                "urnas_alvo": int(alvo.sum()),
            })
    return pl.DataFrame(linhas)
