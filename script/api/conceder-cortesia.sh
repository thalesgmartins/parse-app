#!/usr/bin/env bash

# Aborta imediatamente em caso de erro, variável indefinida ou falha em pipe
set -euo pipefail

# Garante a execução a partir da raiz do projeto, independentemente de onde foi chamado
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${PROJECT_ROOT}"

# Exibe ajuda se solicitado
if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  echo "Uso: $0 [EMAIL] [LIMITE_MENSAL] [TIER]"
  echo ""
  echo "Concede plano de cortesia / teste (sem cobrança no Asaas e sem expiração de ciclo)"
  echo "para um advogado já cadastrado no sistema."
  echo ""
  echo "Argumentos posicionais (opcionais):"
  echo "  1. EMAIL           E-mail da conta (obrigatório ou via USER_EMAIL)"
  echo "  2. LIMITE_MENSAL   Quantidade de extratos/mês (padrão: 99999)"
  echo "  3. TIER            Código do plano (padrão: 'grande_escritorio')"
  echo ""
  echo "Exemplos:"
  echo "  $0 pai@gmail.com"
  echo "  $0 pai@gmail.com 500"
  echo "  $0 teste@escritorio.com 1000 pequeno_escritorio"
  exit 0
fi

EMAIL="${1:-${USER_EMAIL:-}}"
LIMITE="${2:-99999}"
TIER="${3:-grande_escritorio}"

if [ -z "${EMAIL}" ]; then
  echo "Erro: Informe o e-mail do advogado." >&2
  echo "Exemplo: $0 email_do_pai@gmail.com" >&2
  exit 1
fi

PYTHON_CODE="
import sys
from app.database.session import SessionLocal
from app.database.repository import obter_advogado_por_email
from app.services.quotas import CATALOGO_PLANOS, garantir_assinatura_advogado

email = sys.argv[1].strip()
limite = int(sys.argv[2])
tier = sys.argv[3].strip()

db = SessionLocal()
adv = obter_advogado_por_email(db, email)
if not adv:
    print(f'Erro: Advogado com e-mail \"{email}\" não foi encontrado no banco de dados.')
    print('Dica: Peça para o usuário acessar o sistema uma vez com o Google para criar a conta.')
    sys.exit(1)

sub = garantir_assinatura_advogado(db, adv.id)
sub.tier = tier if tier in CATALOGO_PLANOS else 'grande_escritorio'
sub.limite_mensal = limite
sub.status = 'active'
sub.ciclo_fim = None
sub.asaas_subscription_id = None
sub.checkout_url = None
db.commit()

print(f'Sucesso: Plano de cortesia concedido para {adv.nome} ({adv.email})!')
print(f'  Plano atribuído: {sub.tier}')
print(f'  Limite mensal:   {sub.limite_mensal} extratos')
print('  Ciclo:           Vitalício / Sem expiração mensal')
print('  Cobrança Asaas:  Isento (R$ 0,00)')
"

echo "==> Concedendo plano de cortesia para '${EMAIL}'..."

# 1. Se estiver rodando dentro do servidor com docker compose ou container parse-app
if command -v docker &> /dev/null && [ -n "$(docker ps -q -f name=parse-app 2>/dev/null)" ]; then
  docker exec -i parse-app python -c "${PYTHON_CODE}" "${EMAIL}" "${LIMITE}" "${TIER}"
  exit 0
fi

# 2. Se docker compose estiver disponível no diretório
if command -v docker &> /dev/null && [ -n "$(docker compose ps -q parse-app 2>/dev/null || true)" ]; then
  docker compose exec -T parse-app python -c "${PYTHON_CODE}" "${EMAIL}" "${LIMITE}" "${TIER}"
  exit 0
fi

# 3. Fallback: ambiente local com virtualenv
if [ -f ".venv/bin/python" ]; then
  .venv/bin/python -c "${PYTHON_CODE}" "${EMAIL}" "${LIMITE}" "${TIER}"
  exit 0
elif command -v python3 &> /dev/null; then
  python3 -c "${PYTHON_CODE}" "${EMAIL}" "${LIMITE}" "${TIER}"
  exit 0
else
  echo "Erro: Não foi possível localizar o container 'parse-app' nem o interpretador Python local." >&2
  exit 1
fi
