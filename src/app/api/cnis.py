from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.templating import Jinja2Templates

from app.api.auth import obter_usuario_logado
from app.core.parser import extrair_dados_pdf
from app.database.connection import get_supabase

router = APIRouter(prefix="/cnis", tags=["Processamento CNIS"])
templates = Jinja2Templates(directory="src/app/web/templates")


def processar_upload_cnis(arquivo_file, nome_arquivo: str, user_id: str):
    """"""
    supabase = get_supabase()

    try:
        dados = extrair_dados_pdf(arquivo_file)
        supabase.table("extractions_logs").insert(
            {"user_id": user_id, "file_name": nome_arquivo, "status": "sucesso"}
        ).execute()

        return dados
    except Exception as e:
        supabase.table("extractions_logs").insert(
            {"user_id": user_id, "file_name": nome_arquivo, "status": "erro", "message": str(e)}
        ).execute()
        raise e


@router.post("/extrair")
async def extrair_documento_cnis(arquivo: UploadFile = File(...), usuario=Depends(obter_usuario_logado)):
    if arquivo.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são aceitos.")

    try:
        dados = processar_upload_cnis(arquivo.file, arquivo.filename, usuario.id)
        return {"status": "sucesso", "nome_arquivo": arquivo.filename, "dados": dados}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar o PDF: {str(e)}")


@router.post("/extrair-html")
async def extrair_documento_cnis_html(
    request: Request, arquivo: UploadFile = File(...), usuario=Depends(obter_usuario_logado)
):
    if arquivo.content_type != "application/pdf":
        return '<div class="p-4 bg-red-100 text-red-700">Apenas arquivos PDF.</div>'

    try:
        # Chama o MESMO maestro
        dados = processar_upload_cnis(arquivo.file, arquivo.filename, usuario.id)

        return templates.TemplateResponse(request=request, name="tabela_resultados.html", context={"dados": dados})
    except Exception as e:
        return f'<div class="p-4 bg-red-100 text-red-700">Erro ao processar: {str(e)}</div>'
