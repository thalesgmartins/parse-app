"""Rotas de autenticação nativa com JWT e sessões no PostgreSQL."""

import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import timedelta
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

from app.core.config import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
    UPLOAD_DIR,
)
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
    obter_ou_criar_advogado_google,
)
from app.database.session import get_db
from app.database.tenancy import ativar_schema_tenant, gerar_nome_schema

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
@limiter.limit("3/minute")
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

    if not advogado.schema_name:
        advogado.schema_name = gerar_nome_schema(advogado.id)
        db.commit()
        db.refresh(advogado)

    ativar_schema_tenant(db, schema_name=advogado.schema_name, advogado_id=advogado.id)
    return advogado


def _trocar_codigo_por_perfil_google(code: str) -> dict[str, object]:
    """Troca o authorization code pelo token OAuth2 e consulta o userinfo do Google.

    Args:
        code: Código de autorização retornado no callback OAuth 2.0.

    Returns:
        Dicionário contendo 'sub', 'email', 'email_verified', 'name' e 'picture'.

    Raises:
        ValueError: Se a troca de token ou consulta de perfil falhar.
    """
    dados_token = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")

    req_token = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=dados_token,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req_token, timeout=10) as resp:
            token_json = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise ValueError("Falha ao validar código de autorização junto ao Google.") from exc

    access_token_google = str(token_json.get("access_token") or "")
    if not access_token_google:
        raise ValueError("Google não retornou um access_token válido.")

    req_userinfo = urllib.request.Request(
        "https://openidconnect.googleapis.com/v1/userinfo",
        headers={"Authorization": f"Bearer {access_token_google}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req_userinfo, timeout=10) as resp_info:
            perfil = json.loads(resp_info.read().decode("utf-8"))
            return perfil if isinstance(perfil, dict) else {}
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise ValueError("Falha ao obter dados do perfil Google.") from exc


@router.get("/google/login")
async def iniciar_login_google() -> RedirectResponse:
    """Redireciona o advogado para a tela de consentimento Google OAuth 2.0.

    Returns:
        RedirectResponse para accounts.google.com ou para /login com aviso.
    """
    if not GOOGLE_CLIENT_ID.strip() or not GOOGLE_CLIENT_SECRET.strip():
        return RedirectResponse(
            url=(
                "/login?erro=Login+com+Google+não+configurado+no+.env+"
                "(defina+GOOGLE_CLIENT_ID+e+GOOGLE_CLIENT_SECRET)."
            ),
            status_code=303,
        )

    nonce_state = secrets.token_urlsafe(24)
    state_jwt = create_access_token(
        data={"oauth_state": nonce_state},
        expires_delta=timedelta(minutes=10),
    )
    params = urllib.parse.urlencode(
        {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "state": nonce_state,
            "access_type": "online",
            "prompt": "select_account",
        }
    )
    url_google = f"https://accounts.google.com/o/oauth2/v2/auth?{params}"
    resposta = RedirectResponse(url=url_google, status_code=303)
    resposta.set_cookie(
        key="oauth_state",
        value=state_jwt,
        httponly=True,
        samesite="lax",
        max_age=600,
    )
    return resposta


@router.get("/google/callback")
async def callback_login_google(
    db: Annotated[Session, Depends(get_db)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    oauth_state: Annotated[str | None, Cookie()] = None,
) -> RedirectResponse:
    """Processa o retorno do Google OAuth 2.0, provisiona o tenant e inicia sessão.

    Args:
        db: Sessão ativa do banco de dados.
        code: Código de autorização enviado pelo Google.
        state: Token anti-CSRF enviado na query string.
        error: Erro opcional retornado pelo provedor OAuth.
        oauth_state: Cookie assinado contendo o state original.

    Returns:
        Redirecionamento autenticado para /dashboard ou para /login com erro.
    """
    if error or not code or not state or not oauth_state:
        return RedirectResponse(
            url="/login?erro=Autenticação+com+Google+cancelada+ou+inválida.",
            status_code=303,
        )

    payload_state = decode_access_token(oauth_state)
    if not payload_state or payload_state.get("oauth_state") != state:
        return RedirectResponse(
            url="/login?erro=Sessão+OAuth+expirada+ou+inválida+(CSRF).",
            status_code=303,
        )

    try:
        perfil = _trocar_codigo_por_perfil_google(code)
    except ValueError as exc:
        return RedirectResponse(
            url=f"/login?erro={urllib.parse.quote(str(exc))}",
            status_code=303,
        )

    google_sub = str(perfil.get("sub") or "").strip()
    email = str(perfil.get("email") or "").strip().lower()
    email_verificado = bool(perfil.get("email_verified"))
    nome = str(perfil.get("name") or email.split("@")[0]).strip()
    foto_url = str(perfil.get("picture") or "").strip() or None

    if not google_sub or not email or not email_verificado:
        return RedirectResponse(
            url="/login?erro=A+conta+Google+precisa+ter+um+e-mail+verificado.",
            status_code=303,
        )

    advogado = obter_ou_criar_advogado_google(
        db=db,
        google_sub=google_sub,
        email=email,
        nome=nome,
        avatar_url=foto_url,
    )
    token = create_access_token(data={"sub": str(advogado.id), "email": advogado.email})

    resposta = RedirectResponse(url="/dashboard", status_code=303)
    resposta.delete_cookie("oauth_state")
    resposta.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return resposta


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
