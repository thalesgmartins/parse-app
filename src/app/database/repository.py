"""Faz o isolamento do das rotas com o banco."""

from app.core.schemas import CnisCompetencia
from app.database.connection import get_supabase


def salvar_contribuicoes(user_id: str, lista: list[CnisCompetencia]):
    """Recebe a lista do parser e persiste no Supabase."""
    supabase = get_supabase()
