"""Parse Api+Web Main."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from app.api import auth, cnis, web
from app.core.limiter import limiter

VERMELHO = "\033[31m"
VERDE = "\033[32m"
AZUL = "\033[34m"
RESET = "\033[0m"

logging.basicConfig(
    level=logging.INFO,
    format=f"{VERDE}%(asctime)s{RESET} | {VERMELHO}%(levelname)s{RESET} | {AZUL}%(filename)s:%(lineno)d{RESET} | %(message)s",  # noqa: E501
)
_LOGGER = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Executa todas as migrações pendentes ao iniciar o serviço (exceto em testes)
    if not os.getenv("TESTING"):
        ini_path = BASE_DIR / "alembic.ini"
        if ini_path.exists():
            _LOGGER.info("Executando migrações do banco de dados com Alembic...")
            alembic_cfg = Config(str(ini_path))
            alembic_cfg.set_main_option("script_location", str(BASE_DIR / "alembic"))
            command.upgrade(alembic_cfg, "head")
            _LOGGER.info("Migrações concluídas com sucesso!")

            try:
                import asyncio

                from sqlalchemy import update

                from app.database.models import JobExtracao
                from app.database.session import SessionLocal
                from app.services.worker import processar_proximo_job_pendente

                with SessionLocal() as db:
                    stmt = (
                        update(JobExtracao)
                        .where(JobExtracao.status == "processing")
                        .values(status="pending")
                    )
                    resultado = db.execute(stmt)
                    db.commit()
                    if resultado.rowcount:
                        _LOGGER.info(
                            "Recuperados %d jobs de extração para a fila pendente.",
                            resultado.rowcount,
                        )

                        async def _processar_fila_recuperada():
                            while True:
                                processou = await asyncio.to_thread(processar_proximo_job_pendente)
                                if not processou:
                                    break

                        asyncio.create_task(_processar_fila_recuperada())
            except Exception as exc:
                _LOGGER.error("Erro ao verificar jobs pendentes na inicialização: %s", exc)
    yield


# Cria o objeto app que o FastAPI usa.
app = FastAPI(title="Parse API", lifespan=lifespan)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse | RedirectResponse:
    """Trata excesso de requisições devolvendo redirecionamento ou JSON 429.

    Args:
        request: Requisição HTTP recebida.
        exc: Exceção de limite de taxa disparada pelo slowapi.

    Returns:
        RedirectResponse se requisição web via navegador, ou JSONResponse 429.
    """
    if "text/html" in request.headers.get("accept", ""):
        return RedirectResponse(
            url="/login?erro=Muitas+tentativas+de+acesso.+Por+favor,+aguarde+1+minuto.",
            status_code=303,
        )
    return JSONResponse(
        status_code=429,
        content={"detail": "Limite de requisições excedido. Tente novamente mais tarde."},
    )


STATIC_DIR = Path(__file__).resolve().parent / "web" / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Adiciona os routers do app
app.include_router(cnis.router)
app.include_router(auth.router)
app.include_router(web.router)
