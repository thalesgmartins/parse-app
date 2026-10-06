"""Camada de repositório para persistência de dados utilizando SQLAlchemy 2.0."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.schemas import CnisCompetencia
from app.core.security import hash_password
from app.database.models import Advogado, Cliente, Contribuicao, LogExtracao


def obter_advogado_por_email(db: Session, email: str) -> Advogado | None:
    """Busca um advogado pelo seu endereço de e-mail.

    Args:
        db: Sessão ativa do SQLAlchemy.
        email: E-mail do advogado.

    Returns:
        Instância de Advogado ou None se não encontrado.
    """
    stmt = select(Advogado).where(Advogado.email == email)
    return db.scalar(stmt)


def obter_advogado_por_id(
    db: Session,
    advogado_id: uuid.UUID | str,
) -> Advogado | None:
    """Busca um advogado pelo identificador único.

    Args:
        db: Sessão ativa do SQLAlchemy.
        advogado_id: UUID ou representação em string do ID do advogado.

    Returns:
        Instância de Advogado ou None se não encontrado.
    """
    id_uuid = advogado_id if isinstance(advogado_id, uuid.UUID) else uuid.UUID(str(advogado_id))
    stmt = select(Advogado).where(Advogado.id == id_uuid)
    return db.scalar(stmt)


def criar_advogado(
    db: Session,
    nome: str,
    email: str,
    senha: str,
) -> Advogado:
    """Cadastra um novo advogado com senha criptografada.

    Args:
        db: Sessão ativa do SQLAlchemy.
        nome: Nome completo do advogado.
        email: E-mail profissional.
        senha: Senha em texto plano que será hasheada com bcrypt.

    Returns:
        Instância do novo Advogado cadastrado.
    """
    advogado = Advogado(
        nome=nome,
        email=email,
        senha_hash=hash_password(senha),
    )
    db.add(advogado)
    db.commit()
    db.refresh(advogado)
    return advogado


def criar_cliente(
    db: Session,
    advogado_id: uuid.UUID | str,
    nome: str,
    cpf: str | None = None,
) -> Cliente:
    """Cadastra um novo cliente para o advogado logado.

    Args:
        db: Sessão ativa do SQLAlchemy.
        advogado_id: Identificador do advogado responsável.
        nome: Nome completo do cliente.
        cpf: CPF do cliente (opcional).

    Returns:
        Instância do Cliente criado.
    """
    id_uuid = advogado_id if isinstance(advogado_id, uuid.UUID) else uuid.UUID(str(advogado_id))
    cliente = Cliente(
        advogado_id=id_uuid,
        nome=nome,
        cpf=cpf,
    )
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return cliente


def listar_clientes(
    db: Session,
    advogado_id: uuid.UUID | str,
) -> list[Cliente]:
    """Busca todos os clientes vinculados a um advogado específico.

    Args:
        db: Sessão ativa do SQLAlchemy.
        advogado_id: Identificador do advogado.

    Returns:
        Lista de clientes ordenados pelo nome.
    """
    id_uuid = advogado_id if isinstance(advogado_id, uuid.UUID) else uuid.UUID(str(advogado_id))
    stmt = select(Cliente).where(Cliente.advogado_id == id_uuid).order_by(Cliente.nome)
    return list(db.scalars(stmt).all())


def salvar_contribuicoes(
    db: Session,
    cliente_id: uuid.UUID | str,
    lista: list[CnisCompetencia],
) -> list[Contribuicao]:
    """Salva a lista de competências e salários vinculados a um cliente.

    Args:
        db: Sessão ativa do SQLAlchemy.
        cliente_id: Identificador do cliente.
        lista: Lista de competências extraídas do CNIS.

    Returns:
        Lista de instâncias de Contribuicao salvas no banco.
    """
    id_uuid = cliente_id if isinstance(cliente_id, uuid.UUID) else uuid.UUID(str(cliente_id))
    novas_contribuicoes: list[Contribuicao] = [
        Contribuicao(
            cliente_id=id_uuid,
            data_competencia=c.data_competencia,
            valor=c.valor,
        )
        for c in lista
    ]
    db.add_all(novas_contribuicoes)
    db.commit()
    return novas_contribuicoes


def registrar_log_extracao(
    db: Session,
    advogado_id: uuid.UUID | str,
    nome_arquivo: str,
    status: str,
    mensagem_erro: str | None = None,
) -> LogExtracao:
    """Registra uma entrada de auditoria sobre a extração de um arquivo.

    Args:
        db: Sessão ativa do SQLAlchemy.
        advogado_id: Identificador do advogado que submeteu o arquivo.
        nome_arquivo: Nome do arquivo PDF processado.
        status: Status do processamento ('sucesso' ou 'erro').
        mensagem_erro: Detalhes do erro, se houver.

    Returns:
        Instância do LogExtracao gerado.
    """
    id_uuid = advogado_id if isinstance(advogado_id, uuid.UUID) else uuid.UUID(str(advogado_id))
    log = LogExtracao(
        advogado_id=id_uuid,
        nome_arquivo=nome_arquivo,
        status=status,
        mensagem_erro=mensagem_erro,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
