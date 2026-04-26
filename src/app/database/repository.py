"""Faz o isolamento do das rotas com o banco."""

from app.core.schemas import CnisCompetencia
from app.database.connection import get_supabase


def criar_cliente(advogado_id: str, nome: str, cpf: str | None = None):
    """Cadastra um novo cliente para o advogado logado."""
    supabase = get_supabase()

    res = supabase.table("clientes").insert({"advogado_id": advogado_id, "nome": nome, "cpf": cpf}).execute()
    return res.data[0]


def listar_clientes(advogado_id: str):
    """Busca todos os clientes de um advogado para preencher o HTML."""
    supabase = get_supabase()

    res = supabase.table("clientes").select("*").eq("advogado_id", advogado_id).order("nome").execute()
    return res.data


def salvar_contribuicoes(cliente_id: str, lista: list[CnisCompetencia]):
    """Salva os dados vinculados ao ID do CLIENTE."""
    supabase = get_supabase()

    dados_para_banco = [
        {
            "cliente_id": cliente_id,
            "data_competencia": c.data_competencia,
            "valor": c.valor,
        }
        for c in lista
    ]
    response = supabase.table("cnis_contribuicoes").insert(dados_para_banco).execute()
    return response.data
