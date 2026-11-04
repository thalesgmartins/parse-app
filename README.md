# ParseApp - Plataforma SaaS para Extração de Extratos CNIS

[![Versão](https://img.shields.io/badge/vers%C3%A3o-0.12.0-blue.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](pyproject.toml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20Multi--Tenant-336791.svg)](https://www.postgresql.org/)
[![Testes](https://img.shields.io/badge/testes-87%20passed-success.svg)](tests/)

O **ParseApp** é uma solução SaaS B2B moderna projetada especificamente para escritórios de advocacia previdenciária. A plataforma automatiza ponta a ponta a ingestão, o parsing inteligente, a identificação automática do segurado e a consolidação de dados de extratos previdenciários (**CNIS** - Cadastro Nacional de Informações Sociais) emitidos em formato PDF pelo portal Meu INSS / Gov.br.

A ferramenta elimina o trabalho braçal de digitação manual de salários e vínculos, reduz gargalos operacionais e viabiliza a geração ágil de cálculos previdenciários (RMI, revisões da vida toda e liquidação de sentença), contando com isolamento de dados por **Schema PostgreSQL (Schema-per-Tenant)**, gestão de assinaturas via **Asaas**, autenticação **Google OAuth 2.0**, interface nativa em **Modo Escuro com responsividade mobile** e estrita conformidade com a Lei Geral de Proteção de Dados (Lei 13.709/2018 - **LGPD**).

---

## Índice

- [Visão Geral do Produto](#visão-geral-do-produto)
- [Arquitetura da Solução](#arquitetura-da-solução)
  - [Isolamento Multi-Tenant por Schema](#isolamento-multi-tenant-por-schema)
  - [Fluxo de Processamento Assíncrono](#fluxo-de-processamento-assíncrono)
- [Principais Funcionalidades](#principais-funcionalidades)
- [Stack Tecnológico](#stack-tecnológico)
- [Como Executar o Projeto](#como-executar-o-projeto)
  - [Opção 1: Docker Compose (Recomendado)](#opção-1-docker-compose-recomendado)
  - [Opção 2: Desenvolvimento Local com uv](#opção-2-desenvolvimento-local-com-uv)
  - [Modo CLI (Linha de Comando)](#modo-cli-linha-de-comando)
  - [Utilitários e Scripts de Automação](#utilitários-e-scripts-de-automação)
- [Qualidade de Código e Testes](#qualidade-de-código-e-testes)
- [Lógica de Extração do CNIS](#lógica-de-extração-do-cnis)
- [Monetização, Planos e Quotas](#monetização-planos-e-quotas)
- [Segurança e Conformidade LGPD](#segurança-e-conformidade-lgpd)
- [Estrutura do Repositório](#estrutura-do-repositório)
- [Histórico Recente de Versões](#histórico-recente-de-versões)
- [Documentação Técnica Complementar](#documentação-técnica-complementar)

---

## Visão Geral do Produto

Escritórios de advocacia previdenciária frequentemente despendem horas digitando manualmente históricos de vínculos, períodos trabalhados e remunerações contidas em extratos CNIS de dezenas de páginas. Esse processo manual atrasa a entrega de pareceres jurídicos e introduz riscos severos de erros materiais em petições iniciais e recursos perante o INSS ou o Poder Judiciário.

O ParseApp resolve esse problema através de um fluxo inteligente e sem atrito:
1. **Cadastro e Onboarding Instantâneo:** O advogado cria sua conta nativa ou via **Google OAuth 2.0** com provisionamento automático de schema isolado e plano de degustação (*Trial*).
2. **Upload Direto com Identificação Automática:** O advogado faz o upload do PDF oficial do CNIS via dropzone na interface web; o sistema identifica automaticamente o segurado (Nome e CPF) direto do cabeçalho do documento, sem necessidade de cadastro manual prévio de clientes.
3. **Fila Assíncrona Resiliente:** O arquivo é enfileirado no PostgreSQL (`FOR UPDATE SKIP LOCKED`) e processado em segundo plano sem travar a interface.
4. **Deduplicação e Consolidação:** Uploads parciais ou complementares do mesmo segurado são consolidados e deduplicados automaticamente em ordem cronológica estrita.
5. **Dashboard, Análise e Exportação:** Em segundos, as competências, gráficos de evolução salarial e KPIs previdenciários são apresentados via HTMX, prontos para exportação em formato CSV.

---

## Arquitetura da Solução

### Isolamento Multi-Tenant por Schema

A plataforma implementa isolamento rigoroso por **Schema PostgreSQL** (`tenant_{advogado_id}`), superando abordagens simples baseadas em colunas compartilhadas:

- **Schema `public` (Compartilhado):** Armazena dados globais de infraestrutura e faturamento: advogados autenticados, catálogo de planos, assinaturas e histórico de webhooks Asaas.
- **Schemas `tenant_{id}` (Dedicados por Escritório):** Cada advogado/escritório opera em seu próprio namespace físico com tabelas isoladas de `clientes`, `contribuicoes`, `extraction_jobs` e `extractions_logs`.
- **Garantia de Não-Vazamento:** O `search_path` é injetado dinamicamente no ciclo de vida da requisição/sessão SQLAlchemy, viabilizando expurgo facilitado (`DROP SCHEMA`) e total conformidade com a LGPD.

```mermaid
flowchart TD
    subgraph PublicSchema ["PostgreSQL: Schema public (Global)"]
        ADV[advogados]
        PLN[planos]
        SUB[assinaturas_asaas]
        PAG[pagamentos_asaas]
    end

    subgraph TenantA ["PostgreSQL: Schema tenant_1"]
        CLI_A[clientes]
        CON_A[contribuicoes]
        JOB_A[extraction_jobs]
        LOG_A[extractions_logs]
    end

    subgraph TenantB ["PostgreSQL: Schema tenant_2"]
        CLI_B[clientes]
        CON_B[contribuicoes]
        JOB_B[extraction_jobs]
        LOG_B[extractions_logs]
    end

    ADV -->|Provisiona| TenantA
    ADV -->|Provisiona| TenantB
```

### Fluxo de Processamento Assíncrono

```mermaid
flowchart LR
    subgraph Cliente ["Navegador (Dark Mode)"]
        direction TB
        A[Advogado] -->|Upload PDF / Drag-and-Drop| B[Formulário HTMX]
        B -->|Polling 1s| C[Poller HTMX]
        C -->|Renderiza| D[Tabela & Análise Consolidada]
    end

    subgraph API ["FastAPI HTTP Layer"]
        direction TB
        E[Endpoint Ingestão] -->|Validação Fail-Fast| V{Cabeçalho CNIS?}
        V -->|Não| R[Rejeita sem debitar quota]
        V -->|Sim| F["Grava temporário /tmp/uploads"]
        F --> G[(PostgreSQL extraction_jobs)]
        E -->|Dispara tarefa| H[Task Runner]
    end

    subgraph Worker ["Worker Assíncrono"]
        direction TB
        I[Worker Loop] -->|SKIP LOCKED| G
        I -->|Lê stream| F
        I -->|pdfplumber & parser| J[(PostgreSQL tenant.contribuicoes)]
        I -->|Identifica/Cria cliente| K[(PostgreSQL tenant.clientes)]
        I -->|Auditoria| L[(PostgreSQL tenant.extractions_logs)]
        I -->|Finally: os.unlink| M[Exclusão Segura do PDF]
    end

    B -->|Multipart| E
    H -.->|Aciona| I
    C -.->|Consulta status| G
```

---

## Principais Funcionalidades

- **Identificação Automática do Segurado:** Extração automática de Nome e CPF a partir do cabeçalho oficial do CNIS, resolvendo e cadastrando o cliente automaticamente sem etapas manuais.
- **Consolidação e Deduplicação Inteligente:** Mecanismo de *upsert* transacional idempotente que unifica extratos sobrepostos do mesmo segurado em ordem cronológica ascendente.
- **Autenticação Híbrida (Google OAuth 2.0 + JWT):** Login com um clique via conta Google ou credenciais e-mail/senha com hash bcrypt.
- **Gestão de Faturamento & Assinaturas Asaas:** 3 tiers de planos (Gratuito, Básico e Profissional), quotas atômicas mensais de extração, checkout transparente e proteção contra cobrança duplicada.
- **Cancelamento Self-Service Resiliente:** Cancelamento de assinaturas preservando os benefícios e o consumo de quotas até o encerramento do ciclo mensal vigente.
- **Interface Dark Mode & Responsividade Mobile Completa:** Design moderno com foco em ergonomia visual para operadores jurídicos, sidebar retrátil com gaveta móvel, dropzone touch e tabelas adaptáveis.
- **Módulo de Análise Previdenciária (`/analise`):** Painel interativo com KPIs de tempo contributivo, remuneração média, períodos de auxílio e curva gráfica de remunerações ao longo do tempo.
- **Exportação Flexível:** Download completo do histórico do segurado em formato CSV formatado para o padrão contábil/monetário brasileiro.
- **Gerador de CNIS Sintético:** Utilitário baseado em ReportLab para geração de extratos CNIS fidedignos com dados fictícios para fins de testes, auditoria e demonstrações.

---

## Stack Tecnológico

- **Linguagem & Runtime:** Python 3.12 (compatível com 3.10+)
- **Framework Web:** [FastAPI](https://fastapi.tiangolo.com/) com Starlette
- **Camada de Dados & ORM:** [SQLAlchemy 2.0](https://www.sqlalchemy.org/) (Mapped columns, tipagem estrita)
- **Migrações de Banco:** [Alembic](https://alembic.sqlalchemy.org/) (suporte a multi-schema e isolamento dinâmico)
- **Banco de Dados:** [PostgreSQL 16](https://www.postgresql.org/) (driver `psycopg 3` binário com pooling)
- **Motor de Extração de PDF:** [pdfplumber](https://github.com/jsvine/pdfplumber) com suporte a layouts multicolor e tabelas do INSS
- **Gerador de Documentos Sintéticos:** [ReportLab](https://www.reportlab.com/)
- **Frontend & Reatividade:** HTML5 semântico, [HTMX](https://htmx.org/) (local offline) e Jinja2
- **Estilização & Ícones:** [Tailwind CSS](https://tailwindcss.com/) com paleta corporativa Dark Mode compilada localmente e [Material Design Icons](https://materialdesignicons.com/) (MDI webfont offline)
- **Autenticação:** Google OAuth 2.0 + JWT (PyJWT) e senhas com hash bcrypt
- **Proteção & Rate Limiting:** [slowapi](https://github.com/laurents/slowapi) com suporte a headers de proxy reverso (`CF-Connecting-IP`, `X-Forwarded-For`)
- **Gateway de Pagamentos:** [Asaas API v3](https://docs.asaas.com/) (Cobranças via Cartão, PIX e Boleto)
- **Gerenciador de Pacotes:** [uv](https://docs.astral.sh/uv/) (Astral)
- **Infraestrutura:** Docker e Docker Compose com persistência de volumes efêmeros
- **CI/CD:** GitHub Actions com Release Please para versionamento semântico automatizado

---

## Como Executar o Projeto

### Opção 1: Docker Compose (Recomendado)

O Docker Compose orquestra a aplicação e o PostgreSQL em contêineres com *healthchecks* e volumes persistidos:

1. Clone o repositório:
   ```bash
   git clone https://github.com/thalesgmartins/parse-app.git
   cd parse-app
   ```

2. Crie o arquivo `.env` a partir do modelo:
   ```bash
   cp .env.example .env
   ```

3. Inicie os serviços com build:
   ```bash
   docker compose up -d --build
   ```

4. Acesse a aplicação no navegador:
   - **Dashboard:** [http://localhost:8000/dashboard](http://localhost:8000/dashboard)
   - **Análise Previdenciária:** [http://localhost:8000/analise](http://localhost:8000/analise)
   - **Login:** [http://localhost:8000/login](http://localhost:8000/login)
   - **Documentação OpenAPI:** [http://localhost:8000/docs](http://localhost:8000/docs)

Para acompanhar os logs de execução:
```bash
docker compose logs -f parse-app
```

---

### Opção 2: Desenvolvimento Local com uv

Para rodar fora do Docker utilizando o gerenciador de pacotes ultrarrápido `uv`:

1. Instale o `uv` (caso ainda não possua):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Sincronize as dependências do projeto e o ambiente virtual:
   ```bash
   uv sync --extra dev
   ```

3. Suba o banco de dados PostgreSQL via Docker:
   ```bash
   docker compose up -d postgres
   ```

4. Aplique as migrações do banco de dados com o Alembic:
   ```bash
   DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/parseapp uv run alembic upgrade head
   ```

5. Inicie o servidor FastAPI em modo de recarregamento automático (*hot-reload*):
   ```bash
   DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/parseapp uv run uvicorn app.main:app --reload --port 8000
   ```

---

### Modo CLI (Linha de Comando)

Para extrair informações de um extrato CNIS diretamente pelo terminal sem subir a interface web:

```bash
uv run python3 -m app.cli --path "caminho/para/extrato.pdf"
```

O comando executará o parser em modo texto pesquisável e imprimirá a lista estruturada das competências e remunerações identificadas.

---

### Utilitários e Scripts de Automação

O diretório [`script/`](file:///home/thales/projetos/pessoal/parse-app/script/) oferece ferramentas para automação de tarefas administrativas e desenvolvimento:

- **Geração de CNIS Sintético:** Cria PDFs com layout 100% idêntico ao INSS para testes e homologação sem infringir a LGPD:
  ```bash
  uv run python script/gerar_cnis_ficticio.py --saida extrato_demo.pdf
  ```
- **Concessão de Cortesia:** Concede planos e cotas customizadas sem integração financeira com Asaas:
  ```bash
  ./script/api/conceder-cortesia.sh usuario@escritorio.com.br 100 profissional
  ```
- **Criação de Usuário:** Provisiona um novo advogado via API:
  ```bash
  ./script/api/adicionar-usuario.sh "Dr. Nome" "advogado@escritorio.com.br" "SenhaForte123"
  ```

Consulte o [Manual de Scripts](script/README.md) para documentação completa de cada comando.

---

## Qualidade de Código e Testes

O projeto segue padrões estritos de engenharia de software e testes contínuos:
- **87 testes automatizados** com Pytest e pytest-asyncio cobrindo isolamento multi-tenant por schema, quotas atômicas, webhooks do Asaas, autenticação Google OAuth, rate limiting, gerador sintético e rotas HTMX.
- Formatação e linting com [Ruff](https://docs.astral.sh/ruff/) (regras PEP 8, isort, modernizações de sintaxe e complexidade).
- Tipagem estática com tipagem estrita em modelos, serviços e rotas públicas.
- Hooks de pre-commit para validação antes de cada commit.

Para rodar a suíte completa de testes e ferramentas de qualidade:

```bash
# Executa todos os 87 testes automatizados
uv run pytest

# Executa o linter Ruff
uv run ruff check .

# Verifica a formatação do código
uv run ruff format --check .

# Executa todos os hooks do pre-commit
uv run pre-commit run --all-files
```

---

## Lógica de Extração do CNIS

Os extratos do INSS possuem formatos heterogêneos e múltiplos blocos: cabeçalho com identificação do segurado, relação de vínculos empregatícios (com CNPJ, razão social e datas de admissão/demissão) e demonstrativo mensal de remunerações em colunas simples ou paralelas.

A rotina de extração implementada em `app/core/parser.py` segue as seguintes etapas:

1. **Abertura e Streaming Efêmero:**
   O arquivo é aberto via `pdfplumber.open(caminho_arquivo)`, processando iterativamente cada página sem carregar o arquivo inteiro na memória RAM de forma redundante.

2. **Identificação Automática do Segurado (Fail-Fast):**
   O parser inspeciona as primeiras páginas em busca do bloco de cabeçalho padrão INSS, extraindo Nome Completo, CPF e NIT do segurado (`extract_dados_segurado_cabecalho`). Se o documento não for um CNIS válido, o job falha rapidamente antes de consumir qualquer quota do plano do usuário.

3. **Extração Textual & Suporte a Múltiplas Colunas:**
   A extração utiliza `pagina.extract_text()`, tratando layouts em que o INSS posiciona até 3 competências na mesma linha horizontal divididas em colunas de remuneração.

4. **Filtro Temporal de Competências Previdenciárias:**
   As linhas e tokens extraídos passam por validação estrita de padrão temporal `MM/AAAA` (7 caracteres, barra divisória no índice 2), normalizando indicadores (ex: `PREV-FACULT`, `IREC-FBR`, `IEAN`) e salários em valores numéricos (`float`).

5. **Consolidação e Deduplicação Idempotente:**
   As competências são salvas no banco do tenant por meio de rotinas de *upsert* com chave de unicidade `(cliente_id, competencia)`. Uploads repetidos ou extratos de datas diferentes são unificados sem duplicidade e ordenados cronologicamente.

6. **Auditoria e Limpeza:**
   Os logs são gravados em `extractions_logs` e o arquivo PDF é imediatamente removido do disco no bloco `finally:` da execução.

---

## Monetização, Planos e Quotas

O ParseApp conta com um motor completo de cobrança e governança de consumo integrado ao **Asaas**:

- **Tiers de Assinatura:**
  - **Degustação / Trial:** Concedido automaticamente no cadastro para novos escritórios testarem a ferramenta.
  - **Básico:** Destinado a profissionais autônomos com volume mensal moderado.
  - **Profissional:** Destinado a escritórios consolidados com alto volume de processamento de clientes.
- **Quotas Atômicas:** Cada extração confirmada consome 1 crédito mensal de forma transacional. Se o arquivo estiver corrompido ou não contiver competências válidas, a quota é estornada automaticamente.
- **Proteção contra Duplicações e Webhooks Idempotentes:** O sistema deduplica pagamentos e processa com segurança os eventos `PAYMENT_CONFIRMED` e `PAYMENT_RECEIVED` do Asaas.
- **Cancelamento com Preservação de Benefícios:** O cancelamento de assinaturas pode ser acionado self-service diretamente no modal da aplicação; o status é mantido ativo até a data limite da mensalidade já liquidada.

---

## Segurança e Conformidade LGPD

O ParseApp lida com dados sensíveis e histórico contributivo de alto impacto (CPF, NIT, remunerações e períodos de afastamento por saúde/auxílio-doença). Para resguardar a privacidade e cumprir a Lei 13.709/2018 (LGPD), aplicamos pilares estritos de proteção:

1. **Minimização e Armazenamento Efêmero (Art. 6º, III):**
   Os arquivos PDF enviados nunca são armazenados de forma permanente. Ficam salvos em volume efêmero apenas durante o tempo de execução do worker (segundos) e são destruídos no bloco `finally:`.
2. **Isolamento por Schema PostgreSQL (Schema-per-Tenant):**
   Cada escritório possui seu próprio schema de banco (`tenant_{id}`). O isolamento ocorre em nível de banco de dados, impedindo qualquer acesso cruzado entre clientes de escritórios distintos.
3. **Rate Limiting e Proteção de Perímetro:**
   Controle de abuso e ataques de força bruta via `slowapi` nas rotas de autenticação e upload, com identificação real de cliente via headers Cloudflare (`CF-Connecting-IP`).
4. **Logs Seguros e Anonimização:**
   Registros técnicos de observabilidade e logs de aplicação não registram senhas, tokens ou dados pessoais sensíveis dos segurados.
5. **Base Legal Adequada (Art. 11, II, "d"):**
   O tratamento de dados previdenciários e de saúde (como códigos B31/B91 no CNIS) é fundamentado no exercício regular de direitos em processos judiciais e administrativos.

---

## Estrutura do Repositório

```text
parse-app/
├── alembic/                      # Migrações relacionais (suporte multi-tenant)
│   └── versions/                 # Scripts de migração de schema e dados
├── app/
│   ├── api/                      # Controladores HTTP FastAPI
│   │   ├── auth.py               # Autenticação JWT e Google OAuth 2.0
│   │   ├── billing.py            # Planos, checkout e webhooks Asaas
│   │   ├── cnis.py               # Endpoints REST e HTMX de extração
│   │   └── web.py                # Visualizações HTML (Dashboard, Análise, Perfil)
│   ├── core/                     # Motor central e infraestrutura
│   │   ├── config.py             # Configurações com Pydantic Settings
│   │   ├── limiter.py            # Rate limiting com SlowAPI
│   │   ├── parser.py             # Extrator pdfplumber e validador de CNIS
│   │   └── security.py           # Criptografia bcrypt e tokens JWT
│   ├── database/                 # Camada de persistência
│   │   ├── models.py             # Modelos declarativos SQLAlchemy 2.0
│   │   ├── repository.py         # Repositório de dados com upsert e ordenação
│   │   ├── session.py            # Gerenciamento de engine e sessions
│   │   └── tenancy.py            # Provisionamento e search_path de schemas
│   ├── services/                 # Serviços de domínio e workers assíncronos
│   │   ├── analytics.py          # KPIs previdenciários e curva de remunerações
│   │   ├── asaas.py              # Integração cliente Asaas v3
│   │   ├── cnis_generator.py     # Gerador sintético de CNIS via ReportLab
│   │   ├── quotas.py             # Governança e débito atômico de quotas
│   │   └── worker.py             # Worker de fila com SKIP LOCKED e limpeza
│   ├── web/                      # Camada de apresentação
│   │   ├── static/               # CSS Tailwind, Material Design Icons e fontes
│   │   └── templates/            # Templates Jinja2 (Dashboard, Analise, Login)
│   ├── cli.py                    # Interface de linha de comando para parsing
│   └── main.py                   # Ponto de entrada FastAPI e middlewares
├── docs/                         # Documentação de arquitetura, C4 Model e ADRs
├── script/                       # Scripts utilitários de infraestrutura e API
│   ├── api/                      # Shell scripts para cortesia e usuários
│   ├── docker/                   # Automação de Docker
│   ├── postgres/                 # Verificação de banco e tabelas
│   └── gerar_cnis_ficticio.py    # Gerador CLI de extratos para demonstração
├── tests/                        # 87 testes automatizados (unitários, integração e E2E)
├── docker-compose.yml            # Orquestração do app e do PostgreSQL
├── Dockerfile                    # Imagem de produção otimizada (python:3.12-slim)
├── pyproject.toml                # Dependências do projeto e configurações de ferramentas
└── README.md                     # Este documento
```

---

## Histórico Recente de Versões

As principais evoluções incorporadas ao ParseApp nas últimas versões incluem:

- **v0.12.0:**
  - Cancelamento *self-service* de assinaturas preservando o acesso e a quota até o fim do ciclo mensal vigente.
  - Script administrativo de concessão de plano cortesia (`conceder-cortesia.sh`).
  - Proteção financeira contra cobrança duplicada no Asaas e tratamento de expiração de ciclos.
  - Responsividade mobile completa em todas as telas com sidebar retrátil com gaveta e cache-busting.
- **v0.11.0:**
  - Otimização do modal de planos e deduplicação de clientes no Asaas com validação unificada de CPF/CNPJ.
  - Priorização de login via Google OAuth 2.0 na interface.
- **v0.10.0:**
  - Arquitetura multi-tenant por Schema PostgreSQL (`tenant_{advogado_id}`).
  - Integração oficial com a API v3 do gateway de pagamentos Asaas.
  - 3 Tiers de planos com governança atômica de quotas mensais e *fail-fast* de cabeçalho CNIS.
  - Autenticação Google OAuth 2.0 com provisionamento instantâneo de conta e schema.
  - Migração de ícones visuais para Material Design Icons (MDI).
- **v0.9.0:**
  - Reestruturação completa do frontend para Dark Mode nativo com foco no conforto visual dos usuários.
  - Nova tela de Análise Previdenciária (`/analise`) com indicadores analíticos e gráfico de evolução das remunerações.
- **v0.8.0:**
  - Rate limiting com SlowAPI em rotas sensíveis com suporte a proxies reversos/Cloudflare.
  - Limite configurável de tamanho de arquivos com streaming seguro.
  - Persistência do volume de uploads temporários via Docker Compose.
- **v0.7.0:**
  - Identificação automática do segurado (Nome e CPF) direto do cabeçalho do CNIS, dispensando cadastro prévio.
  - Deduplicação inteligente de competências por cliente e ordenação cronológica estrita.
  - Exportação consolidada de históricos em formato CSV.
- **v0.6.0:**
  - Suporte a extração de competências dispostas em múltiplas colunas no extrato do INSS.
  - Histórico persistido de jobs de extração por advogado.

Para o registro detalhado de cada commit e PR, consulte o arquivo [CHANGELOG.md](CHANGELOG.md).

---

## Documentação Técnica Complementar

Para aprofundamento nas decisões de arquitetura e conformidade, consulte os documentos no diretório [`docs/`](docs/):
- [Índice Geral da Documentação](docs/README.md)
- [Diagramas C4 Nível 1 e Nível 2](docs/arquitetura/c4-model.md)
- [ADR 001 - Isolamento de Dados Multi-Tenancy por Schema](docs/arquitetura/adrs/001-multi-tenancy-isolamento.md)
- [ADR 002 - Processamento Assíncrono com Fila Nativa no PostgreSQL](docs/arquitetura/adrs/002-processamento-assincrono-fila-postgres.md)
- [ADR 003 - Armazenamento Efêmero e Minimização de Dados](docs/arquitetura/adrs/003-armazenamento-efemero.md)
- [ADR 004 - Rejeição de Mecanismo de Auto-Atualização In-App para Cloud SaaS](docs/arquitetura/adrs/004-descarte-auto-update-in-app.md)
- [Mapeamento e Conformidade com a LGPD](docs/lgpd.md)
