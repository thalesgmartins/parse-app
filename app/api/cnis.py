"""Rotas para processamento e extração de extratos CNIS."""

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.auth import obter_usuario_logado
from app.core.parser import extrair_dados_pdf
from app.core.schemas import CnisCompetencia
from app.database.models import Advogado
from app.database.repository import (
    criar_cliente,
    registrar_log_extracao,
    salvar_contribuicoes,
)
from app.database.session import get_db

router = APIRouter(prefix="/cnis", tags=["Processamento CNIS"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "web" / "templates")


def processar_upload_cnis(
    db: Session,
    arquivo_file,
    nome_arquivo: str,
    advogado_id: uuid.UUID | str,
    cliente_id: uuid.UUID | str | None = None,
) -> list[CnisCompetencia]:
    """Extrai os dados do PDF e persiste no banco de dados com auditoria."""
    try:
        dados = extrair_dados_pdf(arquivo_file)
        if cliente_id:
            salvar_contribuicoes(db, cliente_id, dados)

        registrar_log_extracao(
            db=db,
            advogado_id=advogado_id,
            nome_arquivo=nome_arquivo,
            status="sucesso",
        )
        return dados
    except Exception as e:
        registrar_log_extracao(
            db=db,
            advogado_id=advogado_id,
            nome_arquivo=nome_arquivo,
            status="erro",
            mensagem_erro=str(e),
        )
        raise e


@router.post("/clientes")
async def cadastrar_novo_cliente(
    nome: Annotated[str, Form()],
    usuario: Annotated[Advogado, Depends(obter_usuario_logado)],
    db: Annotated[Session, Depends(get_db)],
    cpf: Annotated[str | None, Form()] = None,
) -> RedirectResponse:
    """Cadastra um novo cliente vinculado ao advogado logado."""
    criar_cliente(db=db, advogado_id=usuario.id, nome=nome, cpf=cpf)
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/extrair")
async def extrair_documento_cnis(
    arquivo: Annotated[UploadFile, File()],
    usuario: Annotated[Advogado, Depends(obter_usuario_logado)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Extrai competências de um PDF enviado diretamente via JSON API."""
    if arquivo.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são aceitos.")

    try:
        dados = processar_upload_cnis(
            db=db,
            arquivo_file=arquivo.file,
            nome_arquivo=arquivo.filename or "arquivo.pdf",
            advogado_id=usuario.id,
        )
        return {"status": "sucesso", "nome_arquivo": arquivo.filename, "dados": dados}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar o PDF: {str(e)}") from e


@router.post("/extrair-html")
async def extrair_documento_cnis_html(
    request: Request,
    cliente_id: Annotated[str, Form()],
    arquivo: Annotated[UploadFile, File()],
    usuario: Annotated[Advogado, Depends(obter_usuario_logado)],
    db: Annotated[Session, Depends(get_db)],
):
    """Processa o PDF e retorna um fragmento HTML via HTMX para a dashboard."""
    if arquivo.content_type != "application/pdf":
        return '<div class="p-4 bg-red-100 text-red-700">Apenas arquivos PDF.</div>'

    try:
        dados = processar_upload_cnis(
            db=db,
            arquivo_file=arquivo.file,
            nome_arquivo=arquivo.filename or "arquivo.pdf",
            cliente_id=cliente_id,
            advogado_id=usuario.id,
        )

        return templates.TemplateResponse(
            request=request,
            name="tabela_resultados.html",
            context={"dados": dados},
        )
    except Exception as e:
        return f'<div class="p-4 bg-red-100 text-red-700">Erro ao processar: {str(e)}</div>'
