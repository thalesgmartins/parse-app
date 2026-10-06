"""Rotas de autenticação nativa com JWT e sessões no PostgreSQL."""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.security import create_access_token, decode_access_token, verify_password
from app.database.models import Advogado
from app.database.repository import criar_advogado, obter_advogado_por_email, obter_advogado_por_id
from app.database.session import get_db

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/login")
async def fazer_login(
    response: Response,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)],
) -> RedirectResponse:
    """Valida as credenciais do advogado e define o cookie HTTP-only com token JWT."""
    advogado = obter_advogado_por_email(db, email=email)
    if not advogado or not verify_password(password, advogado.senha_hash):
        raise HTTPException(status_code=401, detail="Email ou senha incorretos.")

    token = create_access_token(data={"sub": str(advogado.id), "email": advogado.email})

    redirect_response = RedirectResponse(url="/dashboard", status_code=303)
    redirect_response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return redirect_response


@router.post("/register")
async def cadastrar_advogado(
    nome: Annotated[str, Form()],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)],
) -> RedirectResponse:
    """Cadastra um novo escritório/advogado no sistema."""
    existente = obter_advogado_por_email(db, email=email)
    if existente:
        raise HTTPException(status_code=400, detail="E-mail já cadastrado.")

    advogado = criar_advogado(db, nome=nome, email=email, senha=password)
    token = create_access_token(data={"sub": str(advogado.id), "email": advogado.email})

    redirect_response = RedirectResponse(url="/dashboard", status_code=303)
    redirect_response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return redirect_response


@router.get("/logout")
async def fazer_logout() -> RedirectResponse:
    """Encerra a sessão removendo o cookie de autenticação."""
    redirect_response = RedirectResponse(url="/login", status_code=303)
    redirect_response.delete_cookie(key="access_token")
    return redirect_response


async def obter_usuario_logado(
    access_token: Annotated[str | None, Cookie()] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> Advogado:
    """Dependência para autenticar requisições a partir do cookie JWT."""
    if not access_token:
        raise HTTPException(status_code=401, detail="Não autenticado.")

    payload = decode_access_token(access_token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado.")

    user_id = payload["sub"]
    advogado = obter_advogado_por_id(db, user_id)
    if not advogado:
        raise HTTPException(status_code=401, detail="Usuário não encontrado.")

    return advogado
