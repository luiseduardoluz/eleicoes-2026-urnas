# Eleições 2026 — Boletins de Urna (Presidente)

Código e metodologia para testar, urna a urna e com dados públicos do TSE, a tese de que houve
divergências no 2º turno da eleição presidencial de 2026: entre o que as urnas registraram e o que foi
divulgado, ou um ganho de votos que os números não explicam.

**Leia primeiro: [docs/metodologia-tese-divergencias.md](docs/metodologia-tese-divergencias.md)**, que traz
os resultados, o método, como interpretar e as limitações. Como o projeto foi construído com IA, e como você
pode explorar os dados com IA: [docs/como-foi-feito-com-ia.md](docs/como-foi-feito-com-ia.md).

## Resultados até agora (26/10/2026)

- **Os boletins batem com o resultado oficial.** A soma dos 497.897 Boletins de Urna (BUs) do 2º turno
  confere com o total oficial em todas as 6.106 zonas eleitorais do Brasil, métrica por métrica. No exterior,
  70 seções não têm BU publicado no portal do TSE (831 votos).
- **O ganho de votos fecha com a conta oficial.** Lula ganhou 10,38 milhões de votos do 1º para o 2º turno e
  Flávio Bolsonaro, 3,72 milhões; os 14,1 milhões somados vêm dos eleitores dos 10 eliminados, da queda de
  brancos e nulos e do aumento do comparecimento.
- **Urna a urna, sem padrão a favor de um candidato.** Na Bahia, 0,2% das urnas têm desvio estatístico em
  relação ao 1º turno, sem direção; os logs das urnas não mostram votos sem biometria concentrados no fim
  do dia.

Os resultados são preliminares: a coleta dos BUs do 1º turno do país está em andamento, e a comparação
1º × 2º turno urna a urna está concluída em Bahia, Acre e Roraima.

### O que este trabalho afirma e o que não afirma

A conferência BU × total oficial é uma prova: qualquer diferença seria um fato. Já uma urna sinalizada pelo
modelo estatístico tem um **desvio não explicado pelo modelo** e é um ponto para conferência (BU, log e ata da
seção), não evidência de fraude.

## Estrutura

| Caminho | Conteúdo |
| --- | --- |
| `docs/` | Metodologia e resultados, em texto para publicação; como o projeto foi feito com IA |
| `SPEC.md` | Especificação técnica: unidade de análise, modelo, testes e critérios |
| `src/eleicoes/` | Pacote: cliente da API do TSE com verificação de assinatura, leitura do BU (ASN.1), coleta, consolidação, conferência e modelo |
| `scripts/` | Análises complementares: logs das urnas, fluxos de votos, checagens do 2º turno, curiosidades, exportação dos resultados |
| `resultados/` | Resumos prontos (CSV, relatórios HTML), gerados por `scripts/exportar_resultados.sh` |
| `config/eleicao_2026.toml` | Parâmetros da coleta e chave pública do TSE |
| `tests/` | Testes automatizados, com um BU e um arquivo assinado reais como amostra |

Os dados baixados ficam em `data/`, fora do repositório (cerca de 2 GB). Tudo pode ser refeito com os
comandos abaixo.

## Como reproduzir

Requer Python 3.13 ou mais recente.

```bash
uv venv && uv pip install -e '.[dev]'     # ou: python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest                # testes
```

Pipeline principal (`--uf` é repetível; sem ele, vale para todas as UFs e o exterior):

```bash
python -m eleicoes coletar     --turno 2 --uf ba --sem-raw   # BUs e totais oficiais por zona
python -m eleicoes consolidar  --turno 2                     # tabelas por urna e por votável
python -m eleicoes reconciliar --turno 2                     # soma dos BUs × total oficial, zona a zona
python -m eleicoes analisar    --uf ba                       # modelo 1º × 2º turno (exige os dois turnos)
```

Análises complementares:

```bash
python scripts/logs_urnas.py --rotulo ba ba                  # log de cada urna: habilitação e hora de cada voto
python scripts/analise_logs.py ba ba                         # votos sem biometria no fim do dia
python scripts/fluxos_brasil.py 60                           # decomposição oficial e fluxos de votos (60 reamostras)
python scripts/analise_parcial_2t.py ac al                   # checagens só com o 2º turno
python scripts/curiosidades_2t.py                            # fatos curiosos do 2º turno
scripts/exportar_resultados.sh                               # copia os resumos para resultados/
```

### Respeite o limite do TSE

A API de divulgação aceita **no máximo 100 requisições por segundo por IP** e bloqueia o IP por 10 minutos
quando o limite é excedido. A coleta usa 60 por segundo por padrão (`taxa_req_s` na config), e os scripts de
logs usam 20. Não rode duas coletas ao mesmo tempo acima desse total. A coleta nacional dos dois turnos leva
cerca de 11 horas; com `--sem-raw`, guarda de cada BU o resultado lido, o hash e o endereço, em vez do
arquivo bruto.

## Fonte e verificação dos dados

Todos os dados vêm da API pública de divulgação do TSE ([resultados.tse.jus.br](https://resultados.tse.jus.br)).
Os arquivos de configuração e de resultado vêm assinados (JWS, Ed25519); a chave pública, embutida no
aplicativo oficial de resultados, está em `config/eleicao_2026.toml`, e todo arquivo é verificado antes de ser
usado. Os códigos de eleição e de pleito não ficam no código: são descobertos a cada execução no arquivo de
configuração do próprio TSE.

Os logs das urnas trazem o título de eleitor dos mesários. Por isso nenhum log bruto nem registro voto a voto
é publicado em `resultados/`: só contagens por urna e por hora.

## Licença

- Código (`src/`, `scripts/`, `tests/`): [MIT](LICENSE).
- Documentos e resultados (`docs/`, `SPEC.md`, `resultados/`): [CC BY 4.0](LICENSE-CC-BY-4.0.md), com
  atribuição.
- Dados de origem: públicos, do Tribunal Superior Eleitoral.
