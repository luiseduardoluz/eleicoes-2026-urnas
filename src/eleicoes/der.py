"""Leitor mínimo de DER (ASN.1). Devolve a árvore crua; a interpretação fica em bu.py."""

from __future__ import annotations

from dataclasses import dataclass, field

UNIVERSAL, APLICACAO, CONTEXTO, PRIVADA = range(4)
INTEGER, OCTET_STRING, ENUMERATED, SEQUENCE, GENERAL_STRING = 2, 4, 10, 16, 27


class DerInvalido(ValueError):
    pass


@dataclass
class No:
    classe: int
    construido: bool
    tag: int
    valor: bytes = b""
    filhos: list[No] = field(default_factory=list)

    def eh(self, classe: int, tag: int, construido: bool | None = None) -> bool:
        return self.classe == classe and self.tag == tag and (
            construido is None or self.construido == construido
        )

    @property
    def inteiro(self) -> int:
        if self.construido or not self.valor:
            raise DerInvalido(f"nó [{self.classe}:{self.tag}] não é inteiro primitivo")
        return int.from_bytes(self.valor, "big", signed=True)

    @property
    def texto(self) -> str:
        return self.valor.decode("latin-1")


def ler(dados: bytes) -> No:
    nos, fim = _ler_sequencia(dados, 0, len(dados))
    if len(nos) != 1 or fim != len(dados):
        raise DerInvalido("esperava exatamente um nó raiz ocupando o arquivo todo")
    return nos[0]


def _ler_sequencia(dados: bytes, i: int, fim: int) -> tuple[list[No], int]:
    nos = []
    while i < fim:
        no, i = _ler_no(dados, i, fim)
        nos.append(no)
    if i != fim:
        raise DerInvalido("conteúdo ultrapassa o tamanho declarado")
    return nos, i


def _ler_no(dados: bytes, i: int, fim: int) -> tuple[No, int]:
    if i + 2 > fim:
        raise DerInvalido("nó truncado")
    t = dados[i]
    i += 1
    classe, construido, tag = t >> 6, bool(t & 0x20), t & 0x1F
    if tag == 0x1F:
        tag = 0
        while True:
            if i >= fim:
                raise DerInvalido("tag longa truncada")
            b = dados[i]
            i += 1
            tag = (tag << 7) | (b & 0x7F)
            if not b & 0x80:
                break
    tam = dados[i]
    i += 1
    if tam & 0x80:
        n = tam & 0x7F
        if n == 0 or n > 4:
            raise DerInvalido("tamanho indefinido ou grande demais (não é DER)")
        tam = int.from_bytes(dados[i : i + n], "big")
        i += n
    if i + tam > fim:
        raise DerInvalido("nó ultrapassa o fim do pai")
    if construido:
        filhos, _ = _ler_sequencia(dados, i, i + tam)
        return No(classe, True, tag, filhos=filhos), i + tam
    return No(classe, False, tag, valor=dados[i : i + tam]), i + tam
