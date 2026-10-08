# ADR 003: Armazenamento Efemero de Documentos e Minimizacao de Dados

## Status
Aprovado

## Data
2026-10-06 (Formalizado no Checkpoint 1 e implementado na Fase 4)

## Contexto
O extrato CNIS contem dados de alto impacto sobre a vida do segurado: historico profissional completo, relacao de salarios nominais desde 1982, dados de identificacao (CPF, NIT/PIS) e indicativos de beneficios por incapacidade ou saude (auxilio-doenca e aposentadoria por invalidez).

A equipe precisava decidir se deveria armazenar de forma permanente os arquivos PDF originais submetidos (utilizando servicos de *object storage* como Amazon S3, Google Cloud Storage ou MinIO) ou trata-los de maneira efemera.

Manter copias permanentes dos PDFs introduzia os seguintes desafios:
1. **Passivo Juridico e Risco de Vazamento (LGPD):** A guarda desnecessaria de documentos originais amplia substancialmente a superficie de ataque da aplicacao.
2. **Custo de Armazenamento:** Acumulo continuo de dezenas de gigabytes de arquivos binarios sem necessidade apos a conclusao dos calculos.
3. **Consumo de Memoria RAM:** Carregar o binario do PDF inteiramente em memoria durante o upload para processa-lo síncronamente sobrecarregava os contêineres.

## Decisao
Adotamos uma politica rigorosa de **Armazenamento Efemero e Minimizacao de Dados**:

1. **Gravacao Streaming em Volume Efemero:**
   Durante o upload (`POST /cnis/extrair-html`), o fluxo multipart do arquivo e gravado em blocos (via `shutil.copyfileobj`) diretamente no diretorio temporario `/tmp/uploads/parseapp/{job_id}.pdf`. O arquivo nunca e acumulado de forma integral na RAM dos processos web.

2. **Extracao e Persistencia Apenas dos Dados Estruturados:**
   O worker assincrono le o arquivo a partir do disco temporario, realiza o parsing e armazena unicamente os dados tabulares necessarios para os calculos juridicos nas tabelas `clientes` e `contribuicoes`.

3. **Exclusao Fisica Obrigatoria no Bloco `finally:`:**
   Independentemente do resultado da extracao (sucesso ou falha por erro de formato), a rotina de processamento garante a remocao imediata do arquivo do disco atraves de `os.unlink` dentro de um bloco `finally:`.

Rejeitamos o armazenamento permanente de arquivos PDF brutos em servicos de nuvem S3/MinIO.

## Consequencias

### Positivas
- **Conformidade com o Artigo 11 da LGPD:** Cumprimento direto dos principios de finalidade, necessidade e minimizacao da Lei 13.709/2018. O dado pessoal e retido somente na medida exata para a execucao dos calculos contratados pelo titular com o escritorio.
- **Reducao Radical da Superficie de Ataque:** Caso o servidor sofra um comprometimento fisico ou intrusao, nao ha repositorio historico de extratos governamentais armazenados em disco.
- **Zero Custo de Object Storage:** Dispensa a contratacao e a configuracao de buckets pagos de armazenamento de objetos.
- **Eficiencia de Memoria:** A RAM do servidor permanece constante e previsivel, nao variando com o tamanho do documento submetido.

### Negativas / Riscos Mitigados
- **Impossibilidade de Reanalise Direta do PDF Original:** Se o parser for aprimorado futuramente, nao havera como reprocessar retroativamente os mesmos arquivos originais sem que o usuario realize novo upload.
  - *Mitigacao aceita:* Na rotina previdenciaria, extratos sofrem atualizacoes constantes pelo INSS (inclusao de novos recolhimentos e atualizacao monetaria). Quando uma nova acao e distribuida, os advogados obrigatoriamente solicitam do cliente um extrato CNIS atualizado.
