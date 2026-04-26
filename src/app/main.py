"""Parse Main."""

from fastapi import FastAPI

from app.api import auth, cnis, web

app = FastAPI(title="Parse API")

app.include_router(cnis.router)
app.include_router(auth.router)
app.include_router(web.router)
