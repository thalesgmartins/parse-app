# Documentacao Tecnica - ParseApp

Este diretorio centraliza a documentacao tecnica, arquitetural e de conformidade legal da plataforma **ParseApp**, desenvolvida para a disciplina de **Arquitetura de Software SaaS** (Engenharia de Computacao).

---

## Estrutura da Documentacao

A documentacao esta organizada nas seguintes secoes especializadas:

1. **[Modelagem Arquitetural (C4 Model)](arquitetura/c4-model.md)**
   - **Nivel 1 - Diagrama de Contexto:** Interacao entre o Advogado, o ParseApp, servicos governamentais (Meu INSS / Gov.br), gateways de pagamento e servicos de notificacao.
   - **Nivel 2 - Diagrama de Conteineres:** Divisao dos conteineres da aplicacao (Front-end HTML/HTMX, API FastAPI, Motor de Processamento com pdfplumber e Banco de Dados PostgreSQL).

2. **Registros de Decisoes de Arquitetura (ADRs)**
   - **[ADR 001 - Isolamento de Dados (Multi-Tenancy Obrigatório)](arquitetura/adrs/001-multi-tenancy-isolamento.md):** Adocao do modelo Pool com isolamento logico via chaves estrangeiras e Row-Level Security no PostgreSQL em vez de bancos separados por escritorio.
   - **[ADR 002 - Processamento Assincrono com Fila Nativa no PostgreSQL](arquitetura/adrs/002-processamento-assincrono-fila-postgres.md):** Emprego da clausula `FOR UPDATE SKIP LOCKED` do PostgreSQL como fila ACID confiavel, sem a sobrecarga operacional de um Redis intermediario.
   - **[ADR 003 - Armazenamento Efemero de Documentos](arquitetura/adrs/003-armazenamento-efemero.md):** Minimizacao do ciclo de vida dos PDFs originais, persistindo em disco temporario apenas durante o parsing e descartando obrigatoriamente no bloco `finally:`.
   - **[ADR 004 - Rejeicao de Mecanismo de Auto-Atualizacao In-App](arquitetura/adrs/004-descarte-auto-update-in-app.md):** Fundamentacao arquitetural do descarte do botao de atualizacao pelo cliente em modelo Cloud SaaS centralizado.

3. **[Mapeamento de Conformidade com a LGPD (Lei 13.709/2018)](lgpd.md)**
   - Papéis definidos: Titular dos Dados (segurado), Controlador (escritorio de advocacia) e Operador (ParseApp).
   - Dados tratados, sensibilidade juridica e bases legais (Art. 11 da LGPD).
   - Medidas tecnicas de protecao: isolamento logico, descarte efemero e auditoria sanitizada.

---

## Referencias
- Documento de entrega preliminar: [`docs/Checkpoint 1.pdf`](Checkpoint%201.pdf)
- Código-fonte principal da aplicacao: [`app/`](../app/)
- Suite de testes: [`tests/`](../tests/)
