# Como fizemos isso com IA, e como você pode explorar com IA

Este projeto foi construído em cerca de um dia por um jornalista trabalhando com o
[Claude Code](https://claude.com/claude-code), o agente de programação da Anthropic, que roda no terminal, lê
e escreve código, executa comandos e consulta a web. Este documento conta como foi a divisão de trabalho, o
que a IA errou e como foi corrigido, e como qualquer pessoa pode usar IA para explorar os dados a partir daqui.

## Parte 1 — Como construímos

### A divisão de trabalho

| O jornalista | O Claude |
| --- | --- |
| Fez as perguntas: "o que explica 11 milhões de votos a mais?", "e votos sem biometria no fim do dia?", "e na Bahia?" | Transformou cada pergunta num teste verificável, escreveu o código e rodou |
| Decidiu o escopo, o que publicar e com que licença | Propôs opções, com uma recomendação, e executou a escolhida |
| Trouxe conhecimento que não estava nos dados (a prorrogação da votação até as 19h) | Conferiu o que o jornalista disse contra os dados e as fontes antes de incorporar |
| Revisou os textos e decidiu o que publicar | Redigiu a metodologia, as tabelas e os resumos, com os números conferidos |

### As etapas

1. **A pergunta antes do código.** Começamos por uma especificação (`SPEC.md`). Ela diz o que o sistema
   afirma e o que não afirma, e fixa o vocabulário: "desvio não explicado pelo modelo", nunca "fraude". Essa
   regra valeu para todo texto produzido depois.
2. **Entender a fonte.** O Claude explorou a API de divulgação do TSE e descobriu que os arquivos vêm
   assinados digitalmente. Encontrou a chave pública dentro do aplicativo oficial de resultados, e a partir
   daí todo arquivo baixado passou a ser verificado. Os códigos de eleição não ficam fixos no código: são
   lidos do próprio TSE a cada execução.
3. **Começar pequeno.** O programa foi testado primeiro no Acre e em Roraima, os menores estados, depois na
   Bahia e só então no país. Cada etapa só avançou quando a conferência anterior bateu.
4. **A prova antes do indício.** A primeira verificação é exata: a soma dos boletins de urna de cada zona
   contra o total oficial da zona. Os modelos estatísticos vieram depois, e o próprio método foi testado:
   inserimos fraudes simuladas em urnas reais para medir o que ele consegue detectar.
5. **Ir até o registro da urna.** Para a pergunta sobre biometria, o Claude decifrou o formato dos logs das
   urnas e classificou cada voto pela forma como o eleitor foi liberado. A classificação foi validada contando
   os votos do log e comparando com o comparecimento do boletim: batem em 99,5% das urnas, e as exceções têm
   explicação (urnas de contingência).
6. **Explicar o estranho.** Quando um número fugia do padrão, por exemplo uma urna fechada às 23h ou uma seção
   com 8% de comparecimento, o Claude baixou o log daquela urna e leu o que aconteceu, antes de chamar aquilo
   de "caso".
7. **Escrever e publicar.** A metodologia foi redigida para leitores sem formação técnica. O código,
   os resumos e as licenças foram organizados neste repositório.

### O que a IA errou, e como foi corrigido

Os erros também fazem parte do método. Todos os abaixo foram pegos antes da publicação.

| Erro | Como foi descoberto | Correção |
| --- | --- | --- |
| Atribuiu a fila os mais de 6 mil fechamentos de urna depois das 18h | O jornalista lembrou que a votação foi prorrogada até as 19h | Os dados confirmaram: os fechamentos se concentram entre 19h00 e 19h15, não vão rareando como numa fila. A prorrogação entrou na metodologia, com as fontes |
| Contou 11 candidatos eliminados | Conferência com o arquivo oficial do TSE | São 10 |
| Primeira estimativa de fluxos de votos não fechava com os totais | O próprio Claude comparou o previsto com o observado | Refez o modelo por estado, com restrições; o ajuste passou a reproduzir os totais |
| Tratou o log da urna como um tipo de arquivo comprimido que ele não é | O programa falhou ao abrir | Era um ZIP comum |
| Uma única categoria para "voto sem biometria" misturava situações diferentes | Leitura dos logs de urnas reais | Cinco categorias, entre elas a liberação por digital que não é de mesário registrado |
| A varredura dos logs da Bahia caiu na urna 27 mil e perdeu o progresso | Erro de conexão no meio da leitura | O programa passou a gravar cada urna assim que termina e a retomar de onde parou |

### Princípios que funcionaram

- **Nenhum número sem conferência.** Cada valor deste projeto tem um comando que o reproduz.
- **Separar prova de indício.** Diferença entre boletim e total oficial seria um fato. Uma urna sinalizada
  pelo modelo é só um ponto para conferir.
- **Respeitar a fonte.** A coleta fica abaixo do limite de requisições do TSE, que bloqueia quem o excede.
- **Não expor pessoas.** Os logs trazem o título de eleitor dos mesários e não são publicados.
- **O humano decide.** Escopo, publicação, licença e vocabulário foram decisões do jornalista.

## Parte 2 — Como você pode explorar com IA

### Opção 1: com um agente de programação, no repositório

Com um agente como o Claude Code, você abre a pasta do projeto e conversa em português. O agente lê o código,
roda os comandos e responde com os dados.

```bash
git clone <endereço deste repositório> eleicoes-2026-urnas
cd eleicoes-2026-urnas
claude
```

Perguntas para começar:

- "Leia o README e a metodologia e me explique, em cinco linhas, o que este projeto testa."
- "Colete o 2º turno do meu estado (PE) e confira se a soma dos boletins bate com o total oficial."
- "Quais urnas do município de Caruaru foram sinalizadas pelo modelo? Por quê?"
- "Baixe o log da seção 50 da zona 197 de Teolândia (BA) e me mostre, minuto a minuto, como os eleitores foram liberados depois das 16h."
- "No meu estado, quantas urnas ficaram abertas até as 19h por causa da prorrogação? Quantas pessoas votaram depois das 17h?"
- "Refaça a estimativa de fluxos só para o Nordeste."

O agente respeita a configuração do projeto, mas a responsabilidade pelo limite do TSE é de quem roda: no
máximo 100 requisições por segundo por IP, e nada de duas coletas grandes ao mesmo tempo.

### Opção 2: num chat, com os arquivos de resultados

Sem instalar nada, você pode enviar os arquivos de `resultados/` para um assistente de IA com análise de dados
(Claude, ChatGPT ou similar) e perguntar:

- Com `brasil/decomposicao_ufs.csv`: "Em quais estados o ganho de Flávio foi negativo? Monte um gráfico do ganho de cada candidato por estado."
- Com `ba/urnas_ba.csv.gz`: "Liste as urnas sinalizadas de Salvador, com o desvio de cada candidato em votos."
- Com `logs_ba/perfil_horas.csv`: "Compare, hora a hora, a proporção de votos sem biometria no 1º e no 2º turno."
- Com `brasil/fluxos_zonas.csv`: "Explique esta tabela para um leitor leigo, sem exagerar o que ela permite dizer."

Os arquivos `.csv.gz` são CSV comprimidos; se o assistente não abrir, descompacte antes.

### Cuidados ao usar IA com estes dados

- **Confira na fonte.** Antes de publicar qualquer número sobre uma urna, abra o boletim oficial dela no
  portal do TSE; os relatórios HTML trazem o link.
- **A IA pode errar com convicção.** Peça que ela mostre o comando ou a conta que gerou cada número, e refaça
  as contas que forem para a reportagem.
- **Mantenha o vocabulário.** Uma urna sinalizada tem um "desvio não explicado pelo modelo". Não é "suspeita"
  nem "fraude", por mais que o texto gerado puxe para isso.
- **Fluxos são médias.** A estimativa de para onde foi o eleitor de cada candidato vem de zonas, não de
  pessoas. Não use essa tabela para afirmar em quem um grupo de eleitores votou.
- **Não publique dados pessoais.** Se você baixar logs com `scripts/logs_urnas.py`, eles trazem o título de
  eleitor dos mesários.
