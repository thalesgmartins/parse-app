"""Faz a conexão com o banco de dados"""
import os

from dotenv import load_dotenv
from supabase import create_client

# Carrega as variáveis do arquivo .env
load_dotenv()

# Cria a sessão global do supabase
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)