"""Interpretação do Boletim de Urna (BU) de 2026.

O schema ASN.1 publicado pelo TSE é de 2022 e não descreve o formato de 2026 (há campos novos
em Carga, em ResultadoVotacaoPorEleicao e em TotalVotosVotavel). Por isso cada estrutura é
localizada pela sua *forma* — tipos e etiquetas que não mudaram entre versões — e não pela
posição. Quando nada tem a forma esperada, o BU é recusado (BoletimInvalido), nunca adivinhado.
A conferência `soma dos votos == comparecimento` valida a leitura de cada urna.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import der
from .der import CONTEXTO, ENUMERATED, GENERAL_STRING, INTEGER, OCTET_STRING, SEQUENCE, UNIVERSAL, No

FASE_OFICIAL = 2
TIPOS_VOTO = {1: "nominal", 2: "branco", 3: "nulo", 4: "legenda", 5: "cargo_sem_candidato"}
CARGO_SENADOR = 5


class BoletimInvalido(ValueError):
    pass


@dataclass
class Votavel:
    tipo: int
    qtd: int
    partido: int | None = None
    numero: int | None = None


@dataclass
class Cargo:
    eleicao: int
    cargo: int
    aptos: int
    comparecimento: int
    votaveis: list[Votavel]

    @property
    def soma(self) -> int:
        return sum(v.qtd for v in self.votaveis)


@dataclass
class Boletim:
    fase: int
    pleito: int | None
    municipio: int
    zona: int
    local: int
    secao: int
    emissao: str | None
    abertura: str | None
    encerramento: str | None
    numero_urna: int | None
    tipo_urna: int | None
    cargos: list[Cargo] = field(default_factory=list)

    def cargo(self, codigo: int) -> Cargo | None:
        return next((c for c in self.cargos if c.cargo == codigo), None)


def _seq(no: No) -> bool:
    return no.eh(UNIVERSAL, SEQUENCE, True)


def _int(no: No) -> bool:
    return no.eh(UNIVERSAL, INTEGER, False)


def _identificacao_secao(no: No) -> tuple[int, int, int, int] | None:
    """Forma de IdentificacaoSecaoEleitoral: {{município, zona}, local, seção}."""
    f = no.filhos
    if (
        no.construido
        and len(f) == 3
        and len(f[0].filhos) == 2
        and all(_int(x) for x in f[0].filhos)
        and _int(f[1])
        and _int(f[2])
    ):
        return f[0].filhos[0].inteiro, f[0].filhos[1].inteiro, f[1].inteiro, f[2].inteiro
    return None


def _votavel(no: No) -> Votavel | None:
    """Forma de TotalVotosVotavel: [1] tipo, [2] quantidade, [3] {partido, número} opcional."""
    if not _seq(no):
        return None
    por_tag = {c.tag: c for c in no.filhos if c.classe == CONTEXTO}
    if 1 not in por_tag or 2 not in por_tag or por_tag[1].construido or por_tag[2].construido:
        return None
    v = Votavel(tipo=por_tag[1].inteiro, qtd=por_tag[2].inteiro)
    ident = por_tag.get(3)
    if ident is not None:
        if not (ident.construido and len(ident.filhos) == 2 and all(_int(x) for x in ident.filhos)):
            return None
        v.partido, v.numero = ident.filhos[0].inteiro, ident.filhos[1].inteiro
    return v


def _total_votos_cargo(no: No) -> tuple[int, list[Votavel]] | None:
    """Forma de TotalVotosCargo: codigoCargo ([1] constitucional | [2] livre) + SEQUENCE OF votáveis."""
    if not _seq(no) or not no.filhos:
        return None
    cod = no.filhos[0]
    if cod.classe != CONTEXTO or cod.construido or cod.tag not in (1, 2):
        return None
    for c in no.filhos[1:]:
        if _seq(c) and c.filhos:
            votaveis = [_votavel(x) for x in c.filhos]
            if all(v is not None for v in votaveis):
                return cod.inteiro, votaveis
    return None


def _resultado_votacao(no: No) -> tuple[int, list[tuple[int, list[Votavel]]]] | None:
    """Forma de ResultadoVotacao: tipoCargo (ENUM), comparecimento (INT), SEQUENCE OF TotalVotosCargo."""
    f = no.filhos
    if not (_seq(no) and len(f) >= 3 and f[0].eh(UNIVERSAL, ENUMERATED, False) and _int(f[1])):
        return None
    for c in f[2:]:
        if _seq(c) and c.filhos:
            totais = [_total_votos_cargo(x) for x in c.filhos]
            if all(t is not None for t in totais):
                return f[1].inteiro, totais
    return None


def _resultado_por_eleicao(no: No) -> list[Cargo] | None:
    """Forma de ResultadoVotacaoPorEleicao: idEleicao, aptos, ..., SEQUENCE OF ResultadoVotacao."""
    f = no.filhos
    if not (_seq(no) and len(f) >= 3 and _int(f[0]) and _int(f[1])):
        return None
    eleicao, aptos = f[0].inteiro, f[1].inteiro
    for c in f[2:]:
        if _seq(c) and c.filhos:
            resultados = [_resultado_votacao(x) for x in c.filhos]
            if all(r is not None for r in resultados):
                return [
                    Cargo(eleicao, cargo, aptos, comparecimento, votaveis)
                    for comparecimento, totais in resultados
                    for cargo, votaveis in totais
                ]
    return None


def _envelope(raiz: No) -> tuple[int, int | None, bytes]:
    if not _seq(raiz):
        raise BoletimInvalido("envelope: raiz não é SEQUENCE")
    fase = next((c.inteiro for c in raiz.filhos if c.eh(UNIVERSAL, ENUMERATED, False)), None)
    if fase is None:
        raise BoletimInvalido("envelope: sem campo de fase")
    pleito = None
    cab = raiz.filhos[0]
    if _seq(cab) and len(cab.filhos) >= 2 and cab.filhos[1].classe == CONTEXTO and cab.filhos[1].tag == 2:
        pleito = cab.filhos[1].inteiro
    octets = [c for c in raiz.filhos if c.eh(UNIVERSAL, OCTET_STRING, False)]
    if not octets:
        raise BoletimInvalido("envelope: sem conteúdo")
    return fase, pleito, octets[-1].valor


def _numero_urna(urna: No) -> int | None:
    """Urna → correspondenciaResultado → carga → numeroInternoUrna (primeiro INT da carga)."""
    for corr in urna.filhos:
        if _seq(corr):
            for carga in corr.filhos:
                if _seq(carga) and carga.filhos and _int(carga.filhos[0]):
                    return carga.filhos[0].inteiro
    return None


def ler(dados: bytes, exigir_oficial: bool = True) -> Boletim:
    try:
        fase, pleito, conteudo = _envelope(der.ler(dados))
        raiz = der.ler(conteudo)
    except der.DerInvalido as e:
        raise BoletimInvalido(f"DER inválido: {e}") from e
    if exigir_oficial and fase != FASE_OFICIAL:
        raise BoletimInvalido(f"fase {fase} não é oficial")
    if not _seq(raiz):
        raise BoletimInvalido("boletim: raiz não é SEQUENCE")

    ident = next((x for x in map(_identificacao_secao, raiz.filhos) if x), None)
    if ident is None:
        raise BoletimInvalido("boletim: identificação da seção não encontrada")
    municipio, zona, local, secao = ident

    urna = next(
        (c for c in raiz.filhos if _seq(c) and c.filhos and c.filhos[0].eh(UNIVERSAL, ENUMERATED, False)),
        None,
    )
    textos = [c.texto for c in raiz.filhos if c.eh(UNIVERSAL, GENERAL_STRING, False)]
    dados_secao = next(
        (c for c in raiz.filhos if c.classe == CONTEXTO and c.tag == 0 and c.construido), None
    )
    horarios = [c.texto for c in dados_secao.filhos if c.eh(UNIVERSAL, GENERAL_STRING, False)] if dados_secao else []

    cargos: list[Cargo] = []
    for c in raiz.filhos:
        if _seq(c) and c.filhos:
            por_eleicao = [_resultado_por_eleicao(x) for x in c.filhos]
            if all(p is not None for p in por_eleicao):
                cargos = [cargo for p in por_eleicao for cargo in p]
                break
    if not cargos:
        raise BoletimInvalido("boletim: resultados por eleição não encontrados")

    return Boletim(
        fase=fase,
        pleito=pleito,
        municipio=municipio,
        zona=zona,
        local=local,
        secao=secao,
        emissao=textos[0] if textos else None,
        abertura=horarios[0] if len(horarios) > 0 else None,
        encerramento=horarios[1] if len(horarios) > 1 else None,
        numero_urna=_numero_urna(urna) if urna else None,
        tipo_urna=urna.filhos[0].inteiro if urna else None,
        cargos=cargos,
    )


def conferir(b: Boletim) -> list[str]:
    """Regras que não podem falhar numa leitura correta. Lista vazia = BU consistente."""
    problemas = []
    for c in b.cargos:
        for v in c.votaveis:
            if v.tipo not in TIPOS_VOTO:
                problemas.append(f"eleição {c.eleicao} cargo {c.cargo}: tipo de voto desconhecido {v.tipo}")
            if v.qtd < 0:
                problemas.append(f"eleição {c.eleicao} cargo {c.cargo}: quantidade negativa")
        votos_por_eleitor = 2 if c.cargo == CARGO_SENADOR and c.soma == 2 * c.comparecimento else 1
        if c.soma != votos_por_eleitor * c.comparecimento:
            problemas.append(
                f"eleição {c.eleicao} cargo {c.cargo}: soma {c.soma} != comparecimento {c.comparecimento}"
            )
        if c.comparecimento > c.aptos:
            problemas.append(f"eleição {c.eleicao} cargo {c.cargo}: comparecimento {c.comparecimento} > aptos {c.aptos}")
    return problemas
