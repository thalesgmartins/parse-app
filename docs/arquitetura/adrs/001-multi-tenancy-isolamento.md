# ADR 001: Isolamento de Dados e Estrategia de Multi-Tenancy

## Status
Aprovado

## Data
2026-10-06 (Formalizado no Checkpoint 1)

## Contexto
O ParseApp atende escritorios de advocacia previdenciaria independentes e sociedades de advogados com base em um modelo B2B SaaS. Cada escritorio gerencia dezenas a centenas de clientes titulares de beneficios previdenciarios, com historicos salariais e dados pessoais altamente sensiveis.

Era necessario definir a estrategia de arquitetura para acomodar multiplos inquilinos (*tenants*) no banco de dados, equilibrando:
1. Seguranca e isolamento estrito entre escritorios (garantindo 0% de vazamento de dados).
2. Custo de infraestrutura em estagio inicial de produto.
3. Complexidade operacional para manutencao, backups e aplicacao de migracoes de esquema (Alembic).

## Decisao
Adotamos o **Modelo Pool (Banco Compartilhado com Isolamento Logico)** utilizando o PostgreSQL 16:
- Todas as entidades da aplicacao (`clientes`, `contribuicoes`, `extractions_logs`, `extraction_jobs`) estao direta ou indiretamente vinculadas a chave estrangeira `advogado_id`.
- A camada de servico e de repositorio filtra obrigatoriamente todas as consultas e mutacoes pelo identificador do advogado autenticado na sessao JWT (`usuario.id`).
- No banco de dados, indices sao mantidos em todas as chaves estrangeiras (`ix_clientes_advogado_id`, `ix_extractions_logs_advogado_id`, `ix_extraction_jobs_advogado_id`) e regras de exclusao em cascata (`ON DELETE CASCADE`) garantem a consistencia relacional.
- Como evolucao futura prevista, politicas nativas de **Row-Level Security (RLS)** do PostgreSQL poderao ser ativadas no banco para impor a barreira na propria conexao SQL.

Rejeitamos o modelo Silo (um banco de dados ou schema separado por escritorio) neste estagio.

## Consequencias

### Positivas
- **Custo Operacional e de Infraestrutura Reduzido:** Uma unica instancia de banco de dados atende todos os inquilinos, viabilizando planos de entrada acessiveis.
- **Simplicidade de Deploy e Migracoes:** Migracoes de esquema com o Alembic rodam em um unico passo (`alembic upgrade head`), eliminando a necessidade de scripts de migracao em lote por banco de dados.
- **Pooling Eficiente de Conexoes:** Melhor aproveitamento do pool de conexoes do PostgreSQL (`pool_pre_ping=True`), sem exaustao de sockets TCP.

### Negativas / Riscos Mitigados
- **Risco de Erro de Escopo em Consultas:** Uma consulta relacional mal construida sem filtro por `advogado_id` poderia retornar dados de outro inquilino.
  - *Mitigacao implementada:* A camada de repositorio concentra todas as consultas, e testes de integracao automatizados (`test_get_job_retorna_404_para_outro_advogado`) verificam ativamente que recursos de terceiros retornam HTTP 404.
