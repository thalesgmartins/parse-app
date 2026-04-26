from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["Frontend"])

templates = Jinja2Templates(directory="src/app/web/templates")


@router.get("/dashboard")
async def renderizar_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html")
