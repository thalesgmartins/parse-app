"""Rotas de autenticação nativa com JWT e sessões no PostgreSQL."""

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.core.config import UPLOAD_DIR
from app.core.limiter import limiter
from app.core.security import (
    create_access_token,
    decode_access_token,
    verify_password,
)
from app.database.models import Advogado
from app.database.repository import (
    atualizar_perfil_advogado,
    criar_advogado,
    obter_advogado_por_email,
    obter_advogado_por_id,
)
from app.database.session import get_db

router = APIRouter(prefix="/auth", tags=["Autenticação"])
_MAX_AVATAR_BYTES = 5 * 1024 * 1024


def obter_caminho_avatar(advogado_id: uuid.UUID) -> Path:
    """Retorna o caminho em disco onde o avatar do advogado é armazenado.

    Args:
        advogado_id: Identificador único do advogado.

    Returns:
        Objeto Path apontando para o arquivo de imagem do avatar.
    """
    pasta_avatars = UPLOAD_DIR / "avatars"
    pasta_avatars.mkdir(parents=True, exist_ok=True)
    return pasta_avatars / f"{advogado_id}.img"


def usuario_possui_avatar(advogado_id: uuid.UUID) -> bool:
    """Verifica se o advogado possui uma foto de perfil personalizada salva.

    Args:
        advogado_id: Identificador único do advogado.

    Returns:
        True se o arquivo de avatar existir e não estiver vazio.
    """
    caminho = obter_caminho_avatar(advogado_id)
    return caminho.exists() and caminho.stat().st_size > 0


@router.post("/login")
@limiter.limit("5/minute")
async def fazer_login(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)],
) -> RedirectResponse:
    """Valida as credenciais do advogado e define o cookie HTTP-only com JWT.

    Args:
        request: Objeto da requisição HTTP recebida.
        email: E-mail de login submetido.
        password: Senha em texto plano.
        db: Sessão ativa do banco de dados relacional.

    Returns:
        Redirecionamento para a dashboard (em sucesso) ou para /login com erro.

    Raises:
        HTTPException: Se for cliente de API/testes e credenciais inválidas.
    """
    advogado = obter_advogado_por_email(db, email=email)
    if not advogado or not verify_password(password, advogado.senha_hash):
        if "text/html" in request.headers.get("accept", ""):
            return RedirectResponse(
                url="/login?erro=Email+ou+senha+incorretos.",
                status_code=303,
            )
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
    request: Request,
    nome: Annotated[str, Form()],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)],
) -> RedirectResponse:
    """Cadastra um novo escritório/advogado no sistema.

    Args:
        request: Objeto da requisição HTTP recebida.
        nome: Nome completo do advogado.
        email: E-mail profissional.
        password: Senha em texto plano.
        db: Sessão ativa do banco de dados relacional.

    Returns:
        Redirecionamento para a dashboard ou de volta para /login em erro.

    Raises:
        HTTPException: Se for cliente de API e o e-mail já estiver cadastrado.
    """
    existente = obter_advogado_por_email(db, email=email)
    if existente:
        if "text/html" in request.headers.get("accept", ""):
            return RedirectResponse(
                url="/login?erro=E-mail+já+cadastrado+no+sistema.",
                status_code=303,
            )
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
    db: Annotated[Session, Depends(get_db)],
    access_token: Annotated[str | None, Cookie()] = None,
) -> Advogado:
    """Dependência para autenticar requisições a partir do cookie JWT.

    Args:
        db: Sessão ativa do banco de dados.
        access_token: Token JWT extraído do cookie HTTP-only.

    Returns:
        Instância do Advogado autenticado.

    Raises:
        HTTPException: Se o token estiver ausente, inválido ou expirado.
    """
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


@router.post("/perfil")
async def atualizar_perfil(
    usuario: Annotated[Advogado, Depends(obter_usuario_logado)],
    db: Annotated[Session, Depends(get_db)],
    nome: Annotated[str | None, Form()] = None,
    nova_senha: Annotated[str | None, Form()] = None,
    foto: Annotated[UploadFile | None, File()] = None,
) -> RedirectResponse:
    """Atualiza o nome, senha e/ou foto de perfil do advogado logado.

    Args:
        usuario: Advogado autenticado.
        db: Sessão ativa do banco de dados.
        nome: Novo nome de exibição (opcional).
        nova_senha: Nova senha de acesso (opcional).
        foto: Arquivo de imagem de avatar enviado (opcional).

    Returns:
        RedirectResponse recarregando o painel com os dados atualizados.
    """
    atualizar_perfil_advogado(
        db=db,
        advogado=usuario,
        nome=nome,
        nova_senha=nova_senha,
    )

    if foto and foto.filename:
        conteudo = await foto.read(_MAX_AVATAR_BYTES + 1)
        if 0 < len(conteudo) <= _MAX_AVATAR_BYTES:
            caminho_avatar = obter_caminho_avatar(usuario.id)
            caminho_avatar.write_bytes(conteudo)

    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/avatar")
async def obter_avatar_usuario(
    usuario: Annotated[Advogado, Depends(obter_usuario_logado)],
) -> Response:
    """Serve a imagem de perfil personalizada do advogado autenticado.

    Args:
        usuario: Advogado autenticado.

    Returns:
        Response binária com a imagem do avatar.

    Raises:
        HTTPException: 404 caso o advogado ainda não tenha cadastrado foto.
    """
    caminho = obter_caminho_avatar(usuario.id)
    if not caminho.exists() or caminho.stat().st_size == 0:
        raise HTTPException(status_code=404, detail="Avatar não cadastrado.")

    return Response(
        content=caminho.read_bytes(),
        media_type="image/png",
        headers={"Cache-Control": "no-cache"},
    )
