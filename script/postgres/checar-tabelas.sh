#!/usr/bin/env bash

# Aborta imediatamente em caso de erro, variável indefinida ou falha em pipe
set -euo pipefail

# Garante a execução a partir da raiz do projeto, independentemente de onde o script foi chamado
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${PROJECT_ROOT}"

# Configurações padrão (podem ser sobrescritas por variáveis de ambiente)
SERVICE_NAME="${POSTGRES_SERVICE:-postgres}"
DB_USER="${POSTGRES_USER:-postgres}"
DB_NAME="${POSTGRES_DB:-parseapp}"

echo "==> Verificando status do serviço '${SERVICE_NAME}'..."

# Valida se o docker compose está instalado
if ! command -v docker &> /dev/null; then
  echo "Erro: Docker não encontrado no PATH." >&2
  exit 1
fi

# Valida se o contêiner do serviço está rodando
if [ -z "$(docker compose ps -q "${SERVICE_NAME}" 2>/dev/null)" ]; then
  echo "Erro: O serviço '${SERVICE_NAME}' não está ativo." >&2
  echo "Suba o container antes com: docker compose up -d ${SERVICE_NAME}" >&2
  exit 1
fi

echo "==> Listando tabelas do banco '${DB_NAME}' (usuário: ${DB_USER})..."
echo ""

# Executa o comando psql dentro do contêiner
docker compose exec "${SERVICE_NAME}" psql -U "${DB_USER}" -d "${DB_NAME}" -c "\dt"
