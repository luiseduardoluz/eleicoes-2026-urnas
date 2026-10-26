"""Bronze (JSONL por urna) → silver (Parquet): uma linha por urna e votos densificados.

A unidade é a URNA (seção principal + agregadas), não a seção: os votos das seções agregadas
estão no BU da principal. Votáveis sem voto não aparecem no BU e são preenchidos com zero.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

NR_BRANCO, NR_NULO = 95, 96
STATUS_COM_BU = ("ok", "inconsistente")
CHAVE = ["turno", "uf", "cd_municipio", "nr_zona", "nr_secao"]


def carregar_bronze(dados: Path, turno: int, ufs: list[str] | None = None) -> list[dict]:
    """Último registro de cada urna (a coleta é resumível e pode ter reescrito erros)."""
    ultimo: dict[tuple, dict] = {}
    for arq in sorted((dados / "bronze" / f"{turno}t").glob("*.jsonl")):
        if arq.name.endswith(".zonas.jsonl") or (ufs and arq.stem not in ufs):
            continue
        for linha in arq.read_text().splitlines():
            try:
                r = json.loads(linha)
            except json.JSONDecodeError:  # linha truncada por interrupção da coleta
                continue
            ultimo[(r["uf"], r["municipio"], r["zona"], r["secao"])] = r
    return list(ultimo.values())


def _nr_votavel(v: dict) -> int:
    return {2: NR_BRANCO, 3: NR_NULO}.get(v["tipo"], v["numero"] if v["numero"] is not None else 0)


def tabelas(registros: list[dict], turno: int, cargo: int = 1) -> tuple[pl.DataFrame, pl.DataFrame]:
    urnas, votos = [], []
    for r in registros:
        chave = {
            "turno": turno,
            "uf": r["uf"],
            "cd_municipio": int(r["municipio"]),
            "nr_zona": int(r["zona"]),
            "nr_secao": int(r["secao"]),
        }
        c = next((c for c in r.get("cargos", []) if c["cargo"] == cargo), None)
        urnas.append(
            {
                **chave,
                "nr_local": r.get("local"),
                "secoes_agregadas": [str(s) for s in r.get("agregadas", [])],
                "status": r["status"] if (c is not None or r["status"] not in STATUS_COM_BU) else "sem_cargo",
                "problemas": "; ".join(r.get("problemas", [])),
                "numero_urna": r.get("numero_urna"),
                "tipo_urna": r.get("tipo_urna"),
                "abertura": r.get("abertura"),
                "encerramento": r.get("encerramento"),
                "recebido": r.get("recebido"),
                "hash_bu": r.get("hash"),
                "arquivo_bu": r.get("arquivo"),
                "aptos": c["aptos"] if c else None,
                "comparecimento": c["comparecimento"] if c else None,
            }
        )
        if c is not None and r["status"] in STATUS_COM_BU:
            for v in c["votaveis"]:
                votos.append({**chave, "nr_votavel": _nr_votavel(v), "qt_votos": v["qtd"]})

    df_urnas = pl.DataFrame(urnas, infer_schema_length=None).with_columns(
        (pl.col("aptos") - pl.col("comparecimento")).alias("abstencao"),
        (1 + pl.col("secoes_agregadas").list.len()).alias("n_secoes"),
    )
    df_votos = pl.DataFrame(votos, schema={**{k: pl.Int64 for k in CHAVE}, "uf": pl.String,
                                           "nr_votavel": pl.Int64, "qt_votos": pl.Int64})
    return df_urnas, densificar(df_urnas, df_votos)


def densificar(urnas: pl.DataFrame, votos: pl.DataFrame) -> pl.DataFrame:
    """Toda urna com BU recebe uma linha para cada votável do turno (+ branco e nulo), com zero se faltar."""
    votaveis = pl.DataFrame({"nr_votavel": sorted(set(votos["nr_votavel"].to_list()) | {NR_BRANCO, NR_NULO})})
    com_bu = urnas.filter(pl.col("status").is_in(STATUS_COM_BU)).select(CHAVE)
    return (
        com_bu.join(votaveis, how="cross")
        .join(votos.group_by([*CHAVE, "nr_votavel"]).agg(pl.col("qt_votos").sum()), on=[*CHAVE, "nr_votavel"], how="left")
        .with_columns(pl.col("qt_votos").fill_null(0))
        .sort([*CHAVE, "nr_votavel"])
    )


def consolidar(dados: Path, turno: int, cargo: int = 1, ufs: list[str] | None = None) -> tuple[Path, Path]:
    urnas, votos = tabelas(carregar_bronze(dados, turno, ufs), turno, cargo)
    pasta = dados / "silver" / f"{turno}t"
    pasta.mkdir(parents=True, exist_ok=True)
    urnas.write_parquet(pasta / "urnas.parquet")
    votos.write_parquet(pasta / "votos.parquet")
    return pasta / "urnas.parquet", pasta / "votos.parquet"
