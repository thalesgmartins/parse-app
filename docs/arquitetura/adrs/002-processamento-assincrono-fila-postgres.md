# ADR 002: Processamento Assincrono de PDFs com Fila Nativa no PostgreSQL

## Status
Aprovado

## Data
2026-10-08 (Implementado na Fase 4)

## Contexto
Extratos CNIS oficiais podem conter de 5 a mais de 80 paginas, abrangendo ate quatro decadas de historico contributivo de um segurado. O processo de analise textual via `pdfplumber` exige varredura pagina a pagina e operacoes de regex/split, demandando entre 3 e 25 segundos dependendo do tamanho do arquivo.

Processar esse arquivo diretamente no ciclo sincrono da requisicao HTTP (`POST /cnis/extrair-html`) apresentava serios problemas arquiteturais:
1. **Bloqueio de Workers HTTP:** Cada requisicao mantinha um processo Uvicorn/FastAPI bloqueado pelo tempo total da analise, degradando drasticamente o throughput global da aplicacao.
2. **Timeout de Rede:** Conexoes lentas ou navegadores poderiam sofrer *Gateway Timeout* (HTTP 504).
3. **Perda de Estado:** Qualquer instabilidade no cliente durante o upload resultava no aborto de todo o trabalho sem rastreabilidade.

Avaliou-se a introducao de um *message broker* dedicado (como Redis + Celery ou RabbitMQ) versus a utilizacao do proprio PostgreSQL como fila de trabalhos.

## Decisao
Decidiu-se pela adocao de **Processamento Assincrono com Fila Nativa no PostgreSQL** utilizando o operador relacional `FOR UPDATE SKIP LOCKED`:

- **Entidade de Fila:** Cria-se a tabela `extraction_jobs` com status `pending`, `processing`, `completed` e `failed`.
- **Concorrencia Segura:** Os workers adquirem o proximo trabalho disponivel executando:
  ```sql
  SELECT * FROM extraction_jobs
  WHERE status = 'pending'
  ORDER BY created_at ASC
  LIMIT 1
  FOR UPDATE SKIP LOCKED;
  ```
  O bloqueio em nivel de linha com `SKIP LOCKED` faz com que outros workers concorrentes ignorem os registros bloqueados e avancem para o proximo sem travar a conexao.
- **Transicao de Status:** O worker altera atomicamente o status para `processing` e, ao termino, registra as metricas em `completed` ou `failed`.
- **Orquestracao Imediata:** O endpoint HTTP salva o arquivo no disco, persiste o job no banco e despacha a execucao via `BackgroundTasks` do FastAPI, retornando a resposta ao cliente em menos de 50ms.
- **Frontend com Polling HTMX:** O cliente recebe um fragmento HTML com `hx-trigger="every 1s"` que consulta `GET /cnis/jobs/{job_id}` e interrompe o polling de forma transparente na conclusao.

A adocao de Redis ou RabbitMQ foi expressamente rejeitada para manter a arquitetura enxuta e robusta no estagio atual.

## Consequencias

### Positivas
- **Arquitetura Enxuta (KISS):** O `docker-compose.yml` permanece composto exclusivamente pelo PostgreSQL e pelo servico da API, sem overhead de memoria ou custos operacionais de gerenciar servicos adicionais.
- **Garantias ACID:** A criacao do job, o registro de auditoria e a gravacao das contribuicoes ocorrem dentro do mesmo mecanismo transacional relacional.
- **Resiliencia contra Queda de Servidor:** Caso o container seja reiniciado subitamente durante o processamento, os jobs permanecem no banco de dados. O evento de startup (`lifespan`) detecta jobs em `processing` interrompidos e os restaura para `pending`.
- **Excelente Experiencia do Usuario (UX):** O usuario recebe feedback visual instantaneo, com spinner e barra de progresso animados, sem travamento de tela.

### Negativas / Riscos Mitigados
- **Escala Extrema de Eventos:** Bancos relacionais nao sao indicados para filas com mais de 20.000 mensagens/segundo devido a churn de MVCC.
  - *Mitigacao:* No contexto de processamento de CNIS juridico, o volume estimado e de dezenas a centenas de arquivos por hora, operando com ampla folga de capacidade. Caso a demanda atinja escala massiva no futuro, a interface de servico (`app.services.worker`) permite a substituicao do backend de fila sem alterar os endpoints publicos.
