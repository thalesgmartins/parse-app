"""Utilitário pra extrair os dados de documentos CNIS."""
import logging

import pdfplumber


_LOGGER = logging.getLogger(__name__)

def eh_numero(valor_string: str) -> bool:
    limpo = valor_string.replace('.','').replace(',','.')
    try:
        float(limpo)
        return True
    except ValueError:
        return False

def extrair_tabela_pagina(pagina):
    """Extrai a tabela de contribuições de uma página do PDF."""
    return pagina.extract_table()

def extrair_dados_pdf(caminho_arquivo) -> dict:
    """Carrega um arquivo PDF, extrai os dados de todas as páginas e retorna o resultado."""
    dados_extraidos = {}

    with pdfplumber.open(caminho_arquivo) as pdf:


        # Como a formatação do CNIS não é em tabela, rodamos todas as páginas extraindo os textos. 
        # A variável 'pagina' é um objeto do tipo pdfplumber.Page
        for pagina in pdf.pages:
            
            # Tem sido a forma mais consistente de pegar dados, vai puxar uma nega string com textos.
            texto = pagina.extract_text()

            # Se não tem texto na página simplesmente não tem por que continuar processando.
            if not texto:
                continue

            # Separamos os textos em linhas pra conseguir filtrar só as competências.
            linhas = texto.split("\n")

            for linha in linhas:
                if len(linha) <= 0:
                    continue

                if linha[2] != '/':
                    continue
                
                partes = linha.split()

                if len(partes[0]) != 7:
                    continue

                if not eh_numero(partes[1]):
                    continue

                dados_extraidos[partes[0]] = partes [3]
                    
    _LOGGER.debug(dados_extraidos)
    return dados_extraidos



if __name__ == "__main__":
    """Teste local pra caso executar localmente."""

    # Como o logger não foi inicializdo na main, criamos uma config básica pra ele.
    logging.basicConfig(level=logging.INFO)

    # Ponto de entrada a função pra extrar os dados.
    extrair_dados_pdf("teste.pdf")

