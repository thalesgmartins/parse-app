"""Rotas para renderização das páginas web com Jinja2."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.auth import obter_usuario_logado
from app.database.repository import (
    contar_extracos,
    listar_clientes,
    listar_jobs_por_advogado,
)
from app.database.session import get_db

router = APIRouter(tags=["Frontend"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "web" / "templates")


@router.get("/dashboard")
async def renderizar_dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Renderiza a página principal da dashboard com lista de clientes e métricas.

    Args:
        request: Objeto da requisição HTTP.
        db: Sessão ativa do banco de dados relacional.

    Returns:
        TemplateResponse renderizando dashboard.html ou redirecionamento para login.
    """
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=303)

    try:
        usuario = await obter_usuario_logado(access_token=token, db=db)
        clientes_do_advogado = listar_clientes(db=db, advogado_id=usuario.id)
        total_extracos = contar_extracos(db=db, advogado_id=usuario.id)
        jobs_do_advogado = listar_jobs_por_advogado(db=db, advogado_id=usuario.id)

        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "clientes": clientes_do_advogado,
                "usuario_nome": usuario.nome,
                "usuario_email": usuario.email,
                "total_extracos": total_extracos,
                "jobs": jobs_do_advogado,
            },
        )
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)


@router.get("/login")
async def renderizar_login(request: Request, erro: str | None = None):
    """Renderiza a página de autenticação.

    Args:
        request: Objeto da requisição HTTP.
        erro: Mensagem de erro opcional recebida via query string.

    Returns:
        TemplateResponse renderizando login.html.
    """
    mensagem_erro = erro or request.query_params.get("erro")
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"erro": mensagem_erro},
    )
