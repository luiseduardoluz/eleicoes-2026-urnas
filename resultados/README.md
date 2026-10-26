# Resultados

Resumos gerados a partir de `data/` por `scripts/exportar_resultados.sh`, com dados coletados em 26/10/2026.
A explicação de cada número está em [docs/metodologia-tese-divergencias.md](../docs/metodologia-tese-divergencias.md).
Arquivos `.csv.gz` são CSV comprimidos (abrem direto no pandas, no polars e no R; no Excel, descompacte antes).

## `brasil/`

| Arquivo | Conteúdo |
| --- | --- |
| `conferencia_bu_x_oficial_2t.md` | Soma dos BUs × total oficial, zona a zona, 2º turno, Brasil e exterior |
| `conferencia_bu_x_oficial_1t.md` | O mesmo para o 1º turno, só nas UFs já coletadas (AC, BA e RR) |
| `decomposicao_ufs.csv` | Ganho de votos de cada finalista entre os turnos, por UF, e de onde veio (totais oficiais) |
| `decomposicao_brasil.csv` | Votos de cada candidato eliminado no 1º turno (total oficial do Brasil) |
| `fluxos_zonas.csv` | Estimativa de para onde foi cada grupo de eleitores do 1º turno, com intervalo de 90% (regressão ecológica por zona) |
| `resumo_urna_a_urna.csv` | Modelo 1º × 2º turno: urnas pareadas, sinalizadas e saldo de votos, por UF analisada |
| `urnas_sinalizadas.csv.gz` | Uma linha por urna sinalizada pelo modelo, com votos nos dois turnos, previsto, desvio e q-valor |

## `ac/`, `ba/`, `rr/`

| Arquivo | Conteúdo |
| --- | --- |
| `relatorio_<uf>.html` | Relatório interativo, com link para o BU oficial de cada urna sinalizada |
| `urnas_<uf>.csv.gz` | Uma linha por urna: votos nos dois turnos, previsto, desvio e sinalização |
| `sensibilidade_<uf>.csv` | Quantas fraudes simuladas o método detecta, por cenário e tamanho |
| `transferencias_<uf>.csv` | Coeficientes de transferência de votos do modelo |

## `logs_ba/`

| Arquivo | Conteúdo |
| --- | --- |
| `perfil_horas.csv` | Votos por hora na Bahia, por forma de habilitação do eleitor, nos dois turnos |
| `fim_do_dia.csv.gz` | Uma linha por urna e turno: votos sem biometria no dia e na última hora, teste de excesso e resíduos do modelo |

Não há aqui logs brutos nem registros voto a voto: o log da urna traz o título de eleitor dos mesários.
