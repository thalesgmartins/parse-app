# """Parse Main."""

# import io
# import os
# import shutil

# from fastapi import FastAPI, UploadFile, File, Header, HTTPException
# from fastapi.responses import StreamingResponse
# from fastapi.middleware.cors import CORSMiddleware

# from backend.utils.banco import supabase
# from backend.utils.pdf import extrair_dados_pdf
# from backend.utils.tabela import convert_dict_into_csv

# app = FastAPI(title="Parse API")


# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:3000"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


# @app.post("/api/extrair/csv")
# async def gerar_csv_do_pdf(
#     arquivo: UploadFile = File(...),
#     authorization: str = Header(...)
# ):
#     token = authorization.replace("Bearer ", "")

#     # 1. Valida o token e pegaa o usuário
#     try:
#         usuario = supabase.auth.get_user(token)
#         user_id = usuario.user.id
#     except:
#         raise HTTPException(status_code=401, detail="Token Inválido")

#     # 2. Verifica a quota
#     perfil = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
#     usado = perfil.data["used_quota"]
#     limite = perfil.data["quota_limit"]

#     if usado >= limite:
#         raise HTTPException(status_code=403, detail="Quota esgotada")

#     # 3. Valida se o arquivo é um pdf
#     if not arquivo.filename.endswith(".pdf"):
#         raise HTTPException(status_code=400, detail="Envie um PDF.")

#     # 4. Salva no disco temporariamente
#     caminho_temporario = f"temp_{arquivo.filename}"
#     try:
#     	with open(caminho_temporario, "wb") as buffer_disco:
#             shutil.copyfileobj(arquivo.file, buffer_disco)

#             dados = extrair_dados_pdf(caminho_temporario)

#             if not dados:
#                 raise ValueError("Nenhum dado válido encontrado no PDF.")
#             status, message = "sucesso", None

#     except Exception as e:
#         status, message = "erro", str(e)
#         dados = None

#     finally:
#         if os.path.exists(caminho_temporario):
#             os.remove(caminho_temporario)

#     # 6. Salva o log independente de sucesso ou erro
#     supabase.table("extractions_logs").insert({
#         "user_id": user_id,
#         "file_name": arquivo.filename,
#         "status": status,
#         "message": message
#     }).execute()

#     # 7. Incrementa quota e retorna erro se a extração falhou
#     if status == "erro":
#         raise HTTPException(status_code=422, detail=message)

#     supabase.table("profiles").update({
#         "used_quota": usado + 1
#     }).eq("id", user_id).execute()

#     # Gera um CSV em memória e retorna
#     arquivo_csv = io.StringIO()
#     convert_dict_into_csv(dados, arquivo_csv)
#     arquivo_csv.seek(0)

#     # Enviando para o navegador
#     return StreamingResponse(
#         arquivo_csv,
#         media_type="text/csv",
#         headers={
#             # Esse header avisa o navegador: "Ei, não abra isso como texto, abra a janela de Salvar Como!"
#             "Content-Disposition": f"attachment; filename=parse_extrato.csv"
#         }
#     )


# # Código para iniciar o servidor via terminal usando `uv run parse_backend`
# def start():
#     import uvicorn
#     uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)


# if __name__ == "__main__":
#     """Start Parse Backend."""
#     start()
