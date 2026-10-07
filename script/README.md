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

### PostgreSQL (`scripts/postgres/`)

| Script | Descrição | Como Executar |
| :--- | :--- | :--- |
| `checar-tabelas.sh` | Conecta via `docker compose exec` e exibe as tabelas com `\dt`. | `./scripts/postgres/checar-tabelas.sh` |
