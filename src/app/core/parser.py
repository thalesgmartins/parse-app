"""Parser pra extrair os dados de documentos CNIS."""

import logging
from pathlib import Path

import pdfplumber

from app.core.schemas import CnisCompetencia

_LOGGER = logging.getLogger(__name__)


def validar_formato_data(texto: str) -> bool:
    """Verifica padrão XX/XXXX sem estourar o índice."""
    return len(texto) == 7 and texto[2] == "/"


def extrair_dados_pdf(caminho_arquivo) -> dict:
    """Carrega um arquivo PDF, extrai os dados de todas as páginas e retorna o resultado."""
    dados_extraidos = {}

    with pdfplumber.open(caminho_arquivo) as pdf:
        # Como a formatação do CNIS não é em tabela, rodamos todas as páginas extraindo os textos.
        # A variável 'pagina' é um objeto do tipo pdfplumber.Page
        for pagina in pdf.pages:
            # Tem sido a forma mais consistente de pegar dados, vai puxar uma mega string com textos.
            texto = pagina.extract_text()

            # Se não tem texto na página simplesmente não tem por que continuar processando.
            if not texto:
                continue

            # Separamos os textos em linhas pra conseguir filtrar só as competências.
            linhas = texto.split("\n")

            # Varre todas as linhas filtrando e buscando os valores desejados
            for linha in linhas:
                # Se for uma string vazia
                if not linha:
                    continue

                # Se a primeira informação não for uma data
                if not eh_data(linha):
                    continue

                #
                # A partir daqui sabemos que temos apenas informações que começam com datas, mas elas podem ser tanto
                # Remuneração Apurada quando Valores por Competência.
                #

                # Dividimos a linha em espaços para filtrar ainda mais.
                partes = linha.split()

                # Confere o padrão de data, deve ter 7 caracteres
                # EX: 04/2026    <--- 7 caracteres
                if len(partes[0]) != 7:
                    continue

                # Se estiver no padrão, o segundo dado sempre vai ser um número.
                if not eh_numero(partes[1]):
                    continue

                # Se chegou até aqui é por que temos a linha correta, então
                # adiciona os valores no dicionário de dados extraídos
                dados_extraidos[partes[0]] = partes[3]

    _LOGGER.debug(dados_extraidos)
    return dados_extraidos
