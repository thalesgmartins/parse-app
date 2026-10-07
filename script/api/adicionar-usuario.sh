#!/usr/bin/env bash

# Aborta imediatamente em caso de erro, variável indefinida ou falha em pipe
set -euo pipefail

# Garante a execução a partir da raiz do projeto, independentemente de onde o script foi chamado
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${PROJECT_ROOT}"

# Exibe ajuda se solicitado
if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  echo "Uso: $0 [NOME] [EMAIL] [SENHA]"
  echo ""
  echo "Cadastra um novo usuário/advogado no sistema via API (/auth/register)."
  echo ""
  echo "Argumentos posicionais (opcionais):"
  echo "  1. NOME     Nome completo do usuário (padrão: 'Thales Martins')"
  echo "  2. EMAIL    E-mail para autenticação (padrão: 'thalesdiniz30@gmail.com')"
  echo "  3. SENHA    Senha de acesso (padrão: 'arduinagem')"
  echo ""
  echo "Variáveis de ambiente opcionais:"
  echo "  API_URL             URL da API (padrão: http://localhost:8000)"
  echo "  PARSE_APP_SERVICE   Nome do serviço no docker compose (padrão: parse-app)"
  echo "  USER_NOME           Nome alternativo para uso padrão"
  echo "  USER_EMAIL          E-mail alternativo para uso padrão"
  echo "  USER_PASSWORD       Senha alternativa para uso padrão"
  echo ""
  echo "Exemplos:"
  echo "  $0"
  echo "  $0 \"Maria Souza\" \"maria@advocacia.com\" \"segredo123\""
  exit 0
fi

# Configurações padrão (podem ser sobrescritas por variáveis de ambiente ou argumentos)
API_URL="${API_URL:-http://localhost:8000}"
SERVICE_NAME="${PARSE_APP_SERVICE:-parse-app}"

NOME="${1:-${USER_NOME:-Teste da Sivla}}"
EMAIL="${2:-${USER_EMAIL:-teste@gmail.com}}"
PASSWORD="${3:-${USER_PASSWORD:-senhaforte123}}"

echo "==> Verificando dependências locais..."

# Valida se o curl está instalado
if ! command -v curl &> /dev/null; then
  echo "Erro: curl não encontrado no PATH." >&2
  exit 1
fi

echo "==> Verificando disponibilidade do serviço '${SERVICE_NAME}'..."

# Se o Docker estiver presente, verifica se o contêiner da aplicação está ativo
if command -v docker &> /dev/null; then
  if [ -z "$(docker compose ps -q "${SERVICE_NAME}" 2>/dev/null)" ]; then
    echo "Erro: O contêiner '${SERVICE_NAME}' não está ativo no Docker Compose." >&2
    echo "Suba o contêiner antes com: docker compose up -d ${SERVICE_NAME}" >&2
    exit 1
  fi
fi

# Valida se o endpoint HTTP está respondendo
if ! curl -s --head --connect-timeout 3 --max-time 5 "${API_URL}/auth/login" &> /dev/null; then
  echo "Erro: A API em '${API_URL}' não está acessível." >&2
  echo "Certifique-se de que o backend está iniciado e ouvindo na porta esperada." >&2
  exit 1
fi

echo "==> Cadastrando usuário '${NOME}' (${EMAIL})..."

# Executa o cadastro na API usando codificação URL segura para os campos
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${API_URL}/auth/register" \
  --data-urlencode "nome=${NOME}" \
  --data-urlencode "email=${EMAIL}" \
  --data-urlencode "password=${PASSWORD}")

HTTP_STATUS=$(echo "${RESPONSE}" | tail -n1)
BODY=$(echo "${RESPONSE}" | sed '$d')

# 303 See Other é o código de redirecionamento esperado em caso de sucesso
if [ "${HTTP_STATUS}" -eq 303 ] || [ "${HTTP_STATUS}" -eq 200 ] || [ "${HTTP_STATUS}" -eq 201 ]; then
  echo "Sucesso: Usuário cadastrado com êxito! (HTTP ${HTTP_STATUS})"
  echo "  Nome:  ${NOME}"
  echo "  Email: ${EMAIL}"
  exit 0
elif [ "${HTTP_STATUS}" -eq 400 ]; then
  echo "Erro: Falha no cadastro (HTTP 400)." >&2
  [ -n "${BODY}" ] && echo "Detalhes: ${BODY}" >&2
  exit 1
else
  echo "Erro: Resposta inesperada da API (HTTP ${HTTP_STATUS})." >&2
  [ -n "${BODY}" ] && echo "Detalhes: ${BODY}" >&2
  exit 1
fi
