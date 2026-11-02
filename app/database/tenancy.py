"""Isolamento Multi-Tenant por Schema no PostgreSQL com compatibilidade SQLite."""

import logging
import re
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

_LOGGER = logging.getLogger(__name__)
_RE_SCHEMA_TENANT = re.compile(r"^tenant_[0-9a-f]{32}$")
_SCHEMAS_PROVISIONADOS: set[str] = set()


def gerar_nome_schema(advogado_id: uuid.UUID | str) -> str:
    """Gera o nome determinístico do schema PostgreSQL para um advogado.

    Args:
        advogado_id: UUID ou string UUID do advogado.

    Returns:
        Nome seguro de schema no formato 'tenant_<32_hex>'.

    Raises:
        ValueError: Se o identificador fornecido não for um UUID válido.
    """
    id_uuid = advogado_id if isinstance(advogado_id, uuid.UUID) else uuid.UUID(str(advogado_id))
    return f"tenant_{id_uuid.hex}"


def validar_nome_schema(schema_name: str) -> str:
    """Valida que o identificador do schema segue estritamente o padrão hexadecimal.

    Args:
        schema_name: Nome do schema a ser validado antes de uso em comandos SQL.

    Returns:
        O próprio schema_name caso seja válido.

    Raises:
        ValueError: Se o nome do schema violar o padrão seguro 'tenant_<32_hex>'.
    """
    limpo = schema_name.strip().lower()
    if not _RE_SCHEMA_TENANT.match(limpo):
        raise ValueError(f"Nome de schema multi-tenant inválido: {schema_name}")
    return limpo


def obter_mapa_schema(
    schema_name: str | None,
    *,
    dialeto_sqlite: bool = False,
) -> dict[str, str | None]:
    """Constrói o dicionário de schema_translate_map para o SQLAlchemy.

    Args:
        schema_name: Nome do schema do tenant ativo (ou None para global).
        dialeto_sqlite: Indica se a conexão ativa utiliza SQLite em memória.

    Returns:
        Mapa de tradução de schema compatível com execution_options.
    """
    if dialeto_sqlite or not schema_name:
        return {"tenant": None}
    return {"tenant": validar_nome_schema(schema_name)}


def _executar_ddl_tabelas_tenant(db: Session, schema: str) -> None:
    """Cria o schema e as tabelas isoladas do tenant no PostgreSQL."""
    db.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    db.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS "{schema}".clientes (
                id UUID PRIMARY KEY,
                advogado_id UUID NOT NULL REFERENCES public.advogados(id) ON DELETE CASCADE,
                nome VARCHAR(255) NOT NULL,
                cpf VARCHAR(14),
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL
            )
            """
        )
    )
    db.execute(
        text(
            f'CREATE INDEX IF NOT EXISTS "ix_{schema}_clientes_advogado_id" '
            f'ON "{schema}".clientes (advogado_id)'
        )
    )
    db.execute(
        text(f'CREATE INDEX IF NOT EXISTS "ix_{schema}_clientes_cpf" ON "{schema}".clientes (cpf)')
    )
    db.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS "{schema}".extraction_jobs (
                id UUID PRIMARY KEY,
                advogado_id UUID NOT NULL REFERENCES public.advogados(id) ON DELETE CASCADE,
                cliente_id UUID REFERENCES "{schema}".clientes(id) ON DELETE CASCADE,
                nome_arquivo VARCHAR(255) NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'pending',
                total_competencias INTEGER NOT NULL DEFAULT 0,
                mensagem_erro VARCHAR(1000),
                caminho_arquivo_temp VARCHAR(500),
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
                updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL
            )
            """
        )
    )
    db.execute(
        text(
            f'CREATE INDEX IF NOT EXISTS "ix_{schema}_jobs_advogado_id" '
            f'ON "{schema}".extraction_jobs (advogado_id)'
        )
    )
    db.execute(
        text(
            f'CREATE INDEX IF NOT EXISTS "ix_{schema}_jobs_status" '
            f'ON "{schema}".extraction_jobs (status)'
        )
    )
    db.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS "{schema}".contribuicoes (
                id UUID PRIMARY KEY,
                cliente_id UUID REFERENCES "{schema}".clientes(id) ON DELETE CASCADE,
                job_id UUID REFERENCES "{schema}".extraction_jobs(id) ON DELETE SET NULL,
                data_competencia VARCHAR(10) NOT NULL,
                valor DOUBLE PRECISION NOT NULL,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
                CONSTRAINT "uq_{schema}_cliente_competencia"
                    UNIQUE (cliente_id, data_competencia)
            )
            """
        )
    )
    db.execute(
        text(
            f'CREATE INDEX IF NOT EXISTS "ix_{schema}_contrib_cliente_id" '
            f'ON "{schema}".contribuicoes (cliente_id)'
        )
    )
    db.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS "{schema}".extractions_logs (
                id UUID PRIMARY KEY,
                advogado_id UUID NOT NULL REFERENCES public.advogados(id) ON DELETE CASCADE,
                nome_arquivo VARCHAR(255) NOT NULL,
                status VARCHAR(50) NOT NULL,
                mensagem_erro VARCHAR(1000),
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL
            )
            """
        )
    )
    db.commit()


def provisionar_schema_tenant(db: Session, schema_name: str) -> str:
    """Garante que o schema exclusivo do tenant e suas tabelas existam no banco.

    Args:
        db: Sessão ativa do SQLAlchemy.
        schema_name: Nome do schema do tenant ('tenant_<32_hex>').

    Returns:
        O nome validado do schema provisionado.
    """
    schema_valido = validar_nome_schema(schema_name)
    dialeto = db.bind.dialect.name if db.bind is not None else "sqlite"

    if dialeto == "sqlite":
        _SCHEMAS_PROVISIONADOS.add(schema_valido)
        return schema_valido

    if schema_valido not in _SCHEMAS_PROVISIONADOS:
        _executar_ddl_tabelas_tenant(db, schema_valido)
        _SCHEMAS_PROVISIONADOS.add(schema_valido)
        _LOGGER.info("Schema multi-tenant provisionado: %s", schema_valido)

    return schema_valido


def ativar_schema_tenant(
    db: Session,
    schema_name: str | None = None,
    advogado_id: uuid.UUID | str | None = None,
) -> str:
    """Ativa o isolamento de schema do tenant na sessão atual do banco de dados.

    Args:
        db: Sessão ativa do SQLAlchemy.
        schema_name: Nome do schema já atribuído ao advogado (opcional).
        advogado_id: UUID do advogado para derivar o schema se ausente (opcional).

    Returns:
        Nome validado do schema ativo na sessão.

    Raises:
        ValueError: Se nem schema_name nem advogado_id forem fornecidos.
    """
    if schema_name:
        alvo = validar_nome_schema(schema_name)
    elif advogado_id:
        alvo = gerar_nome_schema(advogado_id)
    else:
        raise ValueError("É necessário informar schema_name ou advogado_id para ativar o tenant.")

    provisionar_schema_tenant(db, alvo)
    db.info["tenant_schema"] = alvo

    dialeto = db.bind.dialect.name if db.bind is not None else "sqlite"
    if dialeto != "sqlite":
        db.execute(text(f'SET search_path TO "{alvo}", public'))

    return alvo


def resetar_schema_sessao(db: Session) -> None:
    """Restaura o search_path da sessão para o schema public ao encerrar o uso.

    Args:
        db: Sessão ativa do SQLAlchemy.
    """
    db.info["tenant_schema"] = "public"
    dialeto = db.bind.dialect.name if db.bind is not None else "sqlite"
    if dialeto != "sqlite":
        try:
            db.execute(text("SET search_path TO public"))
        except Exception as exc:
            _LOGGER.debug("Não foi possível resetar search_path da sessão: %s", exc)
