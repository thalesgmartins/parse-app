from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api.auth import obter_usuario_logado
from app.database.repository import listar_clientes

router = APIRouter(tags=["Frontend"])
templates = Jinja2Templates(directory="src/app/web/templates")


@router.get("/dashboard")
async def renderizar_dashboard(request: Request):
    try:
        usuario = await obter_usuario_logado(request.cookies.get("access_token"))

        clientes_do_advogado = listar_clientes(usuario.id)

        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={"clientes": clientes_do_advogado, "usuario_email": usuario.email},
        )
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)


@router.get("/login")
async def renderizar_login(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")
