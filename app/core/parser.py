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


def extrair_dados_segurado(texto: str) -> tuple[str | None, str | None]:
    """Extrai nome e CPF do segurado a partir do texto do extrato CNIS.

    Args:
        texto: Conteúdo textual das páginas iniciais do documento CNIS.

    Returns:
        Tupla (nome, cpf) caso identificados no padrão oficial do INSS.
    """
    cpf: str | None = None
    nome: str | None = None

    m_cpf = re.search(
        r"(?:CPF|C\.P\.F\.)(?:\s*do\s*Filiado)?[:\s]+(\d{3}\.\d{3}\.\d{3}-\d{2}|\d{11})",
        texto,
        re.IGNORECASE,
    )
    if m_cpf:
        cpf_bruto = m_cpf.group(1).strip()
        if len(cpf_bruto) == 11 and "." not in cpf_bruto:
            cpf = f"{cpf_bruto[:3]}.{cpf_bruto[3:6]}.{cpf_bruto[6:9]}-{cpf_bruto[9:]}"
        else:
            cpf = cpf_bruto

    m_nome = re.search(
        r"(?:Nome|Nome\s*do\s*Filiado|Nome\s*do\s*Trabalhador)[:\s]+"
        r"([A-Za-zÀ-ÖØ-öø-ÿ\s\.\'\-]+?)"
        r"(?=\s+(?:Data de nascimento|Nome da mãe|NIT|CPF|Data|Seq\.)|\n|\r|$)",
        texto,
        re.IGNORECASE,
    )
    if m_nome:
        candidato = m_nome.group(1).strip()
        if len(candidato) >= 3 and not re.match(r"^\d+$", candidato):
            nome = candidato

    return nome, cpf


def extrair_metadados_pdf(caminho_arquivo: Path | str) -> tuple[str | None, str | None]:
    """Extrai nome e CPF do segurado inspecionando o cabeçalho do PDF.

    Args:
        caminho_arquivo: Caminho do arquivo PDF do extrato CNIS a ser lido.

    Returns:
        Tupla contendo (nome, cpf) do segurado identificado.
    """
    caminho = Path(caminho_arquivo)
    try:
        with pdfplumber.open(caminho) as pdf:
            texto_inicial = ""
            for pagina in pdf.pages[:2]:
                texto_pag = pagina.extract_text()
                if texto_pag:
                    texto_inicial += "\n" + texto_pag

        return extrair_dados_segurado(texto_inicial)
    except Exception as exc:
        _LOGGER.debug("Não foi possível extrair metadados do PDF %s: %s", caminho, exc)
        return None, None
