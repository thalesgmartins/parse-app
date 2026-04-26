"""Parse Api+Web Main."""

from fastapi import FastAPI

from app.api import auth, cnis, web

# Cria o objeto app que o FastAPI usa.
app = FastAPI(title="Parse API")

# Adiciona os routers do app
app.include_router(cnis.router)
app.include_router(auth.router)
app.include_router(web.router)
