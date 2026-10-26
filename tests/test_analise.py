import numpy as np
import polars as pl
import pytest

from eleicoes import analise

# Matriz de transferência conhecida: linhas = 1º turno (A, B, eliminados, branco+nulo, abstenção),
# colunas = 2º turno (A, B, branco+nulo, abstenção).
T = np.array([
    [0.90, 0.03, 0.02, 0.05],
    [0.03, 0.90, 0.02, 0.05],
    [0.40, 0.40, 0.10, 0.10],
    [0.20, 0.20, 0.50, 0.10],
    [0.05, 0.05, 0.00, 0.90],
])


def _urna(rng, mun, i, aptos, c1):
    c2 = sum(rng.multinomial(c, T[j]) for j, c in enumerate(c1))
    return {"cd_municipio": mun, "nr_zona": 1, "nr_secao": i, "nr_local_t2": i // 4,
            "aptos_t1": aptos, "aptos_t2": aptos,
            "a_t1": c1[0], "b_t1": c1[1], "elim_t1": c1[2], "bn_t1": c1[3],
            "a_t2": c2[0], "b_t2": c2[1], "bn_t2": c2[2], "comparecimento_t2": aptos - c2[3]}


def _municipios(rng, n_mun=4, n_urnas=250):
    linhas = []
    for m in range(n_mun):
        centro = rng.dirichlet([35, 30, 15, 5, 15])
        for i in range(n_urnas):
            aptos = int(rng.integers(150, 400))
            linhas.append(_urna(rng, m, i, aptos, rng.multinomial(aptos, rng.dirichlet(200 * centro))))
    return linhas


def _fracoes(linhas):
    df = pl.DataFrame(linhas)
    return df.with_columns(
        *[(pl.col(f"{c}_t1") / pl.col("aptos_t1")).alias(f"f_{c}_t1") for c in ("a", "b", "elim", "bn")],
        (1 - (pl.col("a_t1") + pl.col("b_t1") + pl.col("elim_t1") + pl.col("bn_t1")) / pl.col("aptos_t1")).alias("f_abst_t1"),
        *[(pl.col(f"{c}_t2") / pl.col("aptos_t2")).alias(f"f_{c}_t2") for c in ("a", "b", "bn")],
        (1 - pl.col("comparecimento_t2") / pl.col("aptos_t2")).alias("f_abst_t2"),
    )


@pytest.fixture(scope="module")
def resultado():
    rng = np.random.default_rng(7)
    linhas = _municipios(rng)
    # Caso do briefing: 1º turno A=60, B=40, outros=20, branco/nulo=10 (abstenção 30 de 160 aptos);
    # 2º turno A=30, B=90, branco/nulo=10, mesmo comparecimento.
    linhas.append({"cd_municipio": 0, "nr_zona": 1, "nr_secao": 9999, "nr_local_t2": 9999 // 4,
                   "aptos_t1": 160, "aptos_t2": 160, "a_t1": 60, "b_t1": 40, "elim_t1": 20, "bn_t1": 10,
                   "a_t2": 30, "b_t2": 90, "bn_t2": 10, "comparecimento_t2": 130})
    return analise.classificar(analise.modelar(_fracoes(linhas)).urnas)


def test_caso_do_briefing_e_sinalizado(resultado):
    caso = resultado.filter(pl.col("nr_secao") == 9999).row(0, named=True)
    assert caso["sinal_modelo"]
    assert caso["q_modelo"] < 1e-6
    # esperado pela matriz: A ≈ 0,9·60 + 0,03·40 + 0,4·20 + 0,2·10 + 0,05·30 ≈ 67 de 160 aptos
    assert caso["prev_a_t2"] == pytest.approx(66.7 / 160, abs=0.04)
    assert caso["res_a"] < -0.2 and caso["res_b"] > 0.2


def test_urnas_normais_nao_sao_sinalizadas_alem_do_nominal(resultado):
    normais = resultado.filter(pl.col("nr_secao") != 9999)
    assert normais["sinal_modelo"].mean() < analise.ALFA
    for k in ("a", "b", "bn"):
        z = normais[f"z_{k}"].to_numpy()
        assert abs(np.median(z)) < 0.1
        assert 1.4826 * np.median(np.abs(z - np.median(z))) == pytest.approx(1, abs=0.05)


def test_modelo_recupera_a_matriz_de_transferencia(resultado):
    rng = np.random.default_rng(11)
    coef = analise.modelar(_fracoes(_municipios(rng))).coeficientes
    b = coef.filter(pl.col("componente_2t") == "b").row(0, named=True)
    # relativo à abstenção do 1º turno (0,05 → B): B fica com ~0,90−0,05 dos seus e ~0,40−0,05 dos eliminados
    assert b["de_b_1t"] == pytest.approx(0.85, abs=0.06)
    assert b["de_elim_1t"] == pytest.approx(0.35, abs=0.08)


def test_injecao_preserva_aptos_e_comparecimento_na_troca():
    df = _fracoes(_municipios(np.random.default_rng(3), n_mun=1, n_urnas=50))
    alvo = np.zeros(df.height, dtype=bool)
    alvo[:10] = True
    out = analise.injetar(df, "troca_A_para_B", 0.10, alvo)
    assert (out["a_t2"] + out["b_t2"]).equals(df["a_t2"] + df["b_t2"])
    assert out["comparecimento_t2"].equals(df["comparecimento_t2"])
    assert (out["a_t2"].to_numpy()[alvo] < df["a_t2"].to_numpy()[alvo]).all()


def test_benjamini_hochberg():
    p = np.array([0.01, 0.04, 0.03, 0.20, np.nan])
    q = analise.benjamini_hochberg(p)
    # ordenados: 0,01·4/1=0,04 · 0,03·4/2=0,06 · 0,04·4/3=0,0533 · 0,20 → mínimo acumulado de trás para frente
    assert np.allclose(q[:4], [0.04, 0.16 / 3, 0.16 / 3, 0.20])
    assert np.isnan(q[4])
