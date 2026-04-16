"""Parse Main."""

import io
import os
import shutil

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.utils.pdf import extrair_dados_pdf
from backend.utils.tabela import convert_dict_into_csv


app = FastAPI(title="Parse API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/extrair/csv")
async def gerar_csv_do_pdf(arquivo: UploadFile = File(...)):

    # Valida se o arquivo é um pdf
    if not arquivo.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Envie um PDF.")

    # Cria um arquivo temporario pro pdfplumber conseguir ler
    caminho_temporario = f"temp_{arquivo.filename}"
    try:
        with open(caminho_temporario, "wb") as buffer_disco:
            shutil.copyfileobj(arquivo.file, buffer_disco)
        
        # Chamando a função que veio do módulo utils
        dados = extrair_dados_pdf(caminho_temporario)
        
        if not dados:
            raise HTTPException(status_code=400, detail="Nenhum dado válido encontrado no PDF.")
        
    finally:
        if os.path.exists(caminho_temporario):
            os.remove(caminho_temporario)
    
    arquivo_memoria = io.StringIO()
    convert_dict_into_csv(dados, arquivo_memoria)

    arquivo_memoria.seek(0)

    # Enviando para o navegador
    return StreamingResponse(
        arquivo_memoria, 
        media_type="text/csv", 
        headers={
            # Esse header avisa o navegador: "Ei, não abra isso como texto, abra a janela de Salvar Como!"
            "Content-Disposition": f"attachment; filename=parse_extrato.csv"
        }
    )

# Código para iniciar o servidor via terminal usando `uv run parse_backend`
def start():
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    start()