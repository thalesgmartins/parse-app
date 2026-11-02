"""Rotas para renderização das páginas web com Jinja2."""

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.auth import obter_usuario_logado, usuario_possui_avatar
from app.database.models import Cliente, Contribuicao, JobExtracao
from app.database.repository import (
    contar_extracos,
    limpar_registros_vazios_advogado,
    listar_clientes,
    listar_jobs_por_advogado,
    obter_cliente_por_id,
    obter_contribuicoes_por_cliente,
    obter_contribuicoes_por_job,
    obter_job_por_id,
)
from app.database.session import get_db
from app.services.analytics import (
    MESES_LABELS,
    TETO_INSS_REFERENCIA,
    construir_painel_analise,
    formatar_moeda_br,
)
from app.services.quotas import listar_planos_comerciais, obter_resumo_quota

router = APIRouter(tags=["Frontend"])
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "web" / "templates"
templates = Jinja2Templates(directory=_TEMPLATES_DIR)
templates.env.filters["moeda_br"] = formatar_moeda_br


def _calcular_metricas_fila(jobs: list[JobExtracao]) -> dict[str, int]:
    """Calcula indicadores de progresso da fila de extrações para o dashboard."""
    total_jobs = len(jobs)
    concluidos = sum(1 for j in jobs if j.status == "completed")
    em_fila = sum(1 for j in jobs if j.status in ("pending", "processing"))
    falhas = sum(1 for j in jobs if j.status == "failed")
    taxa_conclusao = round((concluidos / total_jobs) * 100) if total_jobs > 0 else 100
    return {
        "total_jobs": total_jobs,
        "jobs_concluidos": concluidos,
        "jobs_em_andamento": em_fila,
        "jobs_falha": falhas,
        "taxa_conclusao": taxa_conclusao,
    }


def _selecionar_dados_analise(
    db: Session,
    advogado_id: uuid.UUID,
    clientes: list[Cliente],
    cliente_id_str: str | None,
    job_id_str: str | None,
) -> tuple[list[Contribuicao], Cliente | None, JobExtracao | None]:
    """Resolve quais contribuições exibir na tela de análise do CNIS."""
    if job_id_str:
        try:
            job = obter_job_por_id(db, uuid.UUID(job_id_str))
            if job and job.advogado_id == advogado_id:
                cli = obter_cliente_por_id(db, job.cliente_id) if job.cliente_id else None
                contribs = (
                    obter_contribuicoes_por_cliente(db, cli.id)
                    if cli
                    else obter_contribuicoes_por_job(db, job.id)
                )
                return contribs, cli, job
        except ValueError:
            pass

    if cliente_id_str:
        try:
            cli = obter_cliente_por_id(db, uuid.UUID(cliente_id_str))
            if cli and cli.advogado_id == advogado_id:
                contribs = obter_contribuicoes_por_cliente(db, cli.id)
                return contribs, cli, None
        except ValueError:
            pass

    for cli in clientes:
        if cli.contribuicoes:
            contribs = obter_contribuicoes_por_cliente(db, cli.id)
            return contribs, cli, None

    if clientes:
        primeiro = clientes[0]
        contribs = obter_contribuicoes_por_cliente(db, primeiro.id)
        return contribs, primeiro, None

    return [], None, None


@router.get("/")
async def rota_raiz(request: Request) -> RedirectResponse:
    """Redireciona o acesso raiz para o dashboard se autenticado, ou login.

    Args:
        request: Objeto da requisição HTTP contendo cookies de sessão.

    Returns:
        RedirectResponse com status 303 direcionando para a rota apropriada.
    """
    token = request.cookies.get("access_token")
    if token:
        return RedirectResponse(url="/dashboard", status_code=303)
    return RedirectResponse(url="/login", status_code=303)


@router.get("/dashboard", response_model=None)
async def renderizar_dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse | RedirectResponse:
    """Renderiza a Tela 2 (Dashboard Principal / Upload e Processamento).

    Args:
        request: Objeto da requisição HTTP.
        db: Sessão ativa do banco de dados relacional.

    Returns:
        TemplateResponse renderizando dashboard.html ou redirecionamento.
    """
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=303)

    try:
        usuario = await obter_usuario_logado(access_token=token, db=db)
        limpar_registros_vazios_advogado(db=db, advogado_id=usuario.id)
        clientes_do_advogado = listar_clientes(db=db, advogado_id=usuario.id)
        total_extracos = contar_extracos(db=db, advogado_id=usuario.id)
        jobs_do_advogado = listar_jobs_por_advogado(
            db=db,
            advogado_id=usuario.id,
        )
        metricas_fila = _calcular_metricas_fila(jobs_do_advogado)
        quota_resumo = obter_resumo_quota(db=db, advogado_id=usuario.id)
        planos_comerciais = listar_planos_comerciais()

        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "clientes": clientes_do_advogado,
                "usuario_nome": usuario.nome,
                "usuario_email": usuario.email,
                "usuario_schema": usuario.schema_name,
                "tem_avatar": usuario_possui_avatar(usuario.id),
                "avatar_url": usuario.avatar_url,
                "total_extracos": total_extracos,
                "jobs": jobs_do_advogado,
                "metricas_fila": metricas_fila,
                "quota": quota_resumo,
                "planos": planos_comerciais,
                "sucesso_plano": request.query_params.get("sucesso_plano"),
                "erro_plano": request.query_params.get("erro_plano"),
            },
        )
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)


@router.get("/analise", response_model=None)
@router.get("/estatisticas", response_model=None)
async def renderizar_analise_cnis(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    cliente_id: str | None = None,
    job_id: str | None = None,
) -> HTMLResponse | RedirectResponse:
    """Renderiza a Tela 3 (Estatísticas e Resultados / Análise do CNIS).

    Args:
        request: Objeto da requisição HTTP.
        db: Sessão ativa do banco de dados relacional.
        cliente_id: UUID opcional do cliente a ser analisado.
        job_id: UUID opcional do job de extração a ser analisado.

    Returns:
        TemplateResponse renderizando analise.html ou redirecionamento.
    """
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=303)

    try:
        usuario = await obter_usuario_logado(access_token=token, db=db)
        limpar_registros_vazios_advogado(db=db, advogado_id=usuario.id)
        clientes_do_advogado = listar_clientes(db=db, advogado_id=usuario.id)
        total_extracos = contar_extracos(db=db, advogado_id=usuario.id)
        jobs_do_advogado = listar_jobs_por_advogado(
            db=db,
            advogado_id=usuario.id,
        )

        contribuicoes, cliente_ativo, job_ativo = _selecionar_dados_analise(
            db=db,
            advogado_id=usuario.id,
            clientes=clientes_do_advogado,
            cliente_id_str=cliente_id,
            job_id_str=job_id,
        )
        painel = construir_painel_analise(contribuicoes)
        quota_resumo = obter_resumo_quota(db=db, advogado_id=usuario.id)
        planos_comerciais = listar_planos_comerciais()

        return templates.TemplateResponse(
            request=request,
            name="analise.html",
            context={
                "usuario_nome": usuario.nome,
                "usuario_email": usuario.email,
                "usuario_schema": usuario.schema_name,
                "tem_avatar": usuario_possui_avatar(usuario.id),
                "avatar_url": usuario.avatar_url,
                "clientes": clientes_do_advogado,
                "jobs": jobs_do_advogado,
                "total_extracos": total_extracos,
                "cliente_ativo": cliente_ativo,
                "job_ativo": job_ativo,
                "painel": painel,
                "meses_labels": MESES_LABELS,
                "teto_inss": TETO_INSS_REFERENCIA,
                "quota": quota_resumo,
                "planos": planos_comerciais,
            },
        )
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)


@router.get("/login", response_model=None)
async def renderizar_login(
    request: Request,
    erro: str | None = None,
) -> HTMLResponse:
    """Renderiza a Tela 1 (Autenticação em Modo Escuro Split-Screen).

    Args:
        request: Objeto da requisição HTTP.
        erro: Mensagem de erro opcional recebida via query string.

    Returns:
        TemplateResponse renderizando login.html.
    """
    mensagem_erro = erro or request.query_params.get("erro")
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"erro": mensagem_erro},
    )
