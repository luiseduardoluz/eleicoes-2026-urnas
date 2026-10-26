import base64
import json
import tomllib
from pathlib import Path

import pytest

from eleicoes import tse

RAIZ = Path(__file__).parents[1]
CFG = tomllib.loads((RAIZ / "config" / "eleicao_2026.toml").read_text())
AUX = (Path(__file__).parent / "fixtures" / "2t-ac-01074-0004-0001-aux.jws").read_text()


@pytest.fixture
def verificador() -> tse.VerificadorJws:
    return tse.VerificadorJws(CFG["jws"]["kid"], CFG["jws"]["x"])


def test_verifica_assinatura_de_arquivo_real(verificador):
    p = verificador.payload(AUX)
    assert p["st"] == "Totalizada"
    assert p["hashes"][0]["st"] == "Totalizado"


def test_recusa_payload_adulterado(verificador):
    cab, carga, assin = AUX.strip().split(".")
    dados = json.loads(base64.urlsafe_b64decode(carga + "=" * (-len(carga) % 4)))
    dados["st"] = "Adulterada"
    nova = base64.urlsafe_b64encode(json.dumps(dados).encode()).decode().rstrip("=")
    with pytest.raises(tse.AssinaturaInvalida):
        verificador.payload(f"{cab}.{nova}.{assin}")


def test_descobre_eleicao_sem_codigo_fixo():
    ele_c = {"pl": [
        {"cd": "3220", "c": "ele2026", "e": [
            {"cd": "6257", "t": "1", "nm": "Federal 1T", "abr": [{"cd": "br", "cp": [{"cd": "1"}]}]},
            {"cd": "6259", "t": "1", "nm": "Estadual 1T", "abr": [{"cd": "br", "cp": [{"cd": "3"}]}]},
        ]},
        {"cd": "3221", "c": "ele2026", "e": [
            {"cd": "6258", "t": "2", "nm": "Federal 2T", "abr": [{"cd": "br", "cp": [{"cd": "1"}]}]},
        ]},
        {"cd": "3228", "c": "ele2024", "e": [
            {"cd": "6268", "t": "1", "nm": "Suplementar", "abr": [{"cd": "rs", "cp": [{"cd": "11"}]}]},
        ]},
    ]}
    e2 = tse.descobrir_eleicao(ele_c, 2026, 2)
    assert (e2.codigo, e2.pleito, e2.e6, e2.p6) == (6258, 3221, "e006258", "p003221")
    assert tse.descobrir_eleicao(ele_c, 2026, 1).codigo == 6257
    with pytest.raises(LookupError):
        tse.descobrir_eleicao(ele_c, 2022, 1)


def test_tenta_de_novo_apos_erro_ssl_na_leitura(monkeypatch):
    class Resposta:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"ok"

    chamadas = []

    def urlopen(req, timeout):
        chamadas.append(req.full_url)
        if len(chamadas) == 1:
            raise tse.ssl.SSLError("[SSL: RECORD_LAYER_FAILURE] record layer failure")
        return Resposta()

    monkeypatch.setattr(tse.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(tse.time, "sleep", lambda s: None)
    cli = tse.Cliente("https://exemplo", None, 1000, 5)
    assert cli.get("a", "b") == b"ok"
    assert len(chamadas) == 2 and cli.contagem["retentativas"] == 1
