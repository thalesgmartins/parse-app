"""Configurações globais de teste para o ParseApp."""

import os

# Define flag para desativar execuções de rede/migrations durante testes unitários
os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
