"""Camada de repositório para persistência de dados utilizando SQLAlchemy 2.0."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.schemas import CnisCompetencia
from app.core.security import hash_password
from app.database.models import Advogado, Cliente, Contribuicao, JobExtracao, LogExtracao


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


def obter_cliente_por_id(
    db: Session,
    cliente_id: uuid.UUID | str,
) -> Cliente | None:
    """Busca um cliente pelo identificador único.

    Args:
        db: Sessão ativa do SQLAlchemy.
        cliente_id: Identificador único do cliente.

    Returns:
        Instância de Cliente ou None se não encontrado.
    """
    id_uuid = cliente_id if isinstance(cliente_id, uuid.UUID) else uuid.UUID(str(cliente_id))
    stmt = select(Cliente).where(Cliente.id == id_uuid)
    return db.scalar(stmt)


def salvar_contribuicoes(
    db: Session,
    cliente_id: uuid.UUID | str | None,
    lista: list[CnisCompetencia],
    job_id: uuid.UUID | str | None = None,
) -> list[Contribuicao]:
    """Salva a lista de competências e salários vinculados a um cliente e/ou job.

    Args:
        db: Sessão ativa do SQLAlchemy.
        cliente_id: Identificador do cliente (opcional).
        lista: Lista de competências extraídas do CNIS.
        job_id: Identificador do job de extração (opcional).

    Returns:
        Lista de instâncias de Contribuicao salvas no banco.
    """
    c_uuid = (
        cliente_id
        if (cliente_id is None or isinstance(cliente_id, uuid.UUID))
        else uuid.UUID(str(cliente_id))
    )
    j_uuid = job_id if (job_id is None or isinstance(job_id, uuid.UUID)) else uuid.UUID(str(job_id))
    novas_contribuicoes: list[Contribuicao] = [
        Contribuicao(
            cliente_id=c_uuid,
            job_id=j_uuid,
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


def contar_extracos(
    db: Session,
    advogado_id: uuid.UUID | str,
) -> int:
    """Retorna o total de extrações de CNIS processadas pelo advogado.

    Args:
        db: Sessão ativa do SQLAlchemy.
        advogado_id: Identificador do advogado.

    Returns:
        Número total de extrações registradas.
    """
    id_uuid = advogado_id if isinstance(advogado_id, uuid.UUID) else uuid.UUID(str(advogado_id))
    stmt = select(func.count(LogExtracao.id)).where(LogExtracao.advogado_id == id_uuid)
    return db.scalar(stmt) or 0


def criar_job_extracao(
    db: Session,
    job_id: uuid.UUID,
    advogado_id: uuid.UUID | str,
    nome_arquivo: str,
    cliente_id: uuid.UUID | str | None = None,
    caminho_arquivo_temp: str | None = None,
) -> JobExtracao:
    """Registra um novo trabalho de processamento na fila do banco de dados.

    Args:
        db: Sessão ativa do SQLAlchemy.
        job_id: Identificador único gerado para o job.
        advogado_id: Identificador do advogado solicitante.
        nome_arquivo: Nome original do arquivo PDF.
        cliente_id: Identificador do cliente associado (opcional).
        caminho_arquivo_temp: Caminho efêmero onde o arquivo foi salvo no disco.

    Returns:
        Instância de JobExtracao persistida com status 'pending'.
    """
    adv_uuid = advogado_id if isinstance(advogado_id, uuid.UUID) else uuid.UUID(str(advogado_id))
    cli_uuid = (
        cliente_id
        if (cliente_id is None or isinstance(cliente_id, uuid.UUID))
        else uuid.UUID(str(cliente_id))
    )
    job = JobExtracao(
        id=job_id,
        advogado_id=adv_uuid,
        cliente_id=cli_uuid,
        nome_arquivo=nome_arquivo,
        status="pending",
        caminho_arquivo_temp=caminho_arquivo_temp,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def obter_job_por_id(
    db: Session,
    job_id: uuid.UUID | str,
) -> JobExtracao | None:
    """Busca um trabalho de extração pelo identificador único.

    Args:
        db: Sessão ativa do SQLAlchemy.
        job_id: Identificador único do job.

    Returns:
        Instância de JobExtracao ou None se inexistente.
    """
    id_uuid = job_id if isinstance(job_id, uuid.UUID) else uuid.UUID(str(job_id))
    stmt = select(JobExtracao).where(JobExtracao.id == id_uuid)
    return db.scalar(stmt)


def obter_proximo_job(db: Session) -> JobExtracao | None:
    """Busca o próximo trabalho pendente na fila utilizando concorrência segura.

    Em bancos de dados compatíveis (como PostgreSQL), aplica
    FOR UPDATE SKIP LOCKED para prevenir condições de corrida entre múltiplos
    workers simultâneos.

    Args:
        db: Sessão ativa do SQLAlchemy.

    Returns:
        Instância do próximo JobExtracao pendente ou None se a fila estiver vazia.
    """
    stmt = (
        select(JobExtracao)
        .where(JobExtracao.status == "pending")
        .order_by(JobExtracao.created_at.asc())
        .limit(1)
    )
    if db.bind and db.bind.dialect.name != "sqlite":
        stmt = stmt.with_for_update(skip_locked=True)
    return db.scalar(stmt)


def bloquear_job_para_processamento(
    db: Session,
    job_id: uuid.UUID | str,
) -> JobExtracao | None:
    """Bloqueia atomicamente um job pendente e altera status para 'processing'.

    Args:
        db: Sessão ativa do SQLAlchemy.
        job_id: Identificador do job a ser bloqueado.

    Returns:
        Instância de JobExtracao em processamento ou None caso indisponível.
    """
    id_uuid = job_id if isinstance(job_id, uuid.UUID) else uuid.UUID(str(job_id))
    stmt = select(JobExtracao).where(
        JobExtracao.id == id_uuid,
        JobExtracao.status == "pending",
    )
    if db.bind and db.bind.dialect.name != "sqlite":
        stmt = stmt.with_for_update(skip_locked=True)
    job = db.scalar(stmt)
    if not job:
        return None

    job.status = "processing"
    db.commit()
    db.refresh(job)
    return job


def concluir_job(
    db: Session,
    job_id: uuid.UUID | str,
    total_competencias: int,
) -> JobExtracao | None:
    """Finaliza com sucesso o processamento de um job.

    Args:
        db: Sessão ativa do SQLAlchemy.
        job_id: Identificador único do job.
        total_competencias: Quantidade total de competências previdenciárias.

    Returns:
        Instância de JobExtracao atualizada ou None se inexistente.
    """
    job = obter_job_por_id(db, job_id)
    if not job:
        return None

    job.status = "completed"
    job.total_competencias = total_competencias
    job.caminho_arquivo_temp = None
    db.commit()
    db.refresh(job)
    return job


def falhar_job(
    db: Session,
    job_id: uuid.UUID | str,
    mensagem_erro: str,
) -> JobExtracao | None:
    """Registra falha no processamento de um job e grava a mensagem de erro.

    Args:
        db: Sessão ativa do SQLAlchemy.
        job_id: Identificador único do job.
        mensagem_erro: Detalhes do motivo da falha.

    Returns:
        Instância de JobExtracao atualizada ou None se inexistente.
    """
    job = obter_job_por_id(db, job_id)
    if not job:
        return None

    job.status = "failed"
    job.mensagem_erro = mensagem_erro
    job.caminho_arquivo_temp = None
    db.commit()
    db.refresh(job)
    return job


def obter_contribuicoes_por_job(
    db: Session,
    job_id: uuid.UUID | str,
) -> list[Contribuicao]:
    """Retorna as contribuições previdenciárias associadas a uma execução de job.

    Args:
        db: Sessão ativa do SQLAlchemy.
        job_id: Identificador único do job.

    Returns:
        Lista de Contribuicao ordenadas pela data da competência cronologicamente.
    """
    id_uuid = job_id if isinstance(job_id, uuid.UUID) else uuid.UUID(str(job_id))
    ano_col = func.substr(Contribuicao.data_competencia, 4, 4)
    mes_col = func.substr(Contribuicao.data_competencia, 1, 2)
    stmt = (
        select(Contribuicao)
        .where(Contribuicao.job_id == id_uuid)
        .order_by(ano_col.asc(), mes_col.asc())
    )
    return list(db.scalars(stmt).all())


def listar_jobs_por_advogado(
    db: Session,
    advogado_id: uuid.UUID | str,
    limit: int = 50,
) -> list[JobExtracao]:
    """Lista os trabalhos de extração pertencentes a um advogado.

    Args:
        db: Sessão ativa do SQLAlchemy.
        advogado_id: Identificador do advogado proprietário.
        limit: Quantidade máxima de registros retornados.

    Returns:
        Lista de JobExtracao ordenados pela data de criação decrescente.
    """
    id_uuid = advogado_id if isinstance(advogado_id, uuid.UUID) else uuid.UUID(str(advogado_id))
    stmt = (
        select(JobExtracao)
        .options(joinedload(JobExtracao.cliente))
        .where(JobExtracao.advogado_id == id_uuid)
        .order_by(JobExtracao.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def obter_contribuicoes_por_cliente(
    db: Session,
    cliente_id: uuid.UUID | str,
) -> list[Contribuicao]:
    """Retorna todas as contribuições previdenciárias de um cliente específico.

    Args:
        db: Sessão ativa do SQLAlchemy.
        cliente_id: Identificador único do cliente.

    Returns:
        Lista de Contribuicao ordenadas cronologicamente de forma ascendente.
    """
    id_uuid = cliente_id if isinstance(cliente_id, uuid.UUID) else uuid.UUID(str(cliente_id))
    ano_col = func.substr(Contribuicao.data_competencia, 4, 4)
    mes_col = func.substr(Contribuicao.data_competencia, 1, 2)
    stmt = (
        select(Contribuicao)
        .where(Contribuicao.cliente_id == id_uuid)
        .order_by(ano_col.asc(), mes_col.asc())
    )
    return list(db.scalars(stmt).all())
