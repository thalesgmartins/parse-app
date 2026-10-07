"""Utilitários de segurança para hashing de senhas e geração de tokens JWT."""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY


def hash_password(password: str) -> str:
    """Gera um hash seguro para a senha fornecida usando bcrypt.

    Args:
        password: Senha em texto plano.

    Returns:
        Hash da senha em formato string.
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha em texto plano corresponde ao hash armazenado.

    Args:
        plain_password: Senha em texto plano a ser testada.
        hashed_password: Hash bcrypt previamente armazenado.

    Returns:
        True se a senha for válida, False caso contrário.
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def create_access_token(
    data: dict[str, str],
    expires_delta: timedelta | None = None,
) -> str:
    """Cria um token JWT codificado com tempo de expiração.

    Args:
        data: Dados a serem inseridos nas claims do token (ex: {'sub': 'user_id'}).
        expires_delta: Tempo opcional de expiração. Se não fornecido, usa a configuração padrão.

    Returns:
        Token JWT assinado.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, str] | None:
    """Decodifica e valida a assinatura e expiração de um token JWT.

    Args:
        token: Token JWT a ser decodificado.

    Returns:
        Dicionário com as claims do token ou None se inválido/expirado.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None
