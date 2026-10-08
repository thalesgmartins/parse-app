# ParseApp - Plataforma SaaS para Extracao de Extratos CNIS

O **ParseApp** e uma solucao SaaS B2B multi-tenant projetada para escritorios de advocacia previdenciaria. A plataforma automatiza a ingestao, o parsing inteligente e a estruturacao de dados de extratos previdenciarios (CNIS - Cadastro Nacional de Informacoes Sociais) emitidos em formato PDF pelo portal Meu INSS / Gov.br.

A ferramenta elimina o trabalho manual de digitacao de historicos contributivos, reduz gargalos operacionais e viabiliza a geracao agil de calculos previdenciarios (RMI, revisoes e liquidacao de sentenca) em conformidade com a Lei Geral de Protecao de Dados (Lei 13.709/2018 - LGPD).

---

## Indice

- [Visao Geral do Produto](#visao-geral-do-produto)
- [Arquitetura da Solucao](#arquitetura-da-solucao)
- [Stack Tecnologico](#stack-tecnologico)
- [Como Executar o Projeto](#como-executar-o-projeto)
  - [Opcao 1: Docker Compose (Recomendado)](#opcao-1-docker-compose-recomendado)
  - [Opcao 2: Desenvolvimento Local com uv](#opcao-2-desenvolvimento-local-com-uv)
  - [Modo CLI (Linha de Comando)](#modo-cli-linha-de-comando)
- [Qualidade de Codigo e Testes](#qualidade-de-codigo-e-testes)
- [Logica de Extracao do CNIS](#logica-de-extracao-do-cnis)
- [Seguranca e Conformidade LGPD](#seguranca-e-conformidade-lgpd)
- [Estrutura do Repositorio](#estrutura-do-repositorio)
- [Documentacao Tecnica Complementar](#documentacao-tecnica-complementar)

---

## Visao Geral do Produto

Escritorios de advocacia previdenciaria frequentemente despendem horas digitando manualmente historicos de vinculos, periodos trabalhados e remuneracoes contidas em extratos CNIS de dezenas de paginas. Esse processo manual atrasa a entrega de pareceres juridicos e introduz riscos de erros materiais em peticoes iniciais e recursos perante o INSS ou Poder Judiciario.

O ParseApp resolve esse problema por meio de uma plataforma centralizada onde:
1. Cada escritorio (tenant) possui seu cadastro seguro com isolamento logico multi-tenant.
2. O advogado vincula ou cadastra rapidamente o cliente segurado.
3. Faz o upload do documento PDF oficial.
4. O sistema enfileira o processamento em segundo plano sem bloquear a interface.
5. Em segundos, as competencias, salarios e metricas sao estruturadas no PostgreSQL e apresentadas em tela via HTMX.

---

## Arquitetura da Solucao

A solucao adota uma arquitetura orientada a resiliencia e alta performance, evitando sobrecarga de memoria e travamento de workers HTTP:

```mermaid
flowchart TD
    subgraph Cliente ["Navegador Web / Cliente"]
        A[Advogado / Usuario] -->|POST /cnis/extrair-html| B[Formulario HTMX]
        B -->|Recebe card de polling| C[Poller HTMX every 1s]
        C -->|GET /cnis/jobs/job_id| D[Resultado Final / Tabela]
    end

    subgraph API ["FastAPI HTTP Layer"]
        B -->|Upload stream multipart| E[Endpoint Ingestao]
        E -->|Salva em disco efemero| F[/tmp/uploads/job_id.pdf]
        E -->|Registra job status: pending| G[(PostgreSQL extraction_jobs)]
        E -->|Dispara tarefa assincrona| H[Background Task Runner]
    end

    subgraph Worker ["Worker Assincrono"]
        H -->|SELECT FOR UPDATE SKIP LOCKED| G
        H -->|Leitura por stream| F
        H -->|Extracao de texto| I[Motor pdfplumber]
        I -->|Salva contribuicoes| J[(PostgreSQL contribuicoes)]
        I -->|Registra auditoria| K[(PostgreSQL extractions_logs)]
        I -->|Atualiza status: completed| G
        I -->|Finally: os.unlink| L[Delecao Imediata do PDF]
    end
```

### Principais Destaques Arquiteturais
- **Fila Nativa com `FOR UPDATE SKIP LOCKED`:** O PostgreSQL e utilizado como fila de processamento transacional ACID. O operador `SKIP LOCKED` impede condicoes de corrida quando multiplos workers disputam jobs pendentes.
- **Volume Efemero:** Arquivos PDF enviados por upload sao gravados em blocos diretamente em `/tmp/uploads/parseapp`, impedindo a retencao de dezenas de megabytes na memoria RAM dos processos FastAPI.
- **Minimizacao LGPD:** Ao concluir ou falhar o processamento, o arquivo temporario e imediatamente removido do disco no bloco `finally:`.
- **UX Reativa com HTMX:** A interface nao depende de SPAs pesadas (React/Vue). O endpoint responde em menos de 50ms com um fragmento que consulta o status do job a cada 1 segundo e encerra o polling automaticamente na finalizacao.

---

## Stack Tecnologico

- **Linguagem:** Python 3.12
- **Framework Web:** [FastAPI](https://fastapi.tiangolo.com/) com Starlette
- **Camada de Dados & ORM:** [SQLAlchemy 2.0](https://www.sqlalchemy.org/) (Mapped columns, tipagem estrita)
- **Migracoes de Banco:** [Alembic](https://alembic.sqlalchemy.org/)
- **Banco de Dados:** [PostgreSQL 16](https://www.postgresql.org/) (driver `psycopg 3` binario)
- **Motor de Extracao de PDF:** [pdfplumber](https://github.com/jsvine/pdfplumber)
- **Frontend & Reatividade:** HTML5 semantico, [HTMX](https://htmx.org/) (local offline) e Jinja2
- **Estilizacao:** [Tailwind CSS](https://tailwindcss.com/) com paleta corporativa compilada localmente (21 KB)
- **Autenticacao & Seguranca:** JWT (PyJWT), senhas com hash bcrypt
- **Gerenciador de Pacotes:** [uv](https://docs.astral.sh/uv/) (Astral)
- **Infraestrutura:** Docker e Docker Compose
- **CI/CD:** GitHub Actions com Release Please para versionamento semantico

---

## Como Executar o Projeto

### Opcao 1: Docker Compose (Recomendado)

O Docker Compose sobe a aplicacao e o PostgreSQL em contêineres orquestrados com verificacao de saude (*healthcheck*):

1. Clone o repositorio:
   ```bash
   git clone https://github.com/thalesgmartins/parse-app.git
   cd parse-app
   ```

2. Crie o arquivo `.env` a partir do modelo:
   ```bash
   cp .env.example .env
   ```

3. Inicie os servicos com build:
   ```bash
   docker compose up -d --build
   ```

4. Acesse a aplicacao no navegador:
   - **Dashboard:** [http://localhost:8000/dashboard](http://localhost:8000/dashboard)
   - **Login:** [http://localhost:8000/login](http://localhost:8000/login)
   - **Documentacao OpenAPI:** [http://localhost:8000/docs](http://localhost:8000/docs)

Para acompanhar os logs de execucao:
```bash
docker compose logs -f parse-app
```

---

### Opcao 2: Desenvolvimento Local com uv

Para rodar fora do Docker utilizando o gerenciador de pacotes ultrarrapido `uv`:

1. Instale o `uv` (caso ainda nao possua):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Sincronize as dependencias do projeto e o ambiente virtual:
   ```bash
   uv sync
   ```

3. Certifique-se de ter uma instancia do PostgreSQL rodando localmente na porta 5432 (ou suba apenas o servico de banco via docker):
   ```bash
   docker compose up -d postgres
   ```

4. Aplique as migracoes do banco de dados com o Alembic:
   ```bash
   DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/parseapp uv run alembic upgrade head
   ```

5. Inicie o servidor FastAPI em modo de recarregamento automatico (*hot-reload*):
   ```bash
   DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/parseapp uv run uvicorn app.main:app --reload --port 8000
   ```

---

### Modo CLI (Linha de Comando)

Para extrair informacoes de um extrato CNIS diretamente pelo terminal sem subir a interface web:

```bash
uv run python3 -m app.cli --path "caminho/para/extrato.pdf"
```

O comando executara o parser em modo texto pesquisavel e imprimira a lista estruturada das competencias e remuneracoes identificadas.

---

## Qualidade de Codigo e Testes

O projeto segue padroes estritos de qualidade de codigo:
- Formatacao e linting com [Ruff](https://docs.astral.sh/ruff/) (regras PEP 8, isort, modernizacoes de sintaxe e complexidade).
- Tipagem estatica estrita em 100% das assinaturas publicas.
- Testes automatizados com `pytest` (28 testes de unidade e integracao cobrindo autenticacao, repositorios, filas concorrentes com `SKIP LOCKED` e rotas HTMX).
- Hooks de pre-commit para assegurar conformidade antes de cada commit.

Para rodar os testes e ferramentas de qualidade:

```bash
# Executa todos os testes automatizados
uv run pytest

# Executa o linter Ruff
uv run ruff check .

# Verifica formatacao de codigo
uv run ruff format --check .

# Executa todos os hooks do pre-commit
uv run pre-commit run --all-files
```

---

## Logica de Extracao do CNIS

Os extratos previdenciarios oficiais emitidos pelo INSS possuem formatos heterogeneos com multiplos blocos: cabecalho com identificacao do segurado, relacao de vinculos empregaticios (com CNPJ, razao social e datas de admissao/demissao) e demonstrativo mensal de remuneracoes.

A rotina de extracao implementada em `app/core/parser.py` segue as seguintes etapas:

1. **Abertura e Streaming do PDF:**
   O arquivo e aberto via `pdfplumber.open(caminho_arquivo)`, processando iterativamente cada pagina sem alocar o documento inteiro em memoria de forma redundante.

2. **Extracao Textual:**
   Como os extratos do INSS nao utilizam tabelas com bordas padronizadas em todas as versoes, a extracao utiliza `pagina.extract_text()`, que reconstroi o fluxo das linhas mantendo o alinhamento visual dos caracteres.

3. **Filtro de Competencias Previdenciarias:**
   As linhas extraidas sao submetidas a uma funcao de validacao de padrao temporal:
   - Uma competencia valida possui obrigatoriamente o formato `MM/AAAA` (7 caracteres, com barra divisoria no indice 2).
   - O primeiro token da linha deve satisfazer essa condicao.
   - A linha deve conter no minimo 4 colunas separadas por espaco (competencia, tipo de vinculo, indicador e valor da remuneracao).

4. **Validacao com Pydantic:**
   Os dados validados sao instanciados no schema `CnisCompetencia`, que normaliza o salario de contribuicao no formato decimal monetario brasileiro (`float`).

5. **Persistencia e Auditoria:**
   As competencias sao gravadas na tabela `contribuicoes` vinculadas ao cliente e ao job de extracao, com auditoria correspondente na tabela `extractions_logs`.

---

## Seguranca e Conformidade LGPD

O ParseApp lida com dados pessoais e dados de historico trabalhista/previdenciario de alto impacto (CPF, remuneracoes, periodos de saude/auxilio). Para resguardar a privacidade e estar em conformidade com o Artigo 11 da Lei 13.709/2018 (LGPD), aplicamos tres pilares fundamentais:

1. **Minimizacao e Armazenamento Efemero:**
   Os PDFs originais enviados nunca sao armazenados de forma definitiva. Eles residem temporariamente em volume efemero apenas durante os segundos necessarios para a extracao do worker, sendo excluidos de maneira irrecuperavel no bloco `finally:` de cada execucao.
2. **Isolamento de Dados Multi-Tenant:**
   Todas as consultas a clientes, competencias e logs possuem clausula de escopo atrelada ao `advogado_id` autenticado na sessao JWT. Nenhuma entidade de um escritorio e acessivel por outro inquilino.
3. **Logs Seguros sem Vazamento de Dados Pessoais:**
   Os registros tecnicos de log do sistema nunca expõem CPFs ou dados pessoais dos segurados, garantindo conformidade nos ambientes de observabilidade e auditoria.

---

## Estrutura do Repositorio

```text
parse-app/
├── alembic/                # Migracoes relacionais do PostgreSQL
├── app/
│   ├── api/                # Controladores HTTP (Auth, CNIS, Web views)
│   ├── core/               # Parser pdfplumber, seguranca JWT e schemas
│   ├── database/           # Modelos SQLAlchemy, repository e sessoes
│   ├── services/           # Worker assincrono e processamento de jobs
│   ├── web/                # Templates Jinja2 e assets estaticos (Tailwind, HTMX, imagens)
│   ├── cli.py              # Ponto de entrada para execucao via terminal
│   └── main.py             # Instancia FastAPI e ciclo de vida do servico
├── docs/                   # Documentacao tecnica aprofundada, C4 Model e ADRs
├── tests/                  # Bateria de testes unitarios e de integracao
├── docker-compose.yml      # Definicao de servicos Postgres e App
├── Dockerfile              # Imagem de producao baseada em python:3.12-slim
├── pyproject.toml          # Dependencias e configuracoes de ferramentas
└── README.md               # Este documento
```

---

## Documentacao Tecnica Complementar

Para aprofundamento na modelagem e nas decisoes de projeto, consulte o diretorio [`docs/`](file:///home/thales/projetos/parse-app/docs/):
- [Indice Geral da Documentacao](docs/README.md)
- [Diagramas C4 Nivel 1 e Nivel 2](docs/arquitetura/c4-model.md)
- [ADR 001 - Isolamento de Dados Multi-Tenancy](docs/arquitetura/adrs/001-multi-tenancy-isolamento.md)
- [ADR 002 - Processamento Assincrono com Fila Nativa no PostgreSQL](docs/arquitetura/adrs/002-processamento-assincrono-fila-postgres.md)
- [ADR 003 - Armazenamento Efemero e Minimizacao de Dados](docs/arquitetura/adrs/003-armazenamento-efemero.md)
- [ADR 004 - Rejeicao de Mecanismo de Auto-Atualizacao In-App para Cloud SaaS](docs/arquitetura/adrs/004-descarte-auto-update-in-app.md)
- [Mapeamento e Conformidade com a LGPD](docs/lgpd.md)
