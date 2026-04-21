"""Parser pra extrair os dados de documentos CNIS."""

import logging
from pathlib import Path

import pdfplumber

from app.core.schemas import CnisCompetencia

_LOGGER = logging.getLogger(__name__)


def validar_formato_data(texto: str) -> bool:
    """Verifica padrão XX/XXXX sem estourar o índice."""
    return len(texto) == 7 and texto[2] == "/"


def processar_linhas_cnis(linhas: list[str]) -> list[CnisCompetencia]:
    """Processa uma lista de strings em uma lista de Competências."""
    resultados = []

    for linha in linhas:
        # Separa a linha em espaços ou quebras (palavras)
        partes = linha.split()

        # Filtros básicos de segurança
        if len(partes) < 4 or not validar_formato_data(partes[0]):
            continue

        try:
            item = CnisCompetencia(data_competencia=partes[0], valor=partes[3])
            resultados.append(item)
        except (ValueError, IndexError) as e:
            _LOGGER.warning("Linha ignorada por erro de formato: %s -> %s", linha, e)
            continue

    return resultados


def extrair_dados_pdf(caminho_arquivo: Path) -> list[CnisCompetencia]:
    """Abre o arquivo e chama o processador de linhas."""
    todas_as_linhas = []

    with pdfplumber.open(caminho_arquivo) as pdf:
        # Como a formatação do CNIS não é em tabela, rodamos todas as páginas extraindo os textos.
        # A variável 'pagina' é um objeto do tipo pdfplumber.Page
        for pagina in pdf.pages:
            # Tem sido a forma mais consistente de pegar dados, vai puxar uma mega string com textos.
            texto = pagina.extract_text()

            if texto:
                # Separamos os textos em linhas pra conseguir filtrar só as competências.
                todas_as_linhas.extend(texto.split("\n"))

    return processar_linhas_cnis(todas_as_linhas)
