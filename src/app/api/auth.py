from fastapi import APIRouter, Cookie, Form, HTTPException, Response

from app.database.connection import get_supabase

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/login")
async def fazer_login(response: Response, email: str = Form(...), password: str = Form(...)):
    supabase = get_supabase()

    try:
        auth_response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        token = auth_response.session.access_token

        response.set_cookie(key="access_token", value=token, httponly=True, samesite="lax", secure=False)
        return {"status": "sucesso", "mensagem": "Login efetuado!"}
    except Exception:
        raise HTTPException(status_code=401, detail="Email ou senha incorretos.")


async def obter_usuario_logado(access_token: str = Cookie(None)):
    """Verifica o cookie e retorna os dados do usuário do Supabase."""
    if not access_token:
        raise HTTPException(status_code=401, detail="Não autenticado.")

    supabase = get_supabase()

    try:
        # Valida o token com o Supabase e pega os dados do usuário
        user_response = supabase.auth.get_user(access_token)
        return user_response.user
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado.")
