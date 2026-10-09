"""Worker para processamento assíncrono e resiliente de extratos CNIS."""

import logging
import os
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.parser import extrair_dados_pdf, extrair_metadados_pdf
from app.database.repository import (
    bloquear_job_para_processamento,
    concluir_job,
    falhar_job,
    obter_cliente_por_id,
    obter_job_por_id,
    obter_ou_criar_cliente_por_dados,
    obter_proximo_job,
    registrar_log_extracao,
    salvar_ou_atualizar_contribuicoes,
)
from app.database.session import SessionLocal

_LOGGER = logging.getLogger(__name__)


def processar_job_extracao(
    job_id: uuid.UUID | str,
    db: Session | None = None,
) -> bool:
    """Processa um job de extração de PDF pendente na fila.

    Executa o parser de competências do CNIS, persiste os registros
    no PostgreSQL vinculados ao cliente/job e remove o arquivo temporário
    do disco após a conclusão (sucesso ou falha).

    Args:
        job_id: Identificador único do trabalho de extração.
        db: Sessão opcional do SQLAlchemy (se omitida, uma nova é criada).

    Returns:
        True se o job foi processado com sucesso, False se já bloqueado ou falhou.

    Raises:
        ValueError: Se o job não existir ou os dados forem inválidos.
    """
    id_uuid = job_id if isinstance(job_id, uuid.UUID) else uuid.UUID(str(job_id))
    owns_session = db is None
    session = SessionLocal() if owns_session else db

    caminho_arquivo: Path | None = None

    try:
        job = bloquear_job_para_processamento(session, id_uuid)
        if not job:
            _LOGGER.info("Job %s já bloqueado ou não está pendente.", id_uuid)
            return False

        if job.caminho_arquivo_temp:
            caminho_arquivo = Path(job.caminho_arquivo_temp)

        if not caminho_arquivo or not caminho_arquivo.exists():
            raise FileNotFoundError(
                f"Arquivo temporário {caminho_arquivo} não encontrado no disco."
            )

        dados = extrair_dados_pdf(caminho_arquivo)
        nome_segurado, cpf_segurado = extrair_metadados_pdf(caminho_arquivo)

        cliente = None
        if job.cliente_id:
            cliente = obter_cliente_por_id(session, job.cliente_id)

        if not cliente:
            cliente = obter_ou_criar_cliente_por_dados(
                db=session,
                advogado_id=job.advogado_id,
                nome=nome_segurado,
                cpf=cpf_segurado,
                nome_arquivo=job.nome_arquivo,
            )
            job.cliente_id = cliente.id
            session.commit()
            session.refresh(job)

        salvar_ou_atualizar_contribuicoes(
            db=session,
            cliente_id=cliente.id,
            lista=dados,
            job_id=job.id,
        )

        registrar_log_extracao(
            db=session,
            advogado_id=job.advogado_id,
            nome_arquivo=job.nome_arquivo,
            status="sucesso",
        )

        concluir_job(
            db=session,
            job_id=job.id,
            total_competencias=len(dados),
        )
        _LOGGER.info("Job %s concluído: %d competências.", id_uuid, len(dados))
        return True

    except Exception as exc:
        _LOGGER.error("Falha ao processar job %s: %s", id_uuid, exc)
        job_falha = obter_job_por_id(session, id_uuid)
        if job_falha:
            registrar_log_extracao(
                db=session,
                advogado_id=job_falha.advogado_id,
                nome_arquivo=job_falha.nome_arquivo,
                status="erro",
                mensagem_erro=str(exc),
            )
            falhar_job(session, id_uuid, mensagem_erro=str(exc))
        return False

    finally:
        if caminho_arquivo and caminho_arquivo.exists():
            try:
                os.unlink(caminho_arquivo)
                _LOGGER.info("Arquivo temporário removido: %s", caminho_arquivo)
            except OSError as err:
                _LOGGER.error("Erro ao deletar arquivo temporário %s: %s", caminho_arquivo, err)

        if owns_session:
            session.close()


def processar_proximo_job_pendente(db: Session | None = None) -> bool:
    """Busca e executa o próximo job disponível na fila com SKIP LOCKED.

    Args:
        db: Sessão opcional do SQLAlchemy.

    Returns:
        True se algum job foi processado, False se a fila estiver vazia.
    """
    owns_session = db is None
    session = SessionLocal() if owns_session else db

    try:
        job = obter_proximo_job(session)
        if not job:
            return False
        return processar_job_extracao(job.id, session)
    finally:
        if owns_session:
            session.close()
