# Metodologia — a tese das divergências no 2º turno (Presidente 2026, Brasil)

26/10/2026 · versão preliminar

## Resumo

A tese de que houve divergências no 2º turno da eleição presidencial não se confirmou em nenhum dos testes feitos até agora.

- **Os boletins batem com o resultado oficial no Brasil inteiro.** Somamos os 497.897 Boletins de Urna (BUs) do 2º turno no país e comparamos com o total oficial de cada uma das 6.106 zonas eleitorais: a diferença é zero em todas, métrica por métrica. No exterior, 70 seções não têm boletim publicado no portal do TSE (831 votos), e são a única diferença encontrada.
- **O ganho de votos de Lula fecha com a conta oficial.** Lula ganhou 10,38 milhões de votos do 1º para o 2º turno e Flávio Bolsonaro, 3,72 milhões. Os 14,1 milhões somados vêm dos eleitores dos 10 candidatos eliminados, da queda de brancos e nulos e do aumento do comparecimento, e a conta fecha voto a voto.
- **A virada veio sobretudo de quem não tinha escolhido candidato no 1º turno.** Pela estimativa por zona, os eleitores dos eliminados se dividiram de forma quase parelha (cerca de 4,2 milhões para Lula e 3,5 milhões para Flávio). A diferença veio de quem votou branco, nulo ou não votou no 1º turno: cerca de 6,7 milhões para Lula e menos de 1 milhão para Flávio.
- **A votação foi prorrogada até as 19h numa parte das seções.** Uma liminar do ministro Cristiano Zanin (STF) estendeu o horário, e o TSE limitou a prorrogação às seções que ainda estavam abertas. Nos boletins, cerca de 6,3 mil urnas (1,3%) fecharam entre 19h e 19h15, quase todas no RJ, SP, BA, PE e PB.
- **Na Bahia, não há sinal de votos sem biometria concentrados no fim do dia.** O log de todas as 35 mil urnas mostra a proporção de votos sem biometria estável ao longo do dia; só 1 urna tem excesso estatístico na última hora, sem efeito no resultado.

A coleta dos BUs do 1º turno está em andamento, com término previsto para a madrugada de 27/10. Com ela, a comparação 1º × 2º turno urna a urna, hoje feita na Bahia, passa a valer para o país, e este documento será atualizado.

## A tese das divergências

A tese testada é que houve divergência no 2º turno: entre o que as urnas registraram e o que foi divulgado, ou um ganho de votos que os números não explicam. Ela foi dividida em hipóteses verificáveis, e nenhuma se confirmou até agora.

| Hipótese | Como testamos | Resultado | Abrangência |
| --- | --- | --- | --- |
| Os boletins de urna não batem com o total divulgado | Soma dos BUs × total oficial, zona a zona e métrica a métrica | 2º turno: nenhuma diferença nas 6.106 zonas do Brasil; no exterior, só as 70 seções sem BU publicado. 1º turno: nenhuma diferença nas 489 zonas de BA, AC e RR | 2º turno: Brasil; 1º turno: BA, AC e RR, demais em andamento |
| O ganho de "11 milhões" de Lula no 2º turno não tem explicação | Conta oficial: votos dos eliminados, queda de brancos e nulos, aumento do comparecimento; estimativa dos fluxos por zona | O ganho real foi de 10,38 milhões e cabe nos 14,1 milhões disponíveis; a conta fecha voto a voto | Brasil (totais oficiais) |
| O ganho veio de poucos lugares | Ganho por estado; desvio por urna | Ganho de Lula em todos os 27 estados e no exterior, maior nos mais populosos; só 0,2% das urnas da BA com desvio | Estados: Brasil; urnas: BA |
| Houve enchimento de urnas | Impressão digital comparecimento × votação; urnas com comparecimento de 100% | Sem mancha no canto de quase 100%; 9 urnas no país com 100% de comparecimento, com logs normais nas 3 conferidas; a abstenção nacional caiu 1,9 ponto | Impressão digital: BA; 100%: Brasil |
| Votos foram trocados entre candidatos em urnas específicas | Modelo 1º × 2º turno por urna, com teste de sensibilidade | 73 urnas da BA sinalizadas, sem direção: saldo de −201 votos para Lula e +121 para Flávio | BA; Brasil depois da coleta do 1º turno |
| Votos sem biometria foram inseridos no fim do dia | Log de cada urna: forma de habilitação de cada eleitor, hora a hora | Perfil estável (12,1% a 12,6% sem biometria em cada hora); 1 urna em 35.317 com excesso na última hora, sem efeito no resultado | BA |
| A prorrogação até as 19h mudou o resultado | Horário de encerramento nos BUs; votos depois das 17h no log | 6,3 mil urnas ficaram abertas até 19h; em Salvador, cerca de 240 votos depois das 18h em 5.124 urnas | Encerramento: Brasil; votos: BA |

## Em um parágrafo

> **Como fizemos.** Este trabalho testou a tese de que houve divergências no 2º turno da eleição presidencial de 2026. Os dados vêm da API de divulgação do Tribunal Superior Eleitoral, com a assinatura digital do TSE verificada em cada arquivo. Baixamos o Boletim de Urna de cada uma das 499.248 seções do 2º turno e comparamos a soma, zona a zona, com o resultado divulgado pelo tribunal: nas 6.106 zonas do Brasil, a diferença foi zero; no exterior, 70 seções não tinham boletim publicado. Para o país, decompusemos o ganho de votos de cada finalista entre os turnos a partir da totalização oficial e estimamos, por regressão ecológica, de onde vieram esses votos. Na Bahia, analisamos também o registro interno (log) de cada urna, que mostra a hora de cada voto e se o eleitor foi identificado pela biometria. Para encontrar comportamentos fora do padrão, cada urna foi comparada ao esperado para urnas com votação parecida no 1º turno no mesmo município e às demais urnas do mesmo local de votação, com correção estatística para múltiplas comparações. Uma urna sinalizada indica um desvio não explicado pelo modelo, não evidência de fraude.

## Fonte dos dados

Todos os dados vêm do TSE, pela API pública de divulgação de resultados ([resultados.tse.jus.br](https://resultados.tse.jus.br)), coletados em 26/10/2026. O 2º turno estava 100% totalizado desde 25/10, às 23h27.

| Dado | O que é | Uso |
| --- | --- | --- |
| Boletim de Urna (BU) | Arquivo de cada seção, o mesmo documento impresso e afixado ao fim da votação: aptos, comparecimento, votos por candidato, brancos, nulos, horário de abertura e encerramento | Unidade da análise |
| Log da urna | Registro interno de tudo o que a urna fez, com data e hora: ligada, aberta, cada eleitor habilitado (por biometria ou não), cada voto computado, encerramento | Horário dos votos e forma de identificação do eleitor |
| Lista de seções por estado | Todas as seções, quais foram agregadas a outras e quando cada BU chegou ao TSE | Saber quais urnas existem, sem adivinhar endereços |
| Resultado oficial por zona e nacional | Totalização divulgada pelo TSE, com votos por candidato | Conferência da soma dos BUs, conta nacional e fluxos |

- **Assinatura digital.** Os arquivos da API são assinados pelo TSE (Ed25519). A chave pública está no aplicativo oficial de resultados, e todo arquivo foi verificado antes de ser usado.
- **Cobertura.** 2º turno: BUs de todas as 499.248 seções do país e do exterior. 1º turno: BUs de Bahia, Acre e Roraima; a coleta do restante está em andamento. Totais oficiais por zona de todo o país, nos dois turnos. Logs: todas as urnas da Bahia nos dois turnos, mais municípios específicos citados neste documento.
- **Armazenamento.** Para caber em disco, a coleta nacional guarda de cada BU o resultado lido, o hash e o endereço, que permitem baixar o arquivo original de novo a qualquer momento. Os BUs brutos ficaram guardados para Bahia, Acre e Roraima.
- **Volume.** Cerca de 885 mil requisições para o 2º turno, a menos de 40 por segundo, abaixo do limite de 100 por segundo fixado pelo TSE. Houve 11 falhas de conexão no Pará, refeitas com sucesso.

## As verificações

Só a primeira pode provar erro ou manipulação. As outras apontam onde vale olhar.

1. **Integridade: BU × total oficial (prova).** Somamos os BUs de cada zona e comparamos com o resultado oficial da zona, métrica por métrica: aptos, comparecimento, cada candidato, brancos e nulos. Qualquer diferença seria um fato. Cada BU também passou por conferência interna: a soma dos votos tem que ser igual ao comparecimento, o comparecimento não pode passar dos aptos, e a seção descrita no arquivo tem que ser a mesma do endereço de onde ele veio.
2. **Comparação 1º × 2º turno por urna (indício).** Cada urna é descrita em percentual dos eleitores aptos: Lula, Flávio, eliminados, brancos e nulos, abstenção. Um modelo estatístico prevê o 2º turno de cada urna a partir do 1º, tomando como referência as outras urnas do mesmo município. A urna é sinalizada quando se afasta do previsto mais do que o tamanho dela explica, ou quando destoa das urnas do mesmo local de votação. Para não produzir alarmes por acaso, aplicamos a correção de Benjamini-Hochberg para múltiplas comparações (q < 0,05).
3. **Logs das urnas (indício).** Para cada voto, o log diz a hora e como o eleitor foi liberado: pela biometria; pelo mesário, quando a digital falha (o mesário confere o documento e libera com a própria digital); ou sem biometria cadastrada. Contamos os votos sem biometria por hora e testamos, urna a urna, se a última hora teve mais votos sem biometria do que o resto do dia da própria urna explicaria.
4. **Checagens complementares.**
    - A "impressão digital" comparecimento × votação (Klimek et al., 2012), que revela enchimento de urna como uma mancha no canto de quase 100% de comparecimento e de votos.
    - Um teste de sensibilidade: inserimos fraudes simuladas (troca de votos, enchimento, anulação) em 2% das urnas reais e medimos quantas o método encontra.
    - A decomposição do ganho nacional de votos com os totais oficiais e a estimativa dos fluxos de eleitores entre turnos (regressão ecológica de Goodman).
    - Horários de abertura e encerramento de cada urna, registrados no BU.

Regras de limpeza: urnas com eleitorado alterado em mais de 10% entre os turnos saíram da comparação 1º × 2º turno (4 na Bahia, provavelmente voto em trânsito, pedido por turno). Votos em número sem candidatura oficial foram contados como nulos, como faz a totalização.

## Resultados

### Brasil: os boletins batem com o resultado oficial

| Métrica (2º turno) | Total oficial | Soma dos BUs | Diferença |
| --- | ---: | ---: | ---: |
| Aptos | 158.745.502 | 158.743.025 | −2.477 |
| Comparecimento | 128.236.074 | 128.235.243 | −831 |
| Lula (13) | 64.256.232 | 64.255.787 | −445 |
| Flávio Bolsonaro (22) | 59.826.041 | 59.825.688 | −353 |
| Brancos | 1.430.496 | 1.430.484 | −12 |
| Nulos | 2.723.305 | 2.723.284 | −21 |

*Fonte: BUs e totalização oficial do TSE por zona, 2º turno de 2026. 499.178 BUs, 6.292 zonas (6.106 no Brasil e 186 cidades no exterior).*

- **No Brasil, a diferença é zero em todas as 6.106 zonas e em todas as métricas.** São 497.897 urnas.
- **Toda a diferença está no exterior.** Em 69 cidades, 70 seções não têm boletim publicado no portal: 41 aparecem sem recebimento e 29 sem BU totalizado. O TSE as dá como totalizadas, então os votos delas (831) estão no total oficial, mas o arquivo da urna não está disponível. Nas cidades do exterior sem seções faltando, a soma bate.
- **No 1º turno**, a conferência está concluída em Bahia, Acre e Roraima (489 zonas): diferença zero em todas. As demais unidades entram quando a coleta terminar.

### Brasil: de onde veio o ganho de votos

**Flávio terminou o 1º turno na frente, e Lula virou no 2º.**

| | 1º turno | 2º turno | Ganho |
| --- | ---: | ---: | ---: |
| Lula (13) | 53.879.538 | 64.256.232 | +10.376.694 |
| Flávio Bolsonaro (22) | 56.104.503 | 59.826.041 | +3.721.538 |

**Os dois finalistas ganharam juntos 14.098.232 votos, e a conta oficial fecha voto a voto:**

| De onde vieram | Votos | Parte do total |
| --- | ---: | ---: |
| Eleitores dos 10 candidatos eliminados no 1º turno | 9.316.747 | 66,1% |
| Ex-brancos e nulos (queda de brancos e nulos, de 5,98 para 4,15 milhões) | 1.821.246 | 12,9% |
| Novos votantes (abstenção de 21,1% para 19,2%) | 2.960.239 | 21,0% |
| **Total** | **14.098.232** | **100%** |

*Fonte: totalização oficial do TSE, 1º e 2º turnos de 2026, Brasil e exterior, 100% das seções.*

Os candidatos eliminados no 1º turno:

| Candidato | Votos no 1º turno | % dos válidos |
| --- | ---: | ---: |
| 70 Augusto Cury | 3.448.569 | 2,89% |
| 14 Renan Santos | 2.675.887 | 2,24% |
| 55 Ronaldo Caiado | 2.605.148 | 2,18% |
| 30 Zema | 326.488 | 0,27% |
| 80 Samara | 122.911 | 0,10% |
| 16 Hertz Dias | 43.103 | 0,04% |
| 27 Clariana Barão | 40.043 | 0,03% |
| 21 Edmilson Costa | 22.693 | 0,02% |
| 35 Veterinário Wilson Grassi | 16.881 | 0,01% |
| 29 Rui Costa Pimenta | 15.024 | 0,01% |
| **Total** | **9.316.747** | |

**Para onde foi cada grupo (estimativa).** A regressão ecológica usa as 6.106 zonas do Brasil, com uma matriz de transição para cada estado (o eleitor de um mesmo candidato se comporta de forma diferente em cada região). O modelo reproduz os totais do 2º turno: previu 64,05 milhões de votos para Lula (real: 64,06) e 59,67 milhões para Flávio (real: 59,65).

| Origem no 1º turno | Eleitores | Para Lula | Para Flávio | Branco, nulo ou não votou |
| --- | ---: | ---: | ---: | ---: |
| Branco ou nulo | 6,0 milhões | ~4,1 milhões (66–70%) | ~0 (0–1%) | ~31% |
| Não votou | 32,9 milhões | ~2,6 milhões (8–9%) | ~0,85 milhão (2–3%) | ~89% |
| Augusto Cury | 3,4 milhões | ~1,9 milhão (49–58%) | ~0,8 milhão (20–27%) | ~22% |
| Renan Santos | 2,7 milhões | ~1,6 milhão (57–65%) | ~0,8 milhão (25–32%) | ~11% |
| Ronaldo Caiado | 2,6 milhões | ~0,6 milhão (23–29%) | ~1,5 milhão (53–61%) | ~18% |
| Eliminados menores | 0,6 milhão | ~0,1 milhão (11–25%) | ~0,4 milhão (61–79%) | ~12% |

*Estimativa por zona eleitoral, 27 estados (sem o exterior). Entre parênteses, intervalo de 90% por reamostragem das zonas (60 réplicas). Lula manteve cerca de 99% dos próprios eleitores do 1º turno, e Flávio também.*

A leitura: entre os eleitores dos eliminados, a divisão foi quase parelha, cerca de 4,2 milhões para Lula e 3,5 milhões para Flávio. A diferença veio de quem não tinha escolhido candidato no 1º turno: cerca de 6,7 milhões dos que votaram branco, nulo ou não votaram foram para Lula, contra menos de 1 milhão para Flávio.

Cuidado com essa tabela: a regressão ecológica mostra para onde foram os votos das zonas, não o voto de cada eleitor. O intervalo entre parênteses mede só o ruído estatístico, não esse viés. O dado de Renan Santos é o menos intuitivo e deve ser lido com cautela; pesquisas pós-eleitorais são a melhor forma de confirmá-lo.

**Lula ganhou votos em todos os 27 estados e no exterior.** Ganho entre o 1º e o 2º turno, ordenado pelo ganho de Lula:

| UF | Ganho de Lula | Ganho de Flávio |
| --- | ---: | ---: |
| SP | +2.613.861 | +1.217.155 |
| MG | +1.162.163 | +464.238 |
| RJ | +872.372 | +202.189 |
| BA | +820.487 | +166.176 |
| PE | +563.542 | +94.511 |
| RS | +529.793 | +300.595 |
| PR | +511.907 | +346.099 |
| CE | +480.861 | +62.628 |
| GO | +396.675 | +293.446 |
| SC | +291.146 | +220.051 |
| PA | +263.212 | +35.983 |
| PB | +252.932 | +33.833 |
| MA | +241.930 | −9.069 |
| RN | +175.633 | +16.916 |
| AL | +157.162 | +8.422 |
| ES | +151.937 | +61.310 |
| DF | +149.597 | +69.926 |
| SE | +133.022 | +15.515 |
| PI | +130.279 | +8.831 |
| MT | +112.486 | +52.518 |
| MS | +112.118 | +54.541 |
| AM | +98.787 | −1.519 |
| RO | +43.779 | +21.394 |
| Exterior | +42.767 | +27.597 |
| TO | +38.953 | −1.405 |
| AP | +10.465 | −13.604 |
| AC | +9.743 | −15.092 |
| RR | +9.085 | −11.647 |
| **Brasil** | **+10.376.694** | **+3.721.538** |

*Fonte: totalização oficial do TSE por unidade da federação, 1º e 2º turnos de 2026. Sinal negativo = perda de votos.*

Em AC, RR, AP, TO, MA e AM, Flávio perdeu votos em números absolutos; no AC e em RR, o modelo urna a urna indica que parte dos eleitores dele no 1º turno não voltou para votar, e não que trocou de lado.

### A prorrogação da votação até as 19h

No dia da eleição, o ministro Cristiano Zanin, do STF, concedeu liminar estendendo a votação até as 19h em todo o país, a pedido da campanha de Lula; a campanha de Flávio havia pedido a prorrogação em 17 municípios de SP, PR e SC. O presidente do TSE, Kassio Nunes Marques, determinou que só as seções ainda abertas naquele momento ampliassem a votação, e o tribunal suspendeu a divulgação dos resultados até as 19h.

Os boletins mostram o efeito com clareza. Com fila, os encerramentos iriam rareando depois das 17h. Em vez disso:

| Encerramento (horário de Brasília) | Urnas |
| --- | ---: |
| 17h00 a 17h15 | 488.803 |
| 17h15 a 18h45 | cerca de 2.300, espalhadas |
| 18h45 a 19h00 | 399 |
| **19h00 a 19h15** | **6.316** |
| Depois de 19h15 | 36 |

- **Onde valeu:** as urnas encerradas às 19h estão em 142 municípios, quase todas no RJ (2.782), em SP (1.569), na BA (933), em PE (654) e na PB (275). No resto do país, praticamente todas já tinham fechado quando a decisão saiu.
- **Urnas abertas sem eleitor.** Em Salvador, 315 urnas cujo último voto foi entre 16h e 17h só foram encerradas por volta das 19h; em vários locais de votação, todas as urnas fecharam juntas, a partir das 19h00.
- **Poucos votos na prorrogação.** Em Salvador, o log registra cerca de 240 votos depois das 18h, em 5.124 urnas. A medição nacional dos votos dados depois das 17h, pelos logs das urnas prorrogadas, ainda não foi feita.

### Bahia: votos sem biometria no fim do dia

Analisamos o log de todas as urnas da Bahia nos dois turnos (70.952 logs). A contagem de votos do log confere com o comparecimento do BU em 70.597; das 355 que não conferem, 353 são urnas de contingência, cujo log não traz a votação inteira.

**A proporção de votos sem biometria é estável ao longo do dia:**

| Hora | 1º turno | 2º turno |
| --- | ---: | ---: |
| 8h | 12,7% | 12,1% |
| 12h | 11,5% | 12,2% |
| 15h | 12,0% | 12,6% |
| 16h (última hora) | 11,9% | 12,6% |

- **Urna a urna, só 1 de 35.317 tem excesso significativo de votos sem biometria na última hora no 2º turno.** No 1º turno foram 6.
- **Sem efeito no resultado:** urnas com mais votos sem biometria no fim do dia não tiveram mais votos para Lula nem para Flávio do que o modelo previa (correlações de +0,007 e −0,009), e a relação com o comparecimento é desprezível (+0,03).
- **Teolândia** é o único município que destoa: os votos sem biometria na última hora foram 21% no 2º turno, contra 11% no 1º (+10 pontos, contra +0,7 na média de 417 municípios). O padrão aparece em 22 das 37 urnas e não muda o resultado: no município, os dois candidatos ficaram dentro do previsto. Na seção 50 (zona 197), 4 eleitores seguidos foram liberados pelo mesário entre 16h06 e 16h09, e os 5 últimos votos (17h02 a 17h08) foram liberados por uma digital que não é de mesário registrado. A ata da seção pode esclarecer o caso.
- **Brecha de procedimento, não fraude:** em 93 de 220 urnas de quatro municípios testados, a urna libera o eleitor mesmo quando a digital que autoriza não é de um mesário registrado ("não é possível associar a habilitação"). Em Araci (zona 123, seção 98), isso aconteceu 69 vezes ao longo do dia, entre 8h53 e 16h15, sem mudança no comparecimento nem nos votos.

### Bahia: comparação 1º × 2º turno urna a urna

- 73 de 35.472 urnas (0,2%) sinalizadas, em 54 municípios.
- A maioria por brancos e nulos (23 urnas) ou abstenção (22), e não por troca entre candidatos.
- Somadas, as urnas sinalizadas ficam 201 votos abaixo do previsto para Lula e 121 acima para Flávio, num estado com 9,4 milhões de votantes.
- Único aglomerado: 4 urnas sinalizadas num mesmo local de votação em Araci (zona 123, local 1171). Nas seções 101 e 102, a abstenção caiu de 26% e 31% para 14% e Lula ganhou 41 e 56 votos, padrão típico de mobilização local.
- A impressão digital comparecimento × votação não mostra mancha no canto de quase 100%, em nenhum dos turnos.

O que o método detecta numa urna, medido com fraudes simuladas em 709 urnas reais:

| Cenário simulado | Alteração de 5 pontos percentuais | Alteração de 10 pontos percentuais |
| --- | ---: | ---: |
| Troca de votos entre candidatos | 31% a 35% | 98% a 99% |
| Enchimento (votos de ausentes) | 40% | 99% |
| Anulação de votos válidos | 94% | 100% |

### Casos fora do padrão que têm explicação no log

| Caso | O que chamou atenção | O que o log mostra |
| --- | --- | --- |
| Chapada Gaúcha (MG), z. 320, s. 185 | BU encerrado às 23h04, o mais tarde do país | A urna original falhou; às 23h, no cartório, uma urna de contingência recebeu a mídia de votação da original e gerou o BU com os 96 votos |
| Santa Maria de Jetibá (ES), z. 9, s. 112 | Um dos 2 BUs do país com código de urna raro (tipo 6) | BU gerado às 19h43 pelo programa de recuperação de dados do TSE, a partir da mídia da urna original |
| Duas Barras (RJ), z. 42, s. 108 | Encerrada às 20h45 | Último voto às 16h53; o mesário desligou a urna pela chave em vez de encerrar, e ela foi religada três vezes até ser encerrada; nenhum voto depois das 16h53 |
| Itajubá (MG), z. 134, s. 295 | Aberta às 13h08 | A urna só foi ligada às 13h; 9 dos 25 eleitores votaram, todos com biometria |
| Inácio Martins (PR), z. 34 | Seção 133 com 8% de comparecimento (18 de 215) | 5 urnas do município só foram ligadas entre 9h54 e 10h51 e tiveram comparecimento de 8% a 71%, contra cerca de 80% nas demais. O TRE-PR havia mudado locais de votação no município por causa de eventos climáticos extremos |
| Caraúbas (RN), z. 36, s. 69 | 100% de comparecimento (163 de 163) | Votos espalhados de 8h a 16h59, 86% com biometria; o mesmo padrão em Deputado Irapuan Pinheiro (CE) e Jaíba (MG) |
| Confresa (MT), z. 28, s. 200 | 309 votos para Lula, 0 para Flávio, nenhum branco ou nulo | Todos votaram entre 7h e 11h55 (hora local), 89% com biometria: padrão de comunidade que vota em bloco; local de votação a confirmar |

## Fatos curiosos verificados

Todos conferidos nos BUs e nos totais oficiais do 2º turno.

- **Uma cidade empatou:** Marquinho (PR), 1.530 votos para cada candidato.
- **Cinco cidades foram decididas por 1 voto:** Apiacá (ES), Altamira do Paraná (PR) e São João do Pau d'Alho (SP) para Lula; Nova Luzitânia (SP) e Anhanguera (GO) para Flávio.
- **Minas deu Lula por 50,4%**, cerca de 109 mil votos de diferença.
- **Extremos:** Carnaubeira da Penha (PE), 92,3% para Lula, e Monte Belo do Sul (RS), 86,8% para Flávio. Por estado: Piauí, 75,9% para Lula; Roraima, 72,5% para Flávio.
- **Exterior:** Lula teve 53,9%, com comparecimento de 42%. Ciudad del Este (Paraguai) deu 91,5% para Flávio e Ramallah (Palestina), 95,6% para Lula. Paris (83%), Berlim (87%) e Dublin (80%) foram de Lula; Nagóia (82%), Orlando (81%) e Miami (77%), de Flávio.
- **Urnas unânimes** (50 válidos ou mais): 88 com 100% para Lula e 3 com 100% para Flávio. A maior é Tabatinga (AM), seção 61: 354 a 0.
- **Comparecimento:** 9 urnas tiveram 100%; o menor município foi Itaubal (AP), com 59%, e o maior, Bela Vista do Piauí (PI), com 93%.
- **Empates por urna:** 2.098 urnas terminaram com o mesmo número de votos para os dois, dentro do esperado ao acaso.
- **Urnas de contingência:** 5.712 (1,1%); o exterior tem a maior proporção (3,3%).

## Como interpretar

Uma urna sinalizada é um ponto para conferência, não um indício de fraude. Desvios grandes têm muitas explicações comuns: perfil local, mobilização e transporte de eleitores, urna pequena, mudança de eleitorado.

| Os dados permitem dizer | Os dados não permitem dizer |
| --- | --- |
| A soma dos boletins de urna do 2º turno confere com o resultado oficial em todas as 6.106 zonas do Brasil | Que as 70 seções do exterior sem BU publicado conferem (os 831 votos delas não puderam ser checados) |
| A soma do 1º turno confere em BA, AC e RR | Que o mesmo vale para o 1º turno nas demais unidades, ainda não verificadas |
| O ganho de 10,38 milhões de votos de Lula cabe nos 14,1 milhões de votos disponíveis entre os turnos | Em quem cada eleitor votou: os fluxos são estimativas agregadas |
| 73 urnas da Bahia (0,2%) tiveram desvio não explicado pelo modelo | Que essas urnas tiveram fraude, são "suspeitas" ou tiveram votos "desviados" |
| Na Bahia, não houve concentração de votos sem biometria no fim do dia | Que o mesmo vale para os outros estados, cujos logs não foram analisados |
| O método detecta uma troca de 10 pontos percentuais numa urna em 98% dos casos | Que não houve nenhuma alteração menor que isso |

Vocabulário recomendado: "desvio não explicado pelo modelo" e "urna sinalizada para conferência". Evitar "suspeita", "irregular" e "fraude" para resultados estatísticos.

## Limitações

- **1º turno parcial.** A conferência BU × total oficial do 1º turno e a comparação 1º × 2º turno urna a urna estão concluídas em 3 estados; a coleta do restante termina na madrugada de 27/10.
- **Exterior.** 70 seções sem BU publicado no portal (831 votos) não puderam ser conferidas.
- **Logs só na Bahia.** A análise de biometria e horário de cada voto cobre a Bahia inteira e casos pontuais em outros estados.
- **Prorrogação.** O número de votos dados depois das 17h nas urnas prorrogadas ainda não foi medido no país; na Bahia, foi pequeno.
- **Estimativa de fluxos.** A regressão ecológica descreve médias por zona e pode sofrer viés de agregação; os intervalos medem só o ruído estatístico.
- **Sem base histórica.** A análise usa só 2026, então não dá para comparar a taxa de urnas sinalizadas com a de eleições anteriores.
- **Resultado preliminar.** O modelo não foi travado em um conjunto de estados de teste antes da rodada final.
- **Sensibilidade.** Trocas de até 5 pontos percentuais numa urna passam despercebidas na maior parte das vezes: o método pega cerca de 30% delas.
- **Casos extremos.** Os resíduos têm mais casos extremos que uma distribuição normal, então parte das sinalizações reflete limites do modelo.
- **Status desatualizado no portal.** Em Lauro de Freitas (BA), zona 180, as 413 seções aparecem como "Recebido" e não "Totalizado". Os BUs foram usados, e a soma bateu com o total oficial da zona.

## Reprodutibilidade e referências

Todo o processo é um programa em Python que roda de ponta a ponta (coletar, consolidar, reconciliar, analisar) e registra a origem e a data de cada arquivo baixado. De cada urna, guarda o BU bruto (Bahia, Acre e Roraima) ou o hash e o endereço que permitem baixá-lo de novo (demais estados). Qualquer pessoa pode refazer a análise com dados públicos.

Código, dados resumidos e instruções estão no repositório do projeto. Na pasta `resultados/`:

- `brasil/conferencia_bu_x_oficial_2t.md`: conferência BU × total oficial do 2º turno, zona a zona, Brasil e exterior.
- `ba/relatorio_ba.html` (e o mesmo para AC e RR): relatório interativo, com link para o BU oficial de cada urna sinalizada, nos dois turnos.
- `ba/urnas_ba.csv.gz`: uma linha por urna da Bahia, com votos, previsto, desvio e sinalização.
- `brasil/decomposicao_ufs.csv` e `brasil/decomposicao_brasil.csv`: ganho de votos por estado e votos dos eliminados, a partir dos totais oficiais.
- `brasil/fluxos_zonas.csv`: estimativa de para onde foi cada grupo de eleitores do 1º turno, com intervalos.
- `logs_ba/fim_do_dia.csv.gz` e `logs_ba/perfil_horas.csv`: votos sem biometria por urna e por hora, Bahia.

Referências:

- [Portal de resultados do TSE](https://resultados.tse.jus.br): boletins de urna, logs e totalização.
- [Portal de dados abertos do TSE, resultados 2026](https://dadosabertos.tse.jus.br/dataset/resultados-2026): usado para conferir o formato dos arquivos.
- [Agência Brasil — TSE: seções eleitorais ainda abertas devem manter votação até as 19h](https://agenciabrasil.ebc.com.br/politica/noticia/2026-10/tse-secoes-eleitorais-ainda-abertas-devem-manter-votacao-ate-19h)
- [Poder360 — Zanin prorroga votação do 2º turno até 19h](https://www.poder360.com.br/poder-eleicoes-2026/zanin-prorroga-votacao-do-2o-turno-ate-19h/)
- [Gazeta do Povo — STF concede liminar e prorroga votação até as 19h](https://www.gazetadopovo.com.br/eleicoes/2026/stf-concede-liminar-e-prorroga-votacao-ate-as-19h-em-todo-o-brasil/)
- [Brasil 61 — Paraná registra mudanças de local de votação para o 2º turno](https://brasil61.com/n/parana-registra-oito-mudancas-de-local-de-votacao-para-o-2-turno-bras2617327)
- [Klimek, Yegorov, Hanel e Thurner, "Statistical detection of systematic election irregularities", PNAS, 2012](https://doi.org/10.1073/pnas.1210722109): impressão digital comparecimento × votação.
- Benjamini e Hochberg, 1995, Journal of the Royal Statistical Society B: correção para múltiplas comparações.
- Goodman, 1953, American Sociological Review: regressão ecológica.
- [Projeto "Como meus vizinhos votam"](https://github.com/juliosaulo/como-meus-vizinhos-votam): documentação pública do formato dos BUs de 2026 e das regras de consumo da API do TSE, usada como apoio.
