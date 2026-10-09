"""Rotas para processamento e extração de extratos CNIS."""

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
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.auth import obter_usuario_logado
from app.core.config import MAX_UPLOAD_SIZE_BYTES, UPLOAD_DIR
from app.database.models import Advogado
from app.database.repository import (
    criar_cliente,
    criar_job_extracao,
    obter_cliente_por_id,
    obter_contribuicoes_por_cliente,
    obter_contribuicoes_por_job,
    obter_job_por_id,
)
from app.database.session import get_db
from app.services.export import gerar_csv_contribuicoes
from app.services.worker import processar_job_extracao

router = APIRouter(prefix="/cnis", tags=["Processamento CNIS"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "web" / "templates")


def _salvar_arquivo_temporario_com_limite(
    arquivo: UploadFile,
    caminho_destino: Path,
    limite_bytes: int | None = None,
) -> None:
    """Grava o arquivo temporário em disco em blocos respeitando o limite máximo.

    Args:
        arquivo: Arquivo enviado via formulário multipart.
        caminho_destino: Caminho onde o arquivo será salvo.
        limite_bytes: Limite máximo em bytes permitido (opcional).

    Raises:
        ValueError: Se o tamanho do arquivo exceder o limite permitido.
    """
    limite = limite_bytes if limite_bytes is not None else MAX_UPLOAD_SIZE_BYTES
    total_gravado = 0
    bloco_tamanho = 64 * 1024  # 64 KB por bloco

    with open(caminho_destino, "wb") as buffer:
        while True:
            pedaco = arquivo.file.read(bloco_tamanho)
            if not pedaco:
                break
            total_gravado += len(pedaco)
            if total_gravado > limite:
                buffer.close()
                if caminho_destino.exists():
                    caminho_destino.unlink()
                limite_mb = max(1, limite // (1024 * 1024))
                raise ValueError(f"O arquivo excede o limite máximo permitido de {limite_mb} MB.")
            buffer.write(pedaco)


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
        _salvar_arquivo_temporario_com_limite(arquivo, caminho_temp)
    except ValueError as val_err:
        raise HTTPException(
            status_code=413,
            detail=str(val_err),
        ) from val_err
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
    arquivo: Annotated[UploadFile, File()],
    usuario: Annotated[Advogado, Depends(obter_usuario_logado)],
    db: Annotated[Session, Depends(get_db)],
    background_tasks: BackgroundTasks,
    cliente_id: Annotated[str | None, Form()] = None,
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
        _salvar_arquivo_temporario_com_limite(arquivo, caminho_temp)
    except ValueError as val_err:
        return templates.TemplateResponse(
            request=request,
            name="tabela_resultados.html",
            context={"erro": str(val_err)},
        )
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
        cliente = obter_cliente_por_id(db, job.cliente_id) if job.cliente_id else None
        if cliente:
            contribuicoes = obter_contribuicoes_por_cliente(db, cliente.id)
        else:
            contribuicoes = obter_contribuicoes_por_job(db, job.id)

        return templates.TemplateResponse(
            request=request,
            name="tabela_resultados.html",
            context={"dados": contribuicoes, "job": job, "cliente": cliente},
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


@router.get("/jobs/{job_id}/csv")
async def exportar_job_csv(
    job_id: uuid.UUID,
    usuario: Annotated[Advogado, Depends(obter_usuario_logado)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """Exporta as contribuições de um job concluído em formato CSV (PT-BR).

    Args:
        job_id: Identificador único do job de extração.
        usuario: Advogado autenticado.
        db: Sessão ativa do banco de dados.

    Returns:
        Response contendo arquivo CSV com cabeçalho attachment.

    Raises:
        HTTPException: Se o job não for encontrado, pertencer a outro advogado ou
            não estiver concluído.
    """
    job = obter_job_por_id(db, job_id)
    if not job or job.advogado_id != usuario.id:
        raise HTTPException(status_code=404, detail="Job de extração não encontrado.")

    if job.status != "completed":
        raise HTTPException(
            status_code=400,
            detail="O processamento do extrato ainda não foi concluído.",
        )

    if job.cliente_id:
        contribuicoes = obter_contribuicoes_por_cliente(db, job.cliente_id)
    else:
        contribuicoes = obter_contribuicoes_por_job(db, job.id)
    conteudo_csv = gerar_csv_contribuicoes(contribuicoes)
    nome_base = Path(job.nome_arquivo).stem or "extrato"
    nome_arquivo_csv = f"{nome_base}_contribuicoes.csv"

    return Response(
        content=conteudo_csv,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{nome_arquivo_csv}"',
        },
    )


@router.get("/clientes/{cliente_id}/csv")
async def exportar_cliente_csv(
    cliente_id: uuid.UUID,
    usuario: Annotated[Advogado, Depends(obter_usuario_logado)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """Exporta todas as contribuições previdenciárias de um cliente em formato CSV.

    Args:
        cliente_id: Identificador único do cliente.
        usuario: Advogado autenticado.
        db: Sessão ativa do banco de dados.

    Returns:
        Response contendo arquivo CSV com cabeçalho attachment.

    Raises:
        HTTPException: Se o cliente não existir ou pertencer a outro advogado.
    """
    cliente = obter_cliente_por_id(db, cliente_id)
    if not cliente or cliente.advogado_id != usuario.id:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")

    contribuicoes = obter_contribuicoes_por_cliente(db, cliente.id)
    conteudo_csv = gerar_csv_contribuicoes(contribuicoes)
    nome_sanitizado = cliente.nome.strip().replace(" ", "_").lower()
    nome_arquivo_csv = f"cnis_{nome_sanitizado}.csv"

    return Response(
        content=conteudo_csv,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{nome_arquivo_csv}"',
        },
    )


@router.get("/clientes/{cliente_id}/tabela")
async def obter_tabela_cliente_view(
    request: Request,
    cliente_id: uuid.UUID,
    usuario: Annotated[Advogado, Depends(obter_usuario_logado)],
    db: Annotated[Session, Depends(get_db)],
):
    """Renderiza a tabela de contribuições consolidadas de um cliente via HTMX.

    Args:
        request: Objeto da requisição HTTP.
        cliente_id: Identificador único do cliente.
        usuario: Advogado autenticado.
        db: Sessão ativa do banco de dados.

    Returns:
        TemplateResponse renderizando tabela_resultados.html.

    Raises:
        HTTPException: Se o cliente não existir ou pertencer a outro advogado.
    """
    cliente = obter_cliente_por_id(db, cliente_id)
    if not cliente or cliente.advogado_id != usuario.id:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")

    contribuicoes = obter_contribuicoes_por_cliente(db, cliente.id)
    return templates.TemplateResponse(
        request=request,
        name="tabela_resultados.html",
        context={"dados": contribuicoes, "cliente": cliente},
    )
