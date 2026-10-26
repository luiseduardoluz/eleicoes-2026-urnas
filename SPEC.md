# Spec v3 — Desvios atípicos entre 1º e 2º turno (Presidente, Brasil 2026)

> Atualizado em 26/10/2026. Substitui a v2.
> **Escopo: só 2026.** Fonte: **API de divulgação do TSE** (`resultados.tse.jus.br`), que já
> publica o 2º turno totalizado e os Boletins de Urna (BU) de cada seção.
> Fase 0 implementada e validada em AC e RR (seção 9).

---

## 1. Objetivo

Comparar, **urna a urna**, o 1º turno (04/10/2026) com o 2º turno (25/10/2026) da eleição
presidencial, e produzir um **ranking de urnas cujo comportamento se desvia do esperado** dado o
comportamento de urnas comparáveis — com checagens de integridade que, essas sim, podem demonstrar
erro ou manipulação.

### 1.1 O que o sistema afirma e o que não afirma

| Produz | Não produz |
|---|---|
| Divergências exatas entre documentos oficiais (BU × totalização) | — (essas são fatos) |
| Resíduo de uma urna frente a um modelo explícito de transferência de votos | Veredito de fraude |
| Medida de surpresa calibrada (z, p, q-valor) | Afirmação de causa dolosa |
| Link para o BU oficial de cada urna sinalizada | Conclusão que dispense a conferência do BU, do log e da ata |

Vocabulário obrigatório na interface: **"desvio não explicado pelo modelo"** — nunca "fraude",
"suspeita" ou "irregularidade".

### 1.2 Sem nomes de candidatos no código

Candidatos são referenciados por `nr_votavel`; o nome vem dos dados na exibição. Na spec, os
finalistas são `CAND_A` e `CAND_B`.

---

## 2. Unidade de análise e definições

| Termo | Definição operacional |
|---|---|
| **Urna** | Unidade de análise. Uma seção principal + as seções agregadas a ela (`nsa` no `cs`). Os votos das agregadas estão no BU da principal. Chave: `(uf, cd_municipio, nr_zona, nr_secao_principal)`. |
| **Seção agregada** | Seção com `nsp` no `cs`: não tem urna nem BU. Nunca é pedida à API (daria 404). |
| **Local de votação** | `local` do BU, dentro de (município, zona). Base da comparação entre urnas irmãs (7.3). |
| **Aptos** | `aptos` do BU, por eleição. Denominador estável. Pode diferir entre cargos na mesma urna (eleitor em trânsito vota só para Presidente). |
| **Comparecimento** | `comparecimento` do BU, por cargo. Igual à soma dos votos do cargo (conferido em toda urna). |
| **Abstenção** | `aptos − comparecimento`. |
| **Branco / nulo** | `tipo` 2 e 3 no BU; codificados como `nr_votavel` 95 e 96. |
| **Número sem candidatura** | Votável presente no BU mas ausente do resultado oficial (ex.: registro cancelado após a carga da urna). **A totalização conta como nulo**; o pipeline reclassifica igual. 1º turno: candidato 28 (23 votos no AC, 14 em RR). |
| **Eliminados** | Candidatos do 1º turno ausentes no 2º. 11 no 1º turno de 2026 (13 candidatos no total). |
| **Resíduo** | Composição observada no 2º turno − composição prevista pelo modelo. Quantidade de interesse; **não** o swing bruto. |

Ordem de grandeza (1º turno, arquivo nacional do TSE): **499.206 seções com voto**, das quais 1.309
no exterior (`zz`). A API trata o exterior como mais uma UF.

---

## 3. Fonte de dados: API de divulgação do TSE

### 3.1 Árvore de caminhos (verificada)

Base: `https://resultados.tse.jus.br/oficial`. Com a assinatura ativa, o app oficial troca
`.json` por **`.jws`** — por isso os caminhos `.json` de anos anteriores davam 404.

```
comum/config/ele-c.jws                                       eleições e pleitos (descoberta)
ele2026/<eleicao>/dados/<uf>/<uf><mun5>-z<zona4>-c0001-e<eleicao6>-u.jws
                                                             total oficial por zona (reconciliação)
ele2026/arquivo-urna/<pleito>/config/<uf>/<uf>-p<pleito6>-cs.jws
                                                             todas as seções da UF + agregação
ele2026/arquivo-urna/<pleito>/dados/<uf>/<mun5>/<zona4>/<secao4>/
    p<pleito6>-<uf>-m<mun5>-z<zona4>-s<secao4>-aux.jws        hashes dos arquivos da urna
    <hash>/o<pleito5><uf><mun5><zona4><secao4>-bu.dat         Boletim de Urna (ASN.1 DER)
    <hash>/…-rdv.dat | …-log.jez | …-vota.vsc                 RDV, log e assinatura (fases futuras)
```

Códigos **descobertos em tempo de execução** no `ele-c` (nada fixo no código):

| | eleição | pleito |
|---|---|---|
| 1º turno — Presidente | 6257 | 3220 |
| 2º turno — Presidente | 6258 | 3221 |

### 3.2 Integridade na origem

- Todo `.jws` é verificado com **Ed25519**. A chave pública (`kid sNbt9Q_fLS65zE1_ZLNV-XRRwPY`) vem
  do app oficial e está em `config/eleicao_2026.toml`. Payload com assinatura inválida é recusado.
- O BU é ASN.1 DER. **O schema publicado pelo TSE (2022) não descreve o formato de 2026**: `Carga`,
  `ResultadoVotacaoPorEleicao` e `TotalVotosVotavel` ganharam campos. O leitor localiza cada
  estrutura pela forma (tipos e etiquetas estáveis) e **recusa** o que não encaixa, sem adivinhar.
- Todo BU passa pela conferência `soma dos votos do cargo == comparecimento`, e sua identificação
  interna (município/zona/seção/pleito) tem de bater com o caminho de onde veio.

### 3.3 Regras de consumo do servidor

Regras da apresentação técnica do TSE: **máx. 100 req/s por IP**, bloqueio de 10 min (renovável),
e **404 em excesso também bloqueia**. Implementação:

- limite de taxa dentro do cliente, compartilhado entre threads: **60 req/s**;
- nenhum caminho inventado: tudo deriva de `ele-c` → `cs` → `aux`;
- seções sem horário de recebimento no `cs` não são pedidas;
- HTTP 403 interrompe a coleta inteira (sinal de bloqueio).

### 3.4 Fontes secundárias (validação cruzada, opcional)

Portal de dados abertos: `votacao_secao_2026_BR.zip` e `bweb_1t_<UF>_*.zip` (1º turno já
publicados); 2º turno previsto para dias (BU) a semanas (CSV). Não são necessários para o pipeline.

---

## 4. Regras de dados (achados verificados)

1. **Votável sem voto não aparece no BU.** Densificar urna × votável com zero antes de qualquer fração.
2. **Unidade = urna**, com aptos das seções agregadas já somados no BU. ~5,7% das urnas do AC são agregações.
3. **Número sem candidatura → nulo** (seção 2), igual à totalização.
4. **Senado (1º turno) tem 2 votos por eleitor**: a conferência aceita soma = 2 × comparecimento só para o cargo 5.
5. **Aptos e comparecimento podem diferir entre cargos** na mesma urna (eleitor em trânsito). No 1º turno
   do AC, 48 de 2.270 urnas têm comparecimento de Presidente ≠ Governador. O teste entre cargos
   tem que descontar isso.
6. Só BU de **fase oficial** é aceito (simulado e treinamento têm a mesma estrutura).
7. **Status do `aux` pode ficar desatualizado.** Lauro de Freitas/BA, zona 180, 2º turno: as 413 seções
   aparecem como "Recebido" no `aux`, mas o resultado oficial dá a zona como 413/413 totalizadas. Regra:
   prefere-se o BU "Totalizado"; sem ele, aceita-se um BU único "Recebido" (registrado em `st_bu`), e a
   reconciliação por zona confirma a soma. `sem_bu_totalizado` não é status final: é pedido de novo.
8. **Eleitorado que muda entre turnos.** O voto em trânsito é pedido por turno, então algumas urnas têm
   aptos muito diferentes no 1º e no 2º turno (Camaçari/BA, zona 170, seção 262: 119 → 68). Com
   |Δaptos| > 10%, a urna sai do pareamento como `eleitorado_mudou` (4 urnas na BA).

---

## 5. Pipeline (Fase 0 — implementado)

```
src/eleicoes/
  der.py         leitor DER mínimo
  bu.py          interpretação do BU 2026 por forma + conferência
  tse.py         cliente HTTP (taxa, retentativas, JWS Ed25519) + descoberta da eleição
  coleta.py      cs → aux → bu.dat, resumível; totais oficiais por zona
  consolida.py   bronze → silver: urnas.parquet e votos.parquet densificado
  reconcilia.py  teste nº 1: soma dos BUs × total oficial por zona
config/eleicao_2026.toml   taxa, threads, UFs, chave JWS
tests/                     12 testes (fixture: BU e aux reais do 2º turno)
data/  (fora do git)
  raw/<t>t/<uf>/cs.json, bu/*.dat      bruto, para auditoria
  bronze/<t>t/<uf>.jsonl               1 linha por urna (status, metadados, votos)
  bronze/<t>t/<uf>.zonas.jsonl         totais oficiais por zona
  silver/<t>t/urnas.parquet, votos.parquet
  relatorios/fase0_<t>t.md
  manifest.jsonl                       eleição, UFs, contagem de requisições, duração
```

```bash
uv venv --python 3.13 --managed-python .venv && uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -m eleicoes coletar --turno 2 --uf ac      # omitir --uf = todas as UFs
.venv/bin/python -m eleicoes consolidar --turno 2
.venv/bin/python -m eleicoes reconciliar --turno 2
.venv/bin/python -m pytest
```

Status de cada urna: `ok`, `inconsistente` (BU lido, conferência falhou), `bu_invalido` (recusado
pelo leitor), `sem_bu_totalizado`, `sem_recebimento`, `erro` (refeito na próxima execução).

**Custo estimado para o Brasil** (medido no AC/RR, ~23 urnas/s): **~5–6 h por turno**, ~1 milhão
de requisições por turno, ~8 GB de BUs brutos nos dois turnos. Resumível a qualquer momento.

---

## 6. Normalização

Métrica primária: **fração sobre aptos**, com a composição completa somando 1:

```
1º turno: A, B, eliminados (agrupados), branco, nulo, abstenção
2º turno: A, B,                         branco, nulo, abstenção
```

O exemplo do briefing mostra por quê: `60/40/20/10 → 30/90/10` fecha tanto com "50% do eleitorado de A
migrou para B" quanto com "parte de A se absteve e novos eleitores vieram por B". Sem aptos e
abstenção, as duas hipóteses são indistinguíveis.

---

## 7. Baseline esperado

No 2º turno os votos dos eliminados se redistribuem: **swing grande é o normal**. O esperado vem de
um modelo, em três camadas.

### 7.1 Camada 1 — swing mediano local
`previsto = composição_1T + mediana(swing do grupo)`, com grupo em cascata
local → zona → município → UF. Baseline de sanidade.

### 7.2 Camada 2 — modelo composicional de transferência
Para cada componente `k ∈ {A, B, branco+nulo}` do 2º turno (abstenção é o complemento):

```
f_k,t2 = Σ_j β_kj · f_j,t1 + γ_k,município + ε
         j ∈ {A, B, eliminados, branco+nulo}      ← abstenção_t1 é a categoria de referência
```

- **Sem intercepto global com todas as categorias**: as frações somam 1, e o modelo da v2 era
  perfeitamente colinear. A abstenção do 1º turno fica como referência.
- Eliminados **agrupados** (11 candidatos, vários com votação residual).
- Estimador **robusto** (Huber), pesos = aptos, estimado **por UF**.
- Score da urna: **distância de Mahalanobis** do vetor de resíduos (A, B, branco+nulo), com a
  covariância robusta do estrato. O resíduo de cada componente é mantido para explicar *onde*
  está o desvio (troca de voto × mobilização).
- Os `β` são taxas médias de transferência e serão publicados como produto analítico.

### 7.3 Camada 3 — urnas irmãs no mesmo local
Para locais com ≥ 3 urnas: resíduo contra a mediana **das outras** urnas do local
(leave-one-out). Mesmo prédio, mesmo bairro: elimina quase todo confundimento por construção.

---

## 8. Medida de anomalia, calibração e múltiplas comparações

### 8.1 Variância com sobredispersão
A variância binomial pura (`p(1−p)/n`) supõe que a urna é amostra, e ela não é: a variação real
entre urnas é muito maior. Modelo único:

```
Var(r_i) = τ²_estrato + φ_estrato · p̂(1 − p̂) / n_i
```

`τ²` e `φ` estimados de forma robusta por estrato (UF × faixa de tamanho). `z = r / sqrt(Var)`.
O `min(|z_robusto|, |z_binomial|)` da v2 não segue N(0,1) e foi abandonado.

### 8.2 FDR
~499 mil urnas: sem correção, ~25 mil seriam sinalizadas por azar a 5%. **Benjamini-Hochberg**,
reportando q-valor e, ao lado, o número de sinalizações esperado sob a hipótese nula.

### 8.3 Calibração sem eleição anterior
Sem 2022, não há taxa de base histórica. A calibração vem de dentro de 2026:

1. **Centro da distribuição de z ≈ N(0,1)** (QQ-plot por estrato). Centro fora disso = modelo mal
   especificado, não anomalia.
2. **Injeção sintética** (curva de poder): perturbar urnas reais com cenários conhecidos — troca A→B,
   enchimento (comparecimento → ~100%), supressão, anulação — e medir detecção. Resultado vira frase
   na interface: *"detecta trocas a partir de ~X p.p. em urnas de ~Y eleitores, FDR 5%"*.
3. **Congelamento antes da rodada final:** modelo, limiares e FDR são ajustados num **conjunto de
   desenvolvimento** de UFs (AC, RR, AP, TO, SE) e no sintético; fixados com uma tag git; só então
   aplicados, sem alteração, a todas as UFs.

Limitação declarada no produto: **sem taxa de base histórica, a proporção de urnas sinalizadas em
2026 não pode ser comparada à de eleições anteriores.**

---

## 9. Bateria de testes

### Nível 1 — Integridade (exato, não estatístico)

| # | Teste | Situação |
|---|---|---|
| 1 | Soma dos BUs × total oficial assinado, por zona e métrica | ✅ **implementado** — AC e RR, 2 turnos: 39 zonas, **0 divergência** |
| 2 | Assinatura dos arquivos (JWS Ed25519) | ✅ `cs`, `aux`, `ele-c` e totais por zona |
| 2b | Assinatura do próprio BU (`vota.vsc`) | ⏳ pendente |
| 3 | RDV × BU (soma dos votos individuais) | ⏳ pendente — `rdv.dat` já disponível por urna |
| 4 | Comparecimento entre cargos na mesma urna | ⏳ pendente — descontar trânsito (seção 4.5) |
| 5 | Aritmética (soma = comparecimento ≤ aptos) e identidade do BU | ✅ em toda urna, na coleta |

### Nível 2 — Forense de urna (por urna, sinal forte)

| # | Teste | Fonte |
|---|---|---|
| 6 | Votos em rajada (intervalos curtos demais) | `log.jez` |
| 7 | Habilitação sem biometria anômala vs. irmãs e vs. 1º turno | BU (campo novo de 2026, a mapear) / log |
| 8 | Votos fora do horário (abertura/encerramento) | BU ✅ já extraído + log |
| 9 | Contingência / troca de urna entre turnos | BU (`tipo_urna`, `numero_urna` ✅ extraídos) |

Logs só nas urnas sinalizadas e nas irmãs delas, não no país inteiro.

### Nível 3 — Estatístico (indício, nunca prova)

| # | Teste |
|---|---|
| 10 | Resíduo composicional (Camadas 2 e 3) com FDR |
| 11 | Impressão digital comparecimento × votação (Klimek et al., PNAS 2012) |
| 12 | Mobilização seletiva: correlação entre resíduo de abstenção e de voto |
| 13 | Concentração espacial das urnas anômalas (Moran local) |
| 14 | Quase unanimidade (> 95%) frente às irmãs |
| 15 | Coincidência de sinais dos níveis 2 e 3 na mesma urna |

Não usar Benford, último dígito nem percentuais inteiros: detectam atas preenchidas à mão, o que não
existe na urna eletrônica.

---

## 10. Flags

Limiares numéricos em `config/`, decididos na etapa de congelamento (8.3), nunca no código.

| Flag | Critério |
|---|---|
| `DESVIO_COMPOSICIONAL` | q < limiar no score de Mahalanobis (Camada 2) |
| `DIVERGENTE_NO_LOCAL` | q < limiar frente às irmãs (Camada 3) |
| `NULOS_ANOMALOS` / `ABSTENCAO_ANOMALA` | resíduo do componente acima do limiar |
| `INTEGRIDADE` | qualquer falha do Nível 1 — **sempre** listada, sem limiar estatístico |

`INVERSAO` (vencedor da urna troca de lado) é **atributo descritivo**, não flag: num 2º turno
disputado, dezenas de milhares de urnas trocam de lado legitimamente.

---

## 11. Critérios de aceite

Fase 0:
- [x] BU × total oficial por zona com diferença 0 (AC, RR — 2 turnos)
- [x] 100% das urnas com BU em `ok` (AC, RR)
- [x] Assinaturas JWS verificadas; payload adulterado recusado (teste)
- [x] BU não oficial recusado; DER inválido recusado (teste)
- [x] Densificação e exclusão de seções agregadas (teste)
- [ ] Coleta completa do Brasil nos dois turnos, com relatório de cobertura
- [ ] Contagem de urnas ≈ seções com voto do arquivo nacional (499.206 no 1º turno)

Fase 1:
- [x] Fixture: municípios sintéticos com matriz de transferência conhecida + o caso `60/40/20/10 → 30/90/10`
      injetado → sinalizado (q < 10⁻⁶), previsto de A ≈ 67/160 como pela matriz (`tests/test_analise.py`)
- [x] Urnas sintéticas normais sinalizadas abaixo do nível nominal; z com mediana ≈ 0 e escala ≈ 1
- [x] Modelo recupera a matriz de transferência conhecida
- [ ] Centro de `z` aprovado no QQ-plot em todos os estratos do conjunto de desenvolvimento
- [x] Curva de poder no relatório por UF (injeção em 2% das urnas, 4 cenários × 4 intensidades)
- [ ] Tag de congelamento criada antes da rodada final

---

## 12. Fases

| Fase | Entrega |
|---|---|
| **0** ✅ parcial | Coleta, leitura, consolidação, teste nº 1. Falta: rodar o Brasil. |
| **1** ✅ parcial | Implementado em `analise.py` / `fase1.py` / `relatorio.py` (`python -m eleicoes analisar --uf ba`): pareamento, modelo composicional com efeito fixo de município, variância com sobredispersão e nulo empírico, urnas irmãs (leave-one-out), BH, injeção sintética, relatório HTML + CSV. Falta: **congelar** num conjunto de desenvolvimento |
| **2** | Rodada final em todas as UFs; testes 2b, 3, 4 e nível 2 nas urnas sinalizadas |
| **3** | Painel: scatter 1T × 2T com banda do modelo, mapa (lat/long dos locais), tabela drill-down, ficha da urna com link para o BU |

---

## 13. Decisões tomadas

| Decisão | Escolha |
|---|---|
| Período | **Só 2026** (sem 2022 como placebo; limitação declarada em 8.3) |
| Fonte | **API de divulgação** para os dois turnos (mesmo formato e mesmo leitor) |
| Escopo | Brasil inteiro + exterior; só Presidente (o BU já traz Governador para extensão futura) |
| Ambiente | Python 3.13 gerenciado pelo `uv` (o Python do Homebrew desta máquina está quebrado: `pyexpat` incompatível com o `libexpat` do macOS 26.2) |
