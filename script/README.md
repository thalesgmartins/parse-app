# Scripts & Utilitários de Desenvolvimento

Coleção de scripts para automação de ambiente, provisionamento de dependências e tarefas de debug.

---

## Pré-requisitos e Permissões

Antes de executar qualquer script pela primeira vez, garanta que os arquivos tenham permissão de execução:

```bash
chmod +x scripts/**/*.sh
```

Execute os comandos **a partir da raiz do projeto**.

---

## Guia de Uso separado por Tecnologia/Área

### Docker (`scripts/docker/`)

| Script | Descrição | Como Executar |
| :--- | :--- | :--- |
| `install-docker.sh` | Faz a instalação do Docker + Compose a partir do script oficial do Docker. | `sudo ./scripts/docker/install-docker.sh` |

---

### PostgreSQL (`script/postgres/`)

| Script | Descrição | Como Executar |
| :--- | :--- | :--- |
| `checar-tabelas.sh` | Conecta via `docker compose exec` e exibe as tabelas com `\dt`. | `./script/postgres/checar-tabelas.sh` |

---

### API (`script/api/`)

| Script | Descrição | Como Executar |
| :--- | :--- | :--- |
| `adicionar-usuario.sh` | Cadastra um usuário/advogado via endpoint `/auth/register` com validações. | `./script/api/adicionar-usuario.sh [NOME] [EMAIL] [SENHA]` |

---

### Geração de CNIS Sintético (`script/gerar_cnis_ficticio.py`)

Gera um arquivo PDF de extrato CNIS com layout 100% idêntico ao modelo oficial do INSS/Gov.br, porém com dados fictícios (nome, CPF, empresas e evolução salarial). Ideal para apresentações e demonstrações sem expor dados reais sob a LGPD.

```bash
# Geração padrão (2015 a 2026, 140 competências, 4 páginas):
uv run python script/gerar_cnis_ficticio.py --saida extrato_apresentacao.pdf

# Geração personalizada:
uv run python script/gerar_cnis_ficticio.py \
  --nome "CARLOS EDUARDO SILVA SANTOS" \
  --inicio 2010 \
  --fim 2026 \
  --salario 2200.0 \
  --saida extrato_custom.pdf
```
