from pathlib import Path

import pytest

from eleicoes import bu

FIXTURE = Path(__file__).parent / "fixtures" / "2t-ac-01074-0004-0001-bu.dat"


@pytest.fixture
def bruto() -> bytes:
    return FIXTURE.read_bytes()


def test_le_bu_real_do_2o_turno(bruto):
    b = bu.ler(bruto)
    assert (b.fase, b.pleito) == (bu.FASE_OFICIAL, 3221)
    assert (b.municipio, b.zona, b.local, b.secao) == (1074, 4, 1015, 1)
    assert (b.abertura, b.encerramento) == ("20261025T060001", "20261025T150152")
    assert b.numero_urna == 2260684

    pres = b.cargo(1)
    assert (pres.eleicao, pres.aptos, pres.comparecimento) == (6258, 262, 202)
    assert {(v.tipo, v.numero): v.qtd for v in pres.votaveis} == {(1, 13): 68, (1, 22): 127, (2, None): 3, (3, None): 4}
    assert b.cargo(3).eleicao == 6260  # governador também tem 2º turno no AC
    assert bu.conferir(b) == []


def test_recusa_bu_que_nao_e_oficial(bruto):
    # O ENUM de fase do envelope (0a 01 02) começa no byte 27; troca oficial(2) por simulado(1).
    assert bruto[27:30] == b"\x0a\x01\x02"
    simulado = bruto[:29] + b"\x01" + bruto[30:]
    with pytest.raises(bu.BoletimInvalido, match="não é oficial"):
        bu.ler(simulado)
    assert bu.ler(simulado, exigir_oficial=False).fase == 1


def test_recusa_bytes_que_nao_sao_der():
    with pytest.raises(bu.BoletimInvalido):
        bu.ler(b"\x30\x05\x02\x01")


def test_conferencia_acusa_soma_diferente_do_comparecimento(bruto):
    b = bu.ler(bruto)
    b.cargo(1).votaveis[0].qtd += 1
    assert any("soma 203 != comparecimento 202" in p for p in bu.conferir(b))


def test_senado_aceita_dois_votos_por_eleitor():
    c = bu.Cargo(6259, bu.CARGO_SENADOR, aptos=100, comparecimento=80, votaveis=[bu.Votavel(1, 160, 10, 101)])
    b = bu.Boletim(2, 3220, 1, 1, 1, 1, None, None, None, None, None, cargos=[c])
    assert bu.conferir(b) == []
