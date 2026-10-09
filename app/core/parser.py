"""Parser para extração de dados estruturados de extratos CNIS."""

import logging
import re
from pathlib import Path

import pdfplumber

from app.core.schemas import CnisCompetencia

_LOGGER = logging.getLogger(__name__)

RE_DATA = re.compile(r"^\d{2}/\d{4}$")
RE_VALOR_BR = re.compile(r"^(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2}$")


def processar_linhas_cnis(linhas: list[str]) -> list[CnisCompetencia]:
    """Processa linhas de texto do CNIS extraindo pares de competência e valor.

    O extrato previdenciário frequentemente organiza as remunerações em até 3
    colunas paralelas, gerando múltiplos pares sequenciais de data e valor em
    uma única linha textual.

    Args:
        linhas: Lista de strings com o conteúdo textual bruto das páginas.

    Returns:
        Lista de competências estruturadas e validadas.
    """
    resultados: list[CnisCompetencia] = []

    for linha in linhas:
        partes = linha.split()
        if not partes or not RE_DATA.match(partes[0]):
            continue

        _LOGGER.debug("Processando partes filtradas: %s", partes)
        i = 0
        while i + 1 < len(partes):
            competencia = partes[i]
            valor_candidato = partes[i + 1]

            if RE_DATA.match(competencia) and RE_VALOR_BR.match(valor_candidato):
                try:
                    item = CnisCompetencia(
                        data_competencia=competencia,
                        valor=valor_candidato,
                    )
                    resultados.append(item)
                except (ValueError, TypeError) as exc:
                    _LOGGER.debug(
                        "Falha na validação do par (%s, %s): %s",
                        competencia,
                        valor_candidato,
                        exc,
                    )
                i += 2
            else:
                break

    resultados.sort(key=_chave_ordenacao_competencia)
    return resultados


def _chave_ordenacao_competencia(item: CnisCompetencia) -> tuple[int, int]:
    """Retorna tupla (ano, mês) para ordenação cronológica de competências.

    Args:
        item: Objeto CnisCompetencia a ser ordenado.

    Returns:
        Tupla (ano, mês) inteiros para ordenação cronológica correta.
    """
    partes = item.data_competencia.split("/")
    if len(partes) == 2:
        try:
            return int(partes[1]), int(partes[0])
        except ValueError:
            pass
    return (0, 0)


def extrair_dados_pdf(caminho_arquivo: Path | str) -> list[CnisCompetencia]:
    """Extrai texto de todas as páginas do PDF e processa as competências.

    Args:
        caminho_arquivo: Caminho do arquivo PDF do extrato CNIS a ser lido.

    Returns:
        Lista de competências identificadas no documento.
    """
    caminho = Path(caminho_arquivo)
    todas_as_linhas: list[str] = []

    with pdfplumber.open(caminho) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text()
            if texto:
                todas_as_linhas.extend(texto.split("\n"))

    return processar_linhas_cnis(todas_as_linhas)
