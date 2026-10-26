"""Habilitação de eleitores pelo log da urna (uso: logs_urnas.py [opções] ba | ba:33413 ...).

Para cada urna pedida (UF inteira ou município), baixa o log do 2º turno (`-log.jez`, um ZIP com `logd.dat`,
na mesma pasta do BU). O log acumula o histórico da urna desde a carga, então o mesmo arquivo traz o 1º turno
quando a urna é a mesma; se não trouxer (urna trocada ou de contingência), baixa o log do 1º turno.
Cada voto computado é classificado pela forma como o eleitor foi habilitado:
  - biometrica: "Tipo de habilitação do eleitor [biométrica]";
  - mesario: a digital falhou; dado pessoal conferido e um mesário registrado liberou com a própria digital
    ("Mesário N habilitou o eleitor");
  - nao_associada: idem, mas a digital que liberou não é de mesário registrado ("Digital coletada bate com
    uma digital gravada após o registro inicial de mesário. Não é possível associar a habilitação...");
  - dado_pessoal: a digital falhou e o eleitor foi liberado sem digital de mesário reconhecida;
  - sem_bio_cadastrada: nenhuma tentativa de digital (eleitor sem biometria no cadastro).
Saídas em data/analise/logs/<rótulo>/: urnas.csv (uma linha por urna e turno, com a conferência votos no
log × comparecimento do BU), horas.parquet (contagem por urna, turno, hora e tipo) e, com --votos,
votos.parquet (um registro por voto — só para alvos pequenos). Cada urna processada vai para
parcial_<uf>.jsonl assim que termina; rodar de novo retoma de onde parou.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import tomllib
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

import polars as pl

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from eleicoes import tse  # noqa: E402

DADOS = RAIZ / "data"
COMPUTADO = "O voto do eleitor foi computado"
INICIO_ELEITOR = "Identificador do eleitor digitado pelo mesário"
RE_MESARIO = re.compile(r"Mesário (\d+) habilitou o eleitor")
NAO_ASSOCIADA = "Digital coletada bate com uma digital gravada após o registro inicial de mesário"
TIPOS = ("biometrica", "mesario", "nao_associada", "dado_pessoal", "sem_bio_cadastrada")


def coletadas(turno: int, uf: str, municipios: set[str] | None) -> dict[tuple[str, str, str], dict]:
    """Último registro com BU de cada seção (a coleta pode ter regravado uma seção)."""
    regs = {}
    arquivo = DADOS / "bronze" / f"{turno}t" / f"{uf}.jsonl"
    if not arquivo.exists():  # turno ainda não coletado nessa UF: só o outro turno entra
        return regs
    for linha in arquivo.open():
        r = json.loads(linha)
        if (municipios is None or r["municipio"] in municipios) and r.get("hash") and r["status"] in ("ok", "inconsistente"):
            regs[(r["municipio"], r["zona"], r["secao"])] = r
    return regs


def baixar_log(cli: tse.Cliente, ele: tse.Eleicao, uf: str, r: dict, guardar: bool) -> bytes:
    destino = DADOS / "raw" / "logs" / f"{ele.turno}t" / uf / f'{r["municipio"]}-{r["zona"]}-{r["secao"]}-log.jez'
    if destino.exists():
        return destino.read_bytes()
    conteudo = cli.get(ele.ciclo, "arquivo-urna", str(ele.pleito), "dados", uf, r["municipio"], r["zona"], r["secao"],
                       r["hash"], r["arquivo"].replace("-bu.dat", "-log.jez"))
    if guardar:
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(conteudo)
    return conteudo


def votos_por_dia(conteudo: bytes) -> dict[str, list[dict]]:
    """Votos computados agrupados pelo dia (dd/mm/aaaa) em que aconteceram."""
    texto = zipfile.ZipFile(BytesIO(conteudo)).read("logd.dat").decode("latin-1")
    dias: dict[str, list[dict]] = {}
    janela, dia_atual = [], None
    for linha in texto.splitlines():
        p = linha.split("\t")
        if len(p) < 5:
            continue
        if p[0][:10] != dia_atual:
            janela, dia_atual = [], p[0][:10]
        if p[4] == INICIO_ELEITOR:
            janela = []  # cada eleitor começa quando o mesário digita o identificador
        janela.append(p[4])
        if p[4] != COMPUTADO:
            continue
        mesario = next((m.group(1) for m in map(RE_MESARIO.match, janela) if m), None)
        tentativas = sum(m.startswith("Solicita digital. Tentativa") for m in janela)
        if "Tipo de habilitação do eleitor [biométrica]" in janela:
            tipo = "biometrica"
        elif mesario:
            tipo = "mesario"
        elif any(m.startswith(NAO_ASSOCIADA) for m in janela):
            tipo = "nao_associada"
        elif tentativas:
            tipo = "dado_pessoal"
        else:
            tipo = "sem_bio_cadastrada"
        dias.setdefault(dia_atual, []).append({"hora": datetime.strptime(p[0], "%d/%m/%Y %H:%M:%S"), "tipo": tipo,
                                               "mesario": mesario, "tentativas_digital": tentativas})
        janela = []
    return dias


def maior_sequencia(votos: list[dict]) -> tuple[int, datetime | None]:
    """Maior sequência de votos seguidos sem biometria e a hora do primeiro deles."""
    maior, inicio, atual, ini_atual = 0, None, 0, None
    for v in votos:
        if v["tipo"] == "biometrica":
            atual = 0
            continue
        atual += 1
        ini_atual = v["hora"] if atual == 1 else ini_atual
        if atual > maior:
            maior, inicio = atual, ini_atual
    return maior, inicio


def resumir(uf: str, chave: tuple[str, str, str], turno: int, r: dict, votos: list[dict], hora_ref: int) -> tuple[dict, list[dict]]:
    mun, zona, secao = chave
    dia = datetime.strptime(r["abertura"][:8], "%Y%m%d")
    ultima_hora = dia + timedelta(hours=hora_ref + 8)  # 8h–17h de Brasília; o log usa a hora local da urna
    fim = [v for v in votos if v["hora"] >= ultima_hora]
    seq, seq_ini = maior_sequencia(votos)
    seq_fim, _ = maior_sequencia(fim)
    comparec = next(c["comparecimento"] for c in r["cargos"] if c["cargo"] == 1)
    base = {"uf": uf, "municipio": mun, "zona": int(zona), "secao": int(secao), "turno": turno}
    resumo = {
        **base, "local": r.get("local"), "tipo_urna": r.get("tipo_urna"), "numero_urna": r.get("numero_urna"),
        "votos_log": len(votos), "comparecimento_bu": comparec,
        **{t: sum(v["tipo"] == t for v in votos) for t in TIPOS},
        "votos_ultima_hora": len(fim),
        **{f"{t}_ultima_hora": sum(v["tipo"] == t for v in fim) for t in TIPOS if t != "biometrica"},
        "maior_sequencia_sem_bio": seq, "inicio_maior_sequencia": seq_ini.strftime("%H:%M") if seq_ini else None,
        "maior_sequencia_sem_bio_ultima_hora": seq_fim,
        "mesarios_distintos": len({v["mesario"] for v in votos if v["mesario"]}),
        "primeiro_voto": votos[0]["hora"].strftime("%H:%M") if votos else None,
        "ultimo_voto": votos[-1]["hora"].strftime("%H:%M") if votos else None,
        "inicio_ultima_hora": ultima_hora.strftime("%H:%M"),
    }
    horas = Counter((v["hora"].hour, v["tipo"]) for v in votos)
    return resumo, [{**base, "hora": h, "tipo": t, "votos": n} for (h, t), n in horas.items()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("alvos", nargs="+", help="uf (todas as urnas) ou uf:municipio")
    ap.add_argument("--rotulo", required=True, help="pasta de saída em data/analise/logs/")
    ap.add_argument("--taxa", type=float, default=20, help="requisições/s (somadas à coleta, abaixo de 100)")
    ap.add_argument("--threads", type=int, default=12)
    ap.add_argument("--guardar-brutos", action="store_true", help="grava os .jez em data/raw/logs/")
    ap.add_argument("--votos", action="store_true", help="grava também um registro por voto")
    a = ap.parse_args()

    cfg = tomllib.loads((RAIZ / "config" / "eleicao_2026.toml").read_text())
    cli = tse.Cliente(cfg["base_url"], tse.VerificadorJws(cfg["jws"]["kid"], cfg["jws"]["x"]), a.taxa, cfg["timeout_s"])
    ele_c = cli.jws("comum", "config", "ele-c.jws")
    ele = {t: tse.descobrir_eleicao(ele_c, cfg["ano"], t, cfg["cargo"]) for t in (1, 2)}
    por_uf: dict[str, set[str] | None] = {}
    for alvo in a.alvos:
        uf, _, mun = alvo.lower().partition(":")
        por_uf[uf] = None if not mun else ((por_uf.get(uf) or set()) | {mun.zfill(5)})

    pasta = DADOS / "analise" / "logs" / a.rotulo
    pasta.mkdir(parents=True, exist_ok=True)
    resumos, horas, votos_todos, erros = [], [], [], Counter()
    inicio = time.monotonic()
    for uf, muns in por_uf.items():
        parcial = pasta / f"parcial_{uf}.jsonl"
        feitas = set()
        if parcial.exists():
            for linha in parcial.open():
                try:
                    reg = json.loads(linha)
                except json.JSONDecodeError:  # última linha cortada por uma interrupção: a urna é refeita
                    continue
                feitas.add(tuple(reg["chave"]))
                resumos.extend(reg["resumos"]), horas.extend(reg["horas"])
        regs = {t: coletadas(t, uf, muns) for t in (1, 2)}
        # hora cheia mais comum de abertura no município = 8h de Brasília no fuso local
        hora_ref = {(t, m): Counter(int(r["abertura"][9:11]) for (mm, _, _), r in regs[t].items() if mm == m).most_common(1)[0][0]
                    for t in (1, 2) for m in {k[0] for k in regs[t]}}
        chaves = sorted((regs[2].keys() | regs[1].keys()) - feitas)
        print(f"[{uf}] {len(chaves)} urnas a processar, {len(feitas)} já feitas", flush=True)

        def tarefa(chave):
            saida = []
            dias = votos_por_dia(baixar_log(cli, ele[2], uf, regs[2][chave], a.guardar_brutos)) if chave in regs[2] else {}
            for t in (2, 1):
                r = regs[t].get(chave)
                if r is None:
                    continue
                dia = f"{r['abertura'][6:8]}/{r['abertura'][4:6]}/{r['abertura'][:4]}"
                if dia not in dias and t == 1:  # urna trocada entre turnos ou contingência: log próprio do 1º turno
                    dias.update(votos_por_dia(baixar_log(cli, ele[1], uf, r, a.guardar_brutos)))
                saida.append((t, r, dias.get(dia, [])))
            return chave, saida

        with ThreadPoolExecutor(a.threads) as ex, parcial.open("a") as arq:
            futuros = [ex.submit(tarefa, c) for c in chaves]
            for i, fut in enumerate(as_completed(futuros), 1):
                try:
                    chave, saida = fut.result()
                except tse.Bloqueado:
                    raise
                except (tse.NaoEncontrado, OSError, zipfile.BadZipFile, KeyError, ValueError) as e:
                    erros[type(e).__name__] += 1  # urna fica fora do parcial e é tentada de novo na próxima execução
                    continue
                reg = {"chave": list(chave), "resumos": [], "horas": []}
                for t, r, votos in saida:
                    res, hs = resumir(uf, chave, t, r, votos, hora_ref[(t, chave[0])])
                    reg["resumos"].append(res)
                    reg["horas"].extend(hs)
                    if a.votos:
                        votos_todos.extend({"uf": uf, "municipio": chave[0], "zona": int(chave[1]), "secao": int(chave[2]),
                                            "turno": t, **v} for v in votos)
                arq.write(json.dumps(reg, ensure_ascii=False) + "\n")
                arq.flush()
                resumos.extend(reg["resumos"]), horas.extend(reg["horas"])
                if i % 1000 == 0 or i == len(futuros):
                    print(f"[{uf}] {i}/{len(futuros)} ({i / (time.monotonic() - inicio):.1f} urnas/s) erros={dict(erros)}", flush=True)

    # esquema inferido de todas as linhas: colunas como `mesario` podem vir nulas nas primeiras centenas de votos
    pl.DataFrame(resumos, infer_schema_length=None).write_csv(pasta / "urnas.csv")
    pl.DataFrame(horas, infer_schema_length=None).write_parquet(pasta / "horas.parquet")
    if a.votos:
        pl.DataFrame(votos_todos, infer_schema_length=None).write_parquet(pasta / "votos.parquet")
    print("gravado", pasta, "| requisições:", cli.contagem, "| erros:", dict(erros), flush=True)


if __name__ == "__main__":
    main()
