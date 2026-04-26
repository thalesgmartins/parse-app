from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api.auth import obter_usuario_logado
from app.core.parser import extrair_dados_pdf
from app.database.connection import get_supabase
from app.database.repository import criar_cliente, salvar_contribuicoes

router = APIRouter(prefix="/cnis", tags=["Processamento CNIS"])
templates = Jinja2Templates(directory="src/app/web/templates")


def processar_upload_cnis(arquivo_file, nome_arquivo: str, cliente_id: str, advogado_id: str):
    """"""
    supabase = get_supabase()

    try:
        dados = extrair_dados_pdf(arquivo_file)
        salvar_contribuicoes(cliente_id, dados)

        supabase.table("extractions_logs").insert(
            {"user_id": advogado_id, "file_name": nome_arquivo, "status": "sucesso"}
        ).execute()

        return dados
    except Exception as e:
        supabase.table("extractions_logs").insert(
            {"user_id": advogado_id, "file_name": nome_arquivo, "status": "erro", "message": str(e)}
        ).execute()
        raise e


@router.post("/clientes")
async def cadastrar_novo_cliente(nome: str = Form(...), cpf: str = Form(None), usuario=Depends(obter_usuario_logado)):
    # Cria o cliente no banco
    criar_cliente(advogado_id=usuario.id, nome=nome, cpf=cpf)

    # Recarrega a página da dashboard automaticamente.
    # Usamos status_code 303 (See Other) que é o padrão da web para redirecionar após um POST.
    return RedirectResponse(url="/dashboard", status_code=303)


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
    request: Request,
    cliente_id: str = Form(...),
    arquivo: UploadFile = File(...),
    usuario=Depends(obter_usuario_logado),
):
    if arquivo.content_type != "application/pdf":
        return '<div class="p-4 bg-red-100 text-red-700">Apenas arquivos PDF.</div>'

    try:
        # Chama o MESMO maestro
        dados = processar_upload_cnis(arquivo.file, arquivo.filename, cliente_id, usuario.id)

        return templates.TemplateResponse(request=request, name="tabela_resultados.html", context={"dados": dados})
    except Exception as e:
        return f'<div class="p-4 bg-red-100 text-red-700">Erro ao processar: {str(e)}</div>'
