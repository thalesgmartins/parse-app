"""Rotas para processamento e extração de extratos CNIS."""

import shutil
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.auth import obter_usuario_logado
from app.core.config import UPLOAD_DIR
from app.database.models import Advogado
from app.database.repository import (
    criar_cliente,
    criar_job_extracao,
    obter_contribuicoes_por_job,
    obter_job_por_id,
)
from app.database.session import get_db
from app.services.worker import processar_job_extracao

router = APIRouter(prefix="/cnis", tags=["Processamento CNIS"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "web" / "templates")


@router.post("/clientes")
async def cadastrar_novo_cliente(
    nome: Annotated[str, Form()],
    usuario: Annotated[Advogado, Depends(obter_usuario_logado)],
    db: Annotated[Session, Depends(get_db)],
    cpf: Annotated[str | None, Form()] = None,
) -> RedirectResponse:
    """Cadastra um novo cliente vinculado ao advogado logado."""
    criar_cliente(db=db, advogado_id=usuario.id, nome=nome, cpf=cpf)
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/extrair")
async def extrair_documento_cnis(
    arquivo: Annotated[UploadFile, File()],
    usuario: Annotated[Advogado, Depends(obter_usuario_logado)],
    db: Annotated[Session, Depends(get_db)],
    background_tasks: BackgroundTasks,
    cliente_id: Annotated[str | None, Form()] = None,
) -> dict:
    """Enfileira o extrato CNIS para processamento assíncrono via JSON API."""
    nome_original = arquivo.filename or "extrato.pdf"
    content_type = arquivo.content_type or ""

    if not nome_original.lower().endswith(".pdf") and content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Apenas arquivos no formato PDF são aceitos para análise do CNIS.",
        )

    job_id = uuid.uuid4()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    caminho_temp = UPLOAD_DIR / f"{job_id}.pdf"

    try:
        with open(caminho_temp, "wb") as buffer:
            shutil.copyfileobj(arquivo.file, buffer)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao salvar arquivo temporário no volume efêmero: {str(exc)}",
        ) from exc

    cli_uuid: uuid.UUID | None = None
    if cliente_id:
        try:
            cli_uuid = uuid.UUID(cliente_id)
        except ValueError:
            cli_uuid = None

    job = criar_job_extracao(
        db=db,
        job_id=job_id,
        advogado_id=usuario.id,
        nome_arquivo=nome_original,
        cliente_id=cli_uuid,
        caminho_arquivo_temp=str(caminho_temp),
    )

    background_tasks.add_task(processar_job_extracao, job_id=job.id)

    return {
        "status": "pending",
        "job_id": str(job.id),
        "nome_arquivo": job.nome_arquivo,
        "message": "Extrato CNIS enfileirado para processamento assíncrono.",
    }


@router.post("/extrair-html")
async def extrair_documento_cnis_html(
    request: Request,
    cliente_id: Annotated[str, Form()],
    arquivo: Annotated[UploadFile, File()],
    usuario: Annotated[Advogado, Depends(obter_usuario_logado)],
    db: Annotated[Session, Depends(get_db)],
    background_tasks: BackgroundTasks,
):
    """Enfileira o extrato CNIS e devolve o fragmento de polling HTMX imediato.

    Args:
        request: Objeto da requisição HTTP.
        cliente_id: Identificador único do cliente selecionado.
        arquivo: Arquivo PDF enviado no formulário multipart.
        usuario: Advogado autenticado via sessão/cookie.
        db: Sessão ativa do banco de dados relacional.
        background_tasks: Orquestrador de tarefas assíncronas do FastAPI.

    Returns:
        TemplateResponse contendo o fragmento de polling ou erro amigável.
    """
    nome_original = arquivo.filename or "extrato.pdf"
    content_type = arquivo.content_type or ""

    if not nome_original.lower().endswith(".pdf") and content_type != "application/pdf":
        return templates.TemplateResponse(
            request=request,
            name="tabela_resultados.html",
            context={"erro": "Apenas arquivos no formato PDF são aceitos para análise do CNIS."},
        )

    job_id = uuid.uuid4()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    caminho_temp = UPLOAD_DIR / f"{job_id}.pdf"

    try:
        with open(caminho_temp, "wb") as buffer:
            shutil.copyfileobj(arquivo.file, buffer)
    except Exception as exc:
        return templates.TemplateResponse(
            request=request,
            name="tabela_resultados.html",
            context={"erro": f"Erro ao persistir arquivo temporário no volume efêmero: {str(exc)}"},
        )

    cli_uuid: uuid.UUID | None = None
    if cliente_id:
        try:
            cli_uuid = uuid.UUID(cliente_id)
        except ValueError:
            cli_uuid = None

    job = criar_job_extracao(
        db=db,
        job_id=job_id,
        advogado_id=usuario.id,
        nome_arquivo=nome_original,
        cliente_id=cli_uuid,
        caminho_arquivo_temp=str(caminho_temp),
    )

    background_tasks.add_task(processar_job_extracao, job_id=job.id)

    return templates.TemplateResponse(
        request=request,
        name="progresso_extracao.html",
        context={"job": job},
    )


@router.get("/jobs/{job_id}")
async def obter_job_extracao_view(
    request: Request,
    job_id: uuid.UUID,
    usuario: Annotated[Advogado, Depends(obter_usuario_logado)],
    db: Annotated[Session, Depends(get_db)],
):
    """Retorna o status atual do job ou o fragmento HTML final para o HTMX.

    Args:
        request: Objeto da requisição HTTP.
        job_id: Identificador único do job.
        usuario: Advogado autenticado.
        db: Sessão ativa do banco de dados.

    Returns:
        TemplateResponse com progresso, tabela de resultados ou card de erro.

    Raises:
        HTTPException: Se o job não for encontrado ou não pertencer ao advogado.
    """
    job = obter_job_por_id(db, job_id)
    if not job or job.advogado_id != usuario.id:
        raise HTTPException(status_code=404, detail="Job de extração não encontrado.")

    accept = request.headers.get("accept", "")
    if "application/json" in accept and "text/html" not in accept:
        return {
            "id": str(job.id),
            "status": job.status,
            "nome_arquivo": job.nome_arquivo,
            "total_competencias": job.total_competencias,
            "mensagem_erro": job.mensagem_erro,
        }

    if job.status in ("pending", "processing"):
        return templates.TemplateResponse(
            request=request,
            name="progresso_extracao.html",
            context={"job": job},
        )

    if job.status == "completed":
        contribuicoes = obter_contribuicoes_por_job(db, job.id)
        return templates.TemplateResponse(
            request=request,
            name="tabela_resultados.html",
            context={"dados": contribuicoes},
        )

    return templates.TemplateResponse(
        request=request,
        name="tabela_resultados.html",
        context={"erro": job.mensagem_erro or "Erro no processamento do documento."},
    )


@router.get("/jobs/{job_id}/status")
async def obter_job_status_json(
    job_id: uuid.UUID,
    usuario: Annotated[Advogado, Depends(obter_usuario_logado)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Consulta o status e métricas de um job em formato JSON.

    Args:
        job_id: Identificador único do job.
        usuario: Advogado autenticado.
        db: Sessão ativa do banco de dados.

    Returns:
        Dicionário com o estado e metadados do processamento.

    Raises:
        HTTPException: Se o job não for encontrado ou não pertencer ao advogado.
    """
    job = obter_job_por_id(db, job_id)
    if not job or job.advogado_id != usuario.id:
        raise HTTPException(status_code=404, detail="Job de extração não encontrado.")

    return {
        "id": str(job.id),
        "status": job.status,
        "nome_arquivo": job.nome_arquivo,
        "total_competencias": job.total_competencias,
        "mensagem_erro": job.mensagem_erro,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }
