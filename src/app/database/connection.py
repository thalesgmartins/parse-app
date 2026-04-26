"""Faz a conexão do projeto com o banco de dados."""

import os

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

_supabase: Client | None = None


def get_supabase() -> Client:
    """Retorna a instância de comunicação com o banco."""

    # Garante que haja apenas uma instância de conxão com o banco.
    global _supabase

    if _supabase is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        _supabase = create_client(url, key)

    return _supabase
