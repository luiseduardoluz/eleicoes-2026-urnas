"""Cliente da API de divulgação do TSE (resultados.tse.jus.br).

Regras de consumo (apresentação técnica do TSE): máx. 100 req/s por IP, bloqueio de 10 min
renovável, e 404 em excesso também pode bloquear. Por isso: limite de taxa dentro do cliente,
compartilhado entre threads, e nenhum caminho montado sem vir de um arquivo de configuração.
"""

from __future__ import annotations

import base64
import http.client
import json
import ssl
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

USER_AGENT = "eleicoes-2026-analise/0.1 (pesquisa; dados publicos do TSE)"


class NaoEncontrado(Exception):
    pass


class Bloqueado(Exception):
    pass


class AssinaturaInvalida(Exception):
    pass


def _b64url(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class VerificadorJws:
    def __init__(self, kid: str, x: str):
        self.kid = kid
        self.chave = Ed25519PublicKey.from_public_bytes(_b64url(x))

    def payload(self, token: str) -> dict:
        try:
            cab_b64, carga_b64, assin_b64 = token.strip().split(".")
        except ValueError as e:
            raise AssinaturaInvalida("JWS não tem 3 partes") from e
        cab = json.loads(_b64url(cab_b64))
        if cab.get("alg") != "EdDSA" or cab.get("kid") != self.kid:
            raise AssinaturaInvalida(f"cabeçalho inesperado: {cab}")
        try:
            self.chave.verify(_b64url(assin_b64), f"{cab_b64}.{carga_b64}".encode())
        except InvalidSignature as e:
            raise AssinaturaInvalida("assinatura Ed25519 não confere") from e
        return json.loads(_b64url(carga_b64))


class LimiteTaxa:
    """Espaça o início das requisições em 1/taxa segundos, entre todas as threads."""

    def __init__(self, taxa_req_s: float):
        self.intervalo = 1.0 / taxa_req_s
        self.proximo = time.monotonic()
        self.trava = threading.Lock()

    def aguardar(self) -> None:
        with self.trava:
            agora = time.monotonic()
            espera = self.proximo - agora
            self.proximo = max(agora, self.proximo) + self.intervalo
        if espera > 0:
            time.sleep(espera)


class Cliente:
    def __init__(self, base_url: str, verificador: VerificadorJws, taxa_req_s: float = 60, timeout_s: float = 30):
        self.base = base_url.rstrip("/")
        self.verificador = verificador
        self.limite = LimiteTaxa(taxa_req_s)
        self.timeout = timeout_s
        self.contagem = {"requisicoes": 0, "404": 0, "retentativas": 0}
        self._trava = threading.Lock()

    def url(self, *partes: str) -> str:
        return "/".join([self.base, *partes])

    def _contar(self, chave: str) -> None:
        with self._trava:
            self.contagem[chave] += 1

    def get(self, *partes: str, tentativas: int = 5) -> bytes:
        url = self.url(*partes)
        for n in range(tentativas):
            self.limite.aguardar()
            self._contar("requisicoes")
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return r.read()
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    self._contar("404")
                    raise NaoEncontrado(url) from e
                if e.code == 403:
                    raise Bloqueado(f"HTTP 403 em {url} — possível bloqueio por taxa; pare e aguarde 10 min") from e
                if e.code not in (429, 500, 502, 503, 504):
                    raise
            # SSLError e IncompleteRead aparecem no meio da leitura da resposta: falha transitória, tenta de novo
            except (urllib.error.URLError, TimeoutError, ConnectionError, ssl.SSLError, http.client.HTTPException):
                pass
            self._contar("retentativas")
            time.sleep(min(30, 2**n))
        raise ConnectionError(f"falhou após {tentativas} tentativas: {url}")

    def jws(self, *partes: str) -> dict:
        """Baixa um .jws e devolve o payload já com a assinatura verificada."""
        return self.verificador.payload(self.get(*partes).decode("ascii"))


@dataclass(frozen=True)
class Eleicao:
    ano: int
    turno: int
    ciclo: str
    codigo: int
    pleito: int
    nome: str

    @property
    def e6(self) -> str:
        return f"e{self.codigo:06d}"

    @property
    def p6(self) -> str:
        return f"p{self.pleito:06d}"


def descobrir_eleicao(ele_c: dict, ano: int, turno: int, cargo: int = 1) -> Eleicao:
    """Acha a eleição federal de `ano`/`turno` com o cargo pedido no arquivo ele-c (nada fixo no código)."""
    ciclo = f"ele{ano}"
    achadas = [
        Eleicao(ano, turno, ciclo, int(e["cd"]), int(p["cd"]), e["nm"])
        for p in ele_c["pl"]
        if p.get("c") == ciclo
        for e in p["e"]
        if e.get("t") == str(turno)
        and any(cp.get("cd") == str(cargo) for a in e.get("abr", []) for cp in a.get("cp", []))
    ]
    if len(achadas) != 1:
        raise LookupError(f"esperava 1 eleição {ciclo} turno {turno} cargo {cargo}, achei {achadas}")
    return achadas[0]
