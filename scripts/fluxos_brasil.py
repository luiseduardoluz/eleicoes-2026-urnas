"""De onde vieram os votos ganhos pelos finalistas no 2º turno (uso: fluxos_brasil.py [reamostras]).

1. Decomposição oficial, Brasil: totais assinados de br-c0001 dos dois turnos (candidatos pelo nome).
2. Fluxos estimados: regressão ecológica de Goodman por zona eleitoral. A composição do 2º turno de cada zona
   (13, 22, brancos+nulos, abstenção, em fração dos aptos) é explicada pela composição do 1º turno (13, 22,
   cada eliminado com mais de 1% dos válidos, demais eliminados, brancos+nulos, abstenção), ponderando pelos
   aptos. Uma matriz de transição por UF (o comportamento do eleitor de um eliminado muda de região para região),
   com cada entrada em [0, 1] e cada origem distribuída inteira entre os destinos (linhas somam 1); os fluxos
   em eleitores somam as UFs. É estimativa agregada: diz para onde foram os votos das zonas, não de cada eleitor.
   Os totais do 1º turno por zona são baixados aqui (a coleta de BUs do 1º turno ainda está em andamento);
   os do 2º turno vêm de data/bronze/2t/<uf>.zonas.jsonl. O exterior (zz) fica fora da regressão.
   Com `reamostras` (ex.: 60), acrescenta o intervalo de 90% de cada percentual, reamostrando as zonas dentro
   de cada UF (cerca de 5 s por réplica).
Saídas em data/analise/fluxos/: zonas_1t.jsonl (cache), decomposicao_brasil.csv, fluxos_zonas.csv.
"""

from __future__ import annotations

import json
import sys
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import polars as pl
from scipy.optimize import minimize

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from eleicoes import tse  # noqa: E402
from eleicoes.coleta import zonas_do_cs  # noqa: E402

DADOS = RAIZ / "data"
SAIDA = DADOS / "analise" / "fluxos"
MIN_VALIDOS = 0.01  # eliminado com pelo menos 1% dos válidos no Brasil entra como coluna própria
REAMOSTRAS = int(sys.argv[1]) if len(sys.argv) > 1 else 0


def _candidatos(o, achados: dict) -> dict:
    if isinstance(o, dict):
        if "n" in o and "vap" in o:
            achados[int(o["n"])] = {"nome": o.get("nmu"), "votos": int(o["vap"])}
        for v in o.values():
            _candidatos(v, achados)
    elif isinstance(o, list):
        for v in o:
            _candidatos(v, achados)
    return achados


def _totais(p: dict) -> dict:
    e, v = p["e"], p["v"]
    return {"aptos": int(e["te"]), "comparecimento": int(e["c"]), "abstencao": int(e["a"]),
            "bn": int(v["vb"]) + int(v["tvn"]), "candidatos": _candidatos(p.get("carg", []), {})}


def transicao(X: np.ndarray, Y: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Mínimos quadrados ponderados de Y ≈ X·B com B ≥ 0 e linhas de B somando 1."""
    k, m = X.shape[1], Y.shape[1]
    sw = np.sqrt(w / w.sum())[:, None]  # pesos normalizados: escala estável para o SLSQP
    Xs, Ys = X * sw, Y * sw

    def custo(b):
        r = Ys - Xs @ b.reshape(k, m)
        return (r * r).sum()

    def gradiente(b):
        return (-2 * Xs.T @ (Ys - Xs @ b.reshape(k, m))).ravel()

    linhas = [{"type": "eq", "fun": lambda b, i=i: b.reshape(k, m)[i].sum() - 1} for i in range(k)]
    r = minimize(custo, np.full(k * m, 1 / m), jac=gradiente, bounds=[(0, 1)] * (k * m), constraints=linhas,
                 method="SLSQP", options={"maxiter": 500, "ftol": 1e-12})
    B = r.x.reshape(k, m)
    if not (r.success and np.allclose(B.sum(axis=1), 1, atol=1e-6)):
        raise RuntimeError(f"ajuste da matriz de transição não convergiu: {r.message}")
    return B


def zonas_1t(cli: tse.Cliente, ele1: tse.Eleicao, ufs: list[str]) -> list[dict]:
    cache = SAIDA / "zonas_1t.jsonl"
    feitas = {}
    if cache.exists():
        for linha in cache.read_text().splitlines():
            r = json.loads(linha)
            feitas[(r["uf"], r["municipio"], r["zona"])] = r
    pend = []
    for uf in ufs:
        cs = json.loads((DADOS / "raw" / "2t" / uf / "cs.json").read_text())  # mesmas zonas nos dois turnos
        pend += [(uf, m, z) for m, z in zonas_do_cs(cs) if (uf, m, z) not in feitas]
    print(f"zonas do 1º turno: {len(feitas)} em cache, {len(pend)} a baixar", flush=True)

    def tarefa(k):
        uf, m, z = k
        p = cli.jws(ele1.ciclo, str(ele1.codigo), "dados", uf, f"{uf}{m}-z{z}-c0001-{ele1.e6}-u.jws")
        t = _totais(p)
        t["candidatos"] = {n: c["votos"] for n, c in t["candidatos"].items()}
        return {"uf": uf, "municipio": m, "zona": z, **t}

    with ThreadPoolExecutor(8) as ex, cache.open("a") as f:
        for i, r in enumerate(ex.map(tarefa, pend), 1):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            feitas[(r["uf"], r["municipio"], r["zona"])] = r
            if i % 1000 == 0:
                print(f"  {i}/{len(pend)}", flush=True)
    return list(feitas.values())


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    cfg = tomllib.loads((RAIZ / "config" / "eleicao_2026.toml").read_text())
    cli = tse.Cliente(cfg["base_url"], tse.VerificadorJws(cfg["jws"]["kid"], cfg["jws"]["x"]), 20, cfg["timeout_s"])
    ele_c = cli.jws("comum", "config", "ele-c.jws")
    ele = {t: tse.descobrir_eleicao(ele_c, cfg["ano"], t, cfg["cargo"]) for t in (1, 2)}

    # 1. decomposição oficial
    br = {t: _totais(cli.jws(e.ciclo, str(e.codigo), "dados", "br", f"br-c0001-{e.e6}-u.jws")) for t, e in ele.items()}
    c1, c2 = br[1]["candidatos"], br[2]["candidatos"]
    validos1 = sum(c["votos"] for c in c1.values())
    linhas = [{"origem": f'{n} {c["nome"]}', "votos_1t": c["votos"], "pct_validos_1t": round(100 * c["votos"] / validos1, 2)}
              for n, c in sorted(c1.items(), key=lambda x: -x[1]["votos"]) if n not in (13, 22)]
    dec = pl.DataFrame(linhas)
    elim = dec["votos_1t"].sum()
    menos_bn = br[1]["bn"] - br[2]["bn"]
    mais_comp = br[2]["comparecimento"] - br[1]["comparecimento"]
    g13, g22 = c2[13]["votos"] - c1[13]["votos"], c2[22]["votos"] - c1[22]["votos"]
    print(f"\n13: {c1[13]['votos']:,} → {c2[13]['votos']:,} ({g13:+,}) | 22: {c1[22]['votos']:,} → {c2[22]['votos']:,} ({g22:+,})")
    print(f"ganho somado {g13 + g22:,} = eliminados {elim:,} + queda de brancos/nulos {menos_bn:,} + aumento do comparecimento {mais_comp:,}"
          f" (= {elim + menos_bn + mais_comp:,})")
    print(f"aptos {br[1]['aptos']:,} → {br[2]['aptos']:,} | abstenção {100 * br[1]['abstencao'] / br[1]['aptos']:.2f}% → "
          f"{100 * br[2]['abstencao'] / br[2]['aptos']:.2f}% | brancos+nulos {br[1]['bn']:,} → {br[2]['bn']:,}")
    with pl.Config(tbl_rows=30, fmt_str_lengths=50):
        print(dec)
    dec.write_csv(SAIDA / "decomposicao_brasil.csv")

    # 2. fluxos por zona
    ufs = [u for u in cfg["ufs"] if u != "zz"]
    z1 = zonas_1t(cli, ele[1], ufs)
    z2 = [json.loads(l) for uf in ufs for l in (DADOS / "bronze" / "2t" / f"{uf}.zonas.jsonl").read_text().splitlines()]
    proprios = [n for n, c in c1.items() if n not in (13, 22) and c["votos"] / validos1 >= MIN_VALIDOS]
    proprios.sort(key=lambda n: -c1[n]["votos"])
    nomes_x = ["13", "22", *[str(n) for n in proprios], "outros_elim", "bn", "abst"]

    def x_de(r):
        cand = {int(k): v for k, v in r["candidatos"].items()}
        outros = sum(v for k, v in cand.items() if k not in (13, 22, *proprios))
        return [cand.get(13, 0), cand.get(22, 0), *[cand.get(n, 0) for n in proprios], outros, r["bn"], r["abstencao"]]

    d1 = {(r["uf"], r["municipio"], r["zona"]): r for r in z1}
    destinos = ("13", "22", "bn", "abst")
    por_uf = {}
    for uf in ufs:
        X, Y, W = [], [], []
        for r in z2:
            k = (r["uf"], r["municipio"], r["zona"])
            if r["uf"] != uf or k not in d1 or r["aptos"] == 0:
                continue
            X.append(np.array(x_de(d1[k])) / d1[k]["aptos"])
            cand = {int(n): v for n, v in r["candidatos"].items()}
            Y.append(np.array([cand.get(13, 0), cand.get(22, 0), r["brancos"] + r["nulos"], r["abstencao"]]) / r["aptos"])
            W.append(r["aptos"])
        por_uf[uf] = np.array(X), np.array(Y), np.array(W, float)

    def fluxos(amostra=None) -> np.ndarray:
        """Eleitores de cada origem × destino, somados nas UFs. `amostra(n)` sorteia as zonas usadas no ajuste;
        a matriz ajustada é sempre aplicada às zonas reais."""
        total = np.zeros((len(nomes_x), 4))
        for X, Y, W in por_uf.values():
            i = amostra(len(W)) if amostra else slice(None)
            total += (X * W[:, None]).sum(axis=0)[:, None] * transicao(X[i], Y[i], W[i])
        return total

    fluxo = fluxos()
    prev = sum(((X @ transicao(X, Y, W)) * W[:, None]).sum(axis=0) for X, Y, W in por_uf.values())
    obs = sum((Y * W[:, None]).sum(axis=0) for _, Y, W in por_uf.values())
    print(f"\nzonas na regressão: {sum(len(W) for *_, W in por_uf.values()):,} em {len(ufs)} UFs")
    rot = {"13": "13", "22": "22", "outros_elim": "outros eliminados", "bn": "brancos e nulos", "abst": "abstenção"}
    origem = fluxo.sum(axis=1)
    flu = pl.DataFrame({
        "origem_1t": [rot.get(n) or f"{n} {c1[int(n)]['nome']}" for n in nomes_x],
        "eleitores_1t": np.round(origem).astype(int),
        **{f"pct_para_{d}": np.round(100 * fluxo[:, j] / origem, 1) for j, d in enumerate(destinos)},
        **{f"para_{d}": np.round(fluxo[:, j]).astype(int) for j, d in enumerate(destinos[:2])},
    })
    if REAMOSTRAS:
        # intervalo de 90% por reamostragem das zonas dentro de cada UF: mede o ruído, não o viés ecológico
        rng = np.random.default_rng(1)
        reps = np.array([fluxos(lambda n: rng.integers(0, n, n)) for _ in range(REAMOSTRAS)])
        pct = 100 * reps / reps.sum(axis=2, keepdims=True)
        flu = flu.with_columns(
            *[pl.Series(f"pct_para_{d}_{q}", np.round(np.percentile(pct[:, :, j], p, axis=0), 1))
              for j, d in enumerate(destinos) for q, p in (("p05", 5), ("p95", 95))])
    flu.write_csv(SAIDA / "fluxos_zonas.csv")
    print("ajuste (soma prevista × observada, milhões):",
          {d: (round(prev[j] / 1e6, 2), round(obs[j] / 1e6, 2)) for j, d in enumerate(destinos)})
    print(f"ganho líquido implícito: 13 {fluxo[:, 0].sum() - origem[0]:+,.0f} | 22 {fluxo[:, 1].sum() - origem[1]:+,.0f}")
    with pl.Config(tbl_rows=30, tbl_cols=12, tbl_width_chars=200, fmt_str_lengths=40):
        print(flu)
    print("requisições:", cli.contagem)


if __name__ == "__main__":
    main()
