"""Parse Main."""

import os
import shutil

from fastapi import FastAPI, UploadFile, File, HTTPException

from backend.utils.pdf import extrair_dados_pdf


app = FastAPI(title="Parse-v1 API Modular")


@app.post("/api/extrair")
async def rota_extrair_documento(arquivo: UploadFile = File(...)):
    if not arquivo.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Envie um PDF.")

    caminho_temporario = f"temp_{arquivo.filename}"
    
    try:
        with open(caminho_temporario, "wb") as buffer:
            shutil.copyfileobj(arquivo.file, buffer)
        
        # Chamando a função que veio do módulo utils
        dados_processados = extrair_dados_pdf(caminho_temporario)
        
        return {
            "status": "sucesso",
            "linhas": len(dados_processados),
            "dados": dados_processados
        }

    except Exception as erro:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(erro)}")
    finally:
        if os.path.exists(caminho_temporario):
            os.remove(caminho_temporario)