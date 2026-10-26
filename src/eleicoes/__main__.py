"""CLI: python -m eleicoes {coletar,consolidar,reconciliar} --turno N [--uf xx ...] | analisar [--uf xx ...]"""

from __future__ import annotations

import argparse
import json
import time
import tomllib
from pathlib import Path

from . import coleta, consolida, fase1, reconcilia, tse

RAIZ = Path(__file__).resolve().parents[2]


def _cliente(cfg: dict) -> tse.Cliente:
    return tse.Cliente(
        cfg["base_url"], tse.VerificadorJws(cfg["jws"]["kid"], cfg["jws"]["x"]), cfg["taxa_req_s"], cfg["timeout_s"]
    )


def main() -> None:
    ap = argparse.ArgumentParser(prog="eleicoes")
    ap.add_argument("--config", type=Path, default=RAIZ / "config" / "eleicao_2026.toml")
    ap.add_argument("--dados", type=Path, default=RAIZ / "data")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nome in ("coletar", "consolidar", "reconciliar"):
        p = sub.add_parser(nome)
        p.add_argument("--turno", type=int, choices=(1, 2), required=True)
        p.add_argument("--uf", action="append", help="repetível; omitido = todas as UFs")
        if nome == "coletar":
            p.add_argument("--sem-zonas", action="store_true", help="não baixa os totais por zona")
            p.add_argument("--sem-raw", action="store_true", help="não grava o BU bruto (fica o hash para baixar de novo)")
    pa = sub.add_parser("analisar", help="Fase 1 por UF (exige os dois turnos coletados)")
    pa.add_argument("--uf", action="append", help="repetível; omitido = todas as UFs + resumo nacional")
    a = ap.parse_args()
    cfg = tomllib.loads(a.config.read_text())

    if a.cmd == "coletar":
        cli = _cliente(cfg)
        ele = tse.descobrir_eleicao(cli.jws("comum", "config", "ele-c.jws"), cfg["ano"], a.turno, cfg["cargo"])
        print(f"{ele.nome}: eleição {ele.codigo}, pleito {ele.pleito}")
        ufs = [u.lower() for u in (a.uf or cfg["ufs"])]
        inicio = time.time()
        resumos = []
        for uf in ufs:
            resumos.append(coleta.coletar_uf(cli, ele, uf, a.dados, cfg["threads"], cfg["cargo"], not a.sem_raw))
            if not a.sem_zonas:
                n = coleta.coletar_zonas(cli, ele, uf, a.dados, cfg["cargo"], cfg["threads"])
                print(f"[{uf} {ele.turno}T] totais oficiais de {n} zonas")
        a.dados.mkdir(parents=True, exist_ok=True)
        with (a.dados / "manifest.jsonl").open("a") as f:
            f.write(json.dumps({"quando": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "comando": "coletar",
                                "eleicao": ele.__dict__, "ufs": ufs, "resumos": resumos,
                                "requisicoes": cli.contagem, "duracao_s": round(time.time() - inicio)},
                               ensure_ascii=False) + "\n")
        print("requisições:", cli.contagem)
    elif a.cmd == "consolidar":
        for p in consolida.consolidar(a.dados, a.turno, cfg["cargo"], [u.lower() for u in a.uf or []]):
            print("gravado", p)
    elif a.cmd == "analisar":
        ufs = [u.lower() for u in (a.uf or cfg["ufs"])]
        for uf in ufs:
            try:
                print("relatório:", fase1.executar(cfg, a.dados, uf))
            except Exception as e:  # uma UF com problema não impede as outras; o erro fica no log
                print(f"[{uf}] ANÁLISE FALHOU: {e!r}")
        if len(ufs) > 1:
            print("resumo nacional:", fase1.resumo_brasil(a.dados, ufs))
    elif a.cmd == "reconciliar":
        texto = reconcilia.relatorio(a.dados, a.turno)
        destino = a.dados / "relatorios" / f"fase0_{a.turno}t.md"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(texto)
        print(texto)
        print("relatório:", destino)


if __name__ == "__main__":
    main()
