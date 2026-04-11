"""Utilitário pra extrair os dados do documento CNIS."""
import logging

import pdfplumber


_LOGGER = logging.getLogger(__name__)

def extract_pdf_data():
    pass



def abrir_pdf(caminho_arquivo: str):
    with pdfplumber.open(caminho_arquivo) as pdf

    pass

def extrair_dados_pdf(caminho_arquivo: str):




    dados_extraidos = []

    with pdfplumber.open(caminho_arquivo) as pdf:
        for pagina in pdf.pages:
            tabela = pagina.extract_table()
            if tabela:
                for linha in tabela:
                    dados_extraidos.append(linha)
    return dados_extraidos


if __name__ == "__main__":
    """Teste local pra caso executar localmente."""
    logging.basicConfig(level=logging.DEBUG)
    resultado = extrair_dados_pdf("backend/utils/teste.pdf")

    _LOGGER.info(resultado)

