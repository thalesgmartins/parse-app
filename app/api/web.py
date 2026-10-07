"""Rotas para renderização das páginas web com Jinja2."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.auth import obter_usuario_logado
from app.database.repository import listar_clientes
from app.database.session import get_db

router = APIRouter(tags=["Frontend"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "web" / "templates")


@router.get("/dashboard")
async def renderizar_dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Renderiza a página principal da dashboard com lista de clientes."""
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=303)

    try:
        usuario = await obter_usuario_logado(access_token=token, db=db)
        clientes_do_advogado = listar_clientes(db=db, advogado_id=usuario.id)

        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "clientes": clientes_do_advogado,
                "usuario_email": usuario.email,
            },
        )
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)


@router.get("/login")
async def renderizar_login(request: Request):
    """Renderiza a página de autenticação."""
    return templates.TemplateResponse(request=request, name="login.html")
