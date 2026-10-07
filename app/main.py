"""Parse Api+Web Main."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from alembic import command
from alembic.config import Config
from app.api import auth, cnis, web

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
    yield


# Cria o objeto app que o FastAPI usa.
app = FastAPI(title="Parse API", lifespan=lifespan)

# Adiciona os routers do app
app.include_router(cnis.router)
app.include_router(auth.router)
app.include_router(web.router)
