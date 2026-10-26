import polars as pl

from eleicoes import coleta, consolida
from eleicoes.reconcilia import reclassificar_nulos


def _reg(secao, votaveis, aptos=100, comparecimento=None, agregadas=()):
    comparecimento = sum(q for _, _, q in votaveis) if comparecimento is None else comparecimento
    return {
        "uf": "ac", "municipio": "01074", "zona": "0004", "secao": secao, "agregadas": list(agregadas),
        "status": "ok", "local": 1015, "problemas": [],
        "cargos": [{"eleicao": 6258, "cargo": 1, "aptos": aptos, "comparecimento": comparecimento,
                    "votaveis": [{"tipo": t, "qtd": q, "partido": n, "numero": n} for t, n, q in votaveis]}],
    }


def test_densifica_votavel_ausente_com_zero():
    regs = [
        _reg("0001", [(1, 13, 10), (1, 22, 20), (2, None, 1), (3, None, 2)]),
        _reg("0002", [(1, 22, 30)], agregadas=["0003"]),  # sem voto em 13, branco ou nulo
    ]
    urnas, votos = consolida.tabelas(regs, turno=2)
    s2 = dict(votos.filter(pl.col("nr_secao") == 2).select("nr_votavel", "qt_votos").iter_rows())
    assert s2 == {13: 0, 22: 30, 95: 0, 96: 0}
    assert votos.height == 2 * 4
    assert urnas.filter(pl.col("nr_secao") == 2)["n_secoes"].item() == 2
    assert urnas.filter(pl.col("nr_secao") == 1)["abstencao"].item() == 100 - 33


def test_urna_sem_bu_nao_entra_nos_votos():
    regs = [_reg("0001", [(1, 13, 5)]), {"uf": "ac", "municipio": "01074", "zona": "0004", "secao": "0009",
                                         "agregadas": [], "status": "sem_bu_totalizado"}]
    urnas, votos = consolida.tabelas(regs, turno=2)
    assert set(urnas["status"]) == {"ok", "sem_bu_totalizado"}
    assert set(votos["nr_secao"]) == {1}


def test_secao_agregada_nao_vira_urna():
    cs = {"abr": [{"mu": [{"cd": "01074", "zon": [{"cd": "0004", "sec": [
        {"ns": "0229", "nsa": ["0270"], "da": "25/10/2026", "ha": "21:26:42"},
        {"ns": "0270", "nsp": "0229"},
        {"ns": "0300"},
    ]}]}]}]}
    urnas = coleta.urnas_do_cs(cs)
    assert [(u["secao"], u["agregadas"], u["recebido"]) for u in urnas] == [
        ("0229", ["0270"], "25/10/2026 21:26:42"),
        ("0300", [], None),
    ]


def test_numero_sem_candidatura_oficial_vira_nulo():
    df = pl.DataFrame({"nr_votavel": [13, 22, 28, 95, 96]})
    out = df.select(reclassificar_nulos(pl.col("nr_votavel"), {13, 22}))["nr_votavel"].to_list()
    assert out == [13, 22, 96, 95, 96]
