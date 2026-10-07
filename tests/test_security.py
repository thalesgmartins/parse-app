"""Testes unitários para o módulo de segurança e autenticação JWT."""

from datetime import timedelta

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_e_verificacao_senha() -> None:
    """Testa geração de hash com bcrypt e validação de senha."""
    # Arrange
    senha_plana = "SegredoAdvogado123"

    # Act
    hash_gerado = hash_password(senha_plana)
    senha_valida = verify_password(senha_plana, hash_gerado)
    senha_invalida = verify_password("SenhaErrada", hash_gerado)

    # Assert
    assert senha_valida is True
    assert senha_invalida is False
    assert hash_gerado != senha_plana


def test_geracao_e_decodificacao_jwt() -> None:
    """Testa a criação de token JWT e extração correta das claims."""
    # Arrange
    dados_usuario = {"sub": "123e4567-e89b-12d3-a456-426614174000", "email": "adv@teste.com"}

    # Act
    token = create_access_token(dados_usuario)
    payload = decode_access_token(token)

    # Assert
    assert payload is not None
    assert payload["sub"] == dados_usuario["sub"]
    assert payload["email"] == dados_usuario["email"]
    assert "exp" in payload


def test_token_expirado_retorna_none() -> None:
    """Testa que tokens com data de expiração no passado retornam None."""
    # Arrange
    dados_usuario = {"sub": "advogado-id"}
    token_expirado = create_access_token(
        dados_usuario,
        expires_delta=timedelta(seconds=-1),
    )

    # Act
    payload = decode_access_token(token_expirado)

    # Assert
    assert payload is None
