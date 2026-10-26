"""Coleta dos BUs de uma UF/turno pela API: cs (seções) → aux (hashes) → bu.dat.

Resumível: cada urna vira uma linha em data/bronze/<turno>t/<uf>.jsonl; ao reiniciar, só o que
não terminou é pedido de novo. O .dat bruto fica em data/raw para auditoria.
"""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path

from . import bu
from .tse import Bloqueado, Cliente, Eleicao, NaoEncontrado

# sem_bu_totalizado não é final: o status do aux pode atualizar depois, então é pedido de novo.
STATUS_FINAIS = {"ok", "inconsistente", "sem_recebimento", "bu_invalido"}


def urnas_do_cs(cs: dict) -> list[dict]:
    """Uma entrada por urna: seções agregadas (`nsp`) não têm arquivo de urna e são descartadas."""
    urnas = []
    for abr in cs["abr"]:
        for mu in abr["mu"]:
            for z in mu["zon"]:
                for s in z["sec"]:
                    if "nsp" in s:
                        continue
                    urnas.append(
                        {
                            "municipio": mu["cd"],
                            "zona": z["cd"],
                            "secao": s["ns"],
                            "agregadas": list(s.get("nsa", [])),
                            "recebido": f'{s["da"]} {s["ha"]}' if "da" in s else None,
                        }
                    )
    return urnas


def zonas_do_cs(cs: dict) -> list[tuple[str, str]]:
    return sorted({(mu["cd"], z["cd"]) for abr in cs["abr"] for mu in abr["mu"] for z in mu["zon"]})


def _processar_urna(cli: Cliente, ele: Eleicao, uf: str, u: dict, pasta_raw: Path | None, cargo: int) -> dict:
    reg = {"uf": uf, **{k: u[k] for k in ("municipio", "zona", "secao", "agregadas", "recebido")}}
    if u["recebido"] is None:
        return {**reg, "status": "sem_recebimento"}

    base = [ele.ciclo, "arquivo-urna", str(ele.pleito), "dados", uf, u["municipio"], u["zona"], u["secao"]]
    aux = cli.jws(*base, f'{ele.p6}-{uf}-m{u["municipio"]}-z{u["zona"]}-s{u["secao"]}-aux.jws')
    hashes = aux.get("hashes", [])
    totalizados = [h for h in hashes if h.get("st") == "Totalizado"]
    reg.update(st_aux=aux.get("st"), n_hashes=len(hashes), st_hashes=[h.get("st") for h in hashes])
    # O aux de algumas zonas fica em "Recebido" mesmo com a zona 100% totalizada no resultado oficial
    # (ex.: Lauro de Freitas/BA, zona 180, 2º turno). Aceita um BU único "Recebido"; a reconciliação
    # por zona confirma se a soma bate com o total oficial.
    if len(totalizados) == 1:
        h = totalizados[0]
    elif not totalizados and len(hashes) == 1 and hashes[0].get("st") == "Recebido":
        h = hashes[0]
    else:
        return {**reg, "status": "sem_bu_totalizado"}
    reg["st_bu"] = h.get("st")
    arq = next((a["nm"] for a in h.get("arq", []) if a.get("tp") == "bu"), None)
    if arq is None:
        return {**reg, "status": "sem_bu_totalizado"}
    dados = cli.get(*base, h["hash"], arq)
    if pasta_raw is not None:  # sem o bruto, o BU continua recuperável pelo hash + arquivo registrados abaixo
        (pasta_raw / f'{u["municipio"]}-{u["zona"]}-{u["secao"]}-bu.dat').write_bytes(dados)
    reg.update(hash=h["hash"], arquivo=arq, bu_recebido=f'{h.get("dr")} {h.get("hr")}')

    try:
        b = bu.ler(dados)
    except bu.BoletimInvalido as e:
        return {**reg, "status": "bu_invalido", "problemas": [str(e)]}
    problemas = bu.conferir(b)
    if (b.municipio, b.zona, b.secao) != (int(u["municipio"]), int(u["zona"]), int(u["secao"])):
        problemas.append(f"BU identifica outra seção: {b.municipio}/{b.zona}/{b.secao}")
    if b.pleito is not None and b.pleito != ele.pleito:
        problemas.append(f"BU do pleito {b.pleito}, esperado {ele.pleito}")
    corpo = asdict(b)
    corpo.pop("municipio"), corpo.pop("zona"), corpo.pop("secao")
    # Votável a votável só do cargo analisado; dos demais, os totais (o .dat bruto guarda tudo).
    for c, original in zip(corpo["cargos"], b.cargos):
        if c["cargo"] != cargo:
            c["votaveis"] = None
            c["soma"] = original.soma
    return {**reg, **corpo, "status": "inconsistente" if problemas else "ok", "problemas": problemas}


def _ja_feitos(arquivo: Path) -> set[tuple[str, str, str]]:
    feitos = set()
    if arquivo.exists():
        for linha in arquivo.read_text().splitlines():
            try:
                r = json.loads(linha)
            except json.JSONDecodeError:  # última linha truncada por interrupção: a urna é refeita
                continue
            if r["status"] in STATUS_FINAIS:
                feitos.add((r["municipio"], r["zona"], r["secao"]))
    return feitos


def coletar_uf(cli: Cliente, ele: Eleicao, uf: str, dados: Path, threads: int, cargo: int = 1,
               salvar_raw: bool = True, log=print) -> dict:
    pasta_raw = dados / "raw" / f"{ele.turno}t" / uf
    pasta_bu = pasta_raw / "bu"
    pasta_bu.mkdir(parents=True, exist_ok=True)
    pasta_bronze = dados / "bronze" / f"{ele.turno}t"
    pasta_bronze.mkdir(parents=True, exist_ok=True)

    cs = cli.jws(ele.ciclo, "arquivo-urna", str(ele.pleito), "config", uf, f"{uf}-{ele.p6}-cs.jws")
    (pasta_raw / "cs.json").write_text(json.dumps(cs, ensure_ascii=False))
    urnas = urnas_do_cs(cs)
    saida = pasta_bronze / f"{uf}.jsonl"
    feitos = _ja_feitos(saida)
    pendentes = [u for u in urnas if (u["municipio"], u["zona"], u["secao"]) not in feitos]
    log(f"[{uf} {ele.turno}T] {len(urnas)} urnas no cs, {len(feitos)} já coletadas, {len(pendentes)} pendentes")

    trava, parar = threading.Lock(), threading.Event()
    contagem: dict[str, int] = {}
    inicio = time.monotonic()

    def tarefa(u: dict) -> dict:
        if parar.is_set():
            return {}
        try:
            return _processar_urna(cli, ele, uf, u, pasta_bu if salvar_raw else None, cargo)
        except Bloqueado:
            parar.set()
            raise
        except (NaoEncontrado, ConnectionError, ValueError) as e:
            return {"uf": uf, **{k: u[k] for k in ("municipio", "zona", "secao")}, "status": "erro", "problemas": [repr(e)]}

    with ThreadPoolExecutor(threads) as ex, saida.open("a") as f:
        futuros = [ex.submit(tarefa, u) for u in pendentes]
        for i, fut in enumerate(as_completed(futuros), 1):
            reg = fut.result()
            if not reg:
                continue
            with trava:
                f.write(json.dumps(reg, ensure_ascii=False) + "\n")
                contagem[reg["status"]] = contagem.get(reg["status"], 0) + 1
            if i % 500 == 0 or i == len(futuros):
                taxa = i / max(1e-9, time.monotonic() - inicio)
                log(f"[{uf} {ele.turno}T] {i}/{len(futuros)} ({taxa:.1f} urnas/s) {contagem}")
    return {"uf": uf, "turno": ele.turno, "urnas_cs": len(urnas), "novas": contagem}


def coletar_zonas(cli: Cliente, ele: Eleicao, uf: str, dados: Path, cargo: int, threads: int) -> int:
    """Totais oficiais por zona (assinados), usados na reconciliação com a soma dos BUs."""
    cs = json.loads((dados / "raw" / f"{ele.turno}t" / uf / "cs.json").read_text())
    zonas = zonas_do_cs(cs)

    def tarefa(mz: tuple[str, str]) -> dict:
        mun, zona = mz
        p = cli.jws(ele.ciclo, str(ele.codigo), "dados", uf, f"{uf}{mun}-z{zona}-c{cargo:04d}-{ele.e6}-u.jws")
        cands = {}

        def andar(o):
            if isinstance(o, dict):
                if "vap" in o and "n" in o:
                    cands[o["n"]] = int(o["vap"])
                for v in o.values():
                    andar(v)
            elif isinstance(o, list):
                for v in o:
                    andar(v)

        andar(p.get("carg", []))
        e, v = p["e"], p["v"]
        return {
            "uf": uf, "municipio": mun, "zona": zona, "gerado": f'{p.get("dg")} {p.get("hg")}',
            "totalizacao_final": p.get("tf"), "secoes_totalizadas": int(p["s"]["st"]), "secoes": int(p["s"]["ts"]),
            "aptos": int(e["te"]), "comparecimento": int(e["c"]), "abstencao": int(e["a"]),
            "brancos": int(v["vb"]), "nulos": int(v["tvn"]), "nominais": int(v["vnom"]), "candidatos": cands,
        }

    with ThreadPoolExecutor(threads) as ex:
        regs = list(ex.map(tarefa, zonas))
    destino = dados / "bronze" / f"{ele.turno}t" / f"{uf}.zonas.jsonl"
    destino.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in regs))
    return len(regs)
