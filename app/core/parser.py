"""Parser para extração de dados estruturados de extratos CNIS."""

import logging
import re
from abc import ABC, abstractmethod
from pathlib import Path

import pdfplumber

from app.core.schemas import CnisCompetencia

_LOGGER = logging.getLogger(__name__)

RE_DATA = re.compile(r"^\d{2}/\d{4}$")
RE_DATA_COMPLETA = re.compile(r"^\d{2}/\d{2}/\d{4}$")
RE_VALOR_BR = re.compile(r"^(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2}$")

_TERMOS_CABECALHO_CNIS = (
    "CNIS",
    "CADASTRO NACIONAL DE INFORMA",
    "PREVIDENCIA SOCIAL",
    "PREVIDÊNCIA SOCIAL",
    "RELACOES PREVIDENCIARIAS",
    "RELAÇÕES PREVIDENCIÁRIAS",
    "INSS",
    "NIT",
    "REMUNERACOES",
    "REMUNERAÇÕES",
    "CONTRIBUIÇÕES",
    "CONTRIBUICOES",
    "SALÁRIO DE CONTRIBUIÇÃO",
    "SALARIO DE CONTRIBUICAO",
    "CONTRIBUINTE INDIVIDUAL",
)


class BaseExtractorStrategy(ABC):
    """Contrato abstrato para estratégias de extração de competências do CNIS."""

    @abstractmethod
    def tentar_extrair(
        self,
        partes: list[str],
        indice: int,
    ) -> tuple[CnisCompetencia, int] | None:
        """Tenta extrair uma competência a partir do índice atual na lista de tokens.

        Args:
            partes: Lista de tokens da linha textual.
            indice: Posição inicial para análise dos tokens.

        Returns:
            Tupla contendo a competência extraída e o próximo índice a ser processado,
            ou None caso o padrão não seja correspondente.
        """


class ContribuinteIndividualExtractorStrategy(BaseExtractorStrategy):
    """Estratégia para recolhimentos de Contribuinte Individual (Carnê/GPS).

    Identifica o padrão:
    [Competência MM/AAAA] [Data Pgto DD/MM/AAAA] [Contribuição R$]
    [Salário Contribuição R$] [Indicadores...]
    Extrai como valor o Salário de Contribuição (base de cálculo oficial da Previdência).
    """

    def tentar_extrair(
        self,
        partes: list[str],
        indice: int,
    ) -> tuple[CnisCompetencia, int] | None:
        """Extrai competência de contribuinte individual com salário de contribuição.

        Args:
            partes: Lista de tokens da linha.
            indice: Índice inicial da competência.

        Returns:
            Tupla (competência, próximo índice) se casar o padrão, None caso contrário.
        """
        n = len(partes)
        if indice + 3 >= n:
            return None

        comp = partes[indice]
        if not RE_DATA.match(comp):
            return None

        if (
            RE_DATA_COMPLETA.match(partes[indice + 1])
            and RE_VALOR_BR.match(partes[indice + 2])
            and RE_VALOR_BR.match(partes[indice + 3])
        ):
            salario_base = partes[indice + 3]
            indicadores: list[str] = []
            proximo = indice + 4
            while proximo < n and not RE_DATA.match(partes[proximo]):
                indicadores.append(partes[proximo])
                proximo += 1

            item = CnisCompetencia(
                data_competencia=comp,
                valor=salario_base,
                origem_vinculo="Contribuinte Individual / Carnê",
                indicadores=indicadores,
            )
            return item, proximo

        return None


class AgrupamentoContratantesExtractorStrategy(BaseExtractorStrategy):
    """Estratégia para cooperativas e agrupamento de contratantes.

    Identifica linhas com competência seguida de CNPJ/identificadores, forma de
    prestação de serviço e o valor da remuneração informada pela tomadora.
    """

    def tentar_extrair(
        self,
        partes: list[str],
        indice: int,
    ) -> tuple[CnisCompetencia, int] | None:
        """Extrai competência de agrupamento de contratantes ou cooperativas.

        Args:
            partes: Lista de tokens da linha.
            indice: Índice inicial da competência.

        Returns:
            Tupla (competência, próximo índice) se casar o padrão, None caso contrário.
        """
        n = len(partes)
        if indice + 2 >= n:
            return None

        comp = partes[indice]
        if not RE_DATA.match(comp):
            return None

        posicao_valor: int | None = None
        j = indice + 1
        while j < n and not RE_DATA.match(partes[j]):
            if RE_VALOR_BR.match(partes[j]):
                posicao_valor = j
                break
            j += 1

        if posicao_valor is not None and posicao_valor > indice + 1:
            valor_remuneracao = partes[posicao_valor]
            indicadores: list[str] = []
            proximo = posicao_valor + 1
            while proximo < n and not RE_DATA.match(partes[proximo]):
                indicadores.append(partes[proximo])
                proximo += 1

            item = CnisCompetencia(
                data_competencia=comp,
                valor=valor_remuneracao,
                origem_vinculo="Cooperativa / Contratante",
                indicadores=indicadores,
            )
            return item, proximo

        return None


class CltRemuneracaoExtractorStrategy(BaseExtractorStrategy):
    """Estratégia padrão para vínculos empregatícios (CLT / Estatutário).

    Identifica o padrão:
    [Competência MM/AAAA] [Remuneração R$] [Indicadores...]
    Suporta colunas paralelas dispostas lado a lado na mesma linha do relatório.
    """

    def tentar_extrair(
        self,
        partes: list[str],
        indice: int,
    ) -> tuple[CnisCompetencia, int] | None:
        """Extrai competência CLT ou emprego padrão.

        Args:
            partes: Lista de tokens da linha.
            indice: Índice inicial da competência.

        Returns:
            Tupla (competência, próximo índice) se casar o padrão, None caso contrário.
        """
        n = len(partes)
        if indice + 1 >= n:
            return None

        comp = partes[indice]
        if not RE_DATA.match(comp):
            return None

        valor_candidato = partes[indice + 1]
        if RE_VALOR_BR.match(valor_candidato):
            indicadores: list[str] = []
            proximo = indice + 2
            while proximo < n and not RE_DATA.match(partes[proximo]):
                indicadores.append(partes[proximo])
                proximo += 1

            item = CnisCompetencia(
                data_competencia=comp,
                valor=valor_candidato,
                origem_vinculo="CLT / Emprego",
                indicadores=indicadores,
            )
            return item, proximo

        return None


class CnisParserPipeline:
    """Coordenador do pipeline de extração de tabelas do extrato CNIS."""

    def __init__(self, estrategias: list[BaseExtractorStrategy] | None = None) -> None:
        """Inicializa o pipeline com a cadeia de estratégias em ordem de prioridade.

        Args:
            estrategias: Lista opcional de estratégias de extração personalizadas.
        """
        self._estrategias = estrategias or [
            ContribuinteIndividualExtractorStrategy(),
            AgrupamentoContratantesExtractorStrategy(),
            CltRemuneracaoExtractorStrategy(),
        ]

    def extrair_linha(self, partes: list[str]) -> list[CnisCompetencia]:
        """Processa os tokens de uma linha buscando competências em qualquer padrão.

        Args:
            partes: Lista de tokens obtidos pela quebra de linha por espaços.

        Returns:
            Lista de competências estruturadas encontradas na linha.
        """
        resultados: list[CnisCompetencia] = []
        i = 0
        n = len(partes)

        while i < n:
            if not RE_DATA.match(partes[i]):
                i += 1
                continue

            casou = False
            for estrategia in self._estrategias:
                resultado = estrategia.tentar_extrair(partes, i)
                if resultado is not None:
                    item, proximo_i = resultado
                    resultados.append(item)
                    i = proximo_i
                    casou = True
                    break

            if not casou:
                i += 1

        return resultados


def validar_texto_cabecalho_cnis(texto: str) -> bool:
    """Verifica rapidamente se o texto inicial contém marcadores de um extrato CNIS.

    Args:
        texto: Conteúdo textual extraído da primeira página do documento.

    Returns:
        True se contiver marcadores oficiais do CNIS/INSS ou pares de competência.
    """
    if not texto or not texto.strip():
        return False
    texto_upper = texto.upper()
    if any(termo in texto_upper for termo in _TERMOS_CABECALHO_CNIS):
        return True
    return len(processar_linhas_cnis(texto.split("\n"))) > 0


def validar_cabecalho_cnis_rapido(caminho_arquivo: Path | str) -> bool:
    """Inspeciona apenas a primeira página do PDF para rejeição rápida (Fail-Fast).

    Evita processar dezenas de páginas em PDFs que não são extratos previdenciários.

    Args:
        caminho_arquivo: Caminho para o arquivo PDF no disco.

    Returns:
        True se a Página 1 apresentar estrutura compatível com o CNIS, False caso contrário.
    """
    caminho = Path(caminho_arquivo)
    if not caminho.exists():
        return False
    try:
        with pdfplumber.open(caminho) as pdf:
            if not pdf.pages:
                return False
            texto_pag1 = pdf.pages[0].extract_text() or ""
            return validar_texto_cabecalho_cnis(texto_pag1)
    except Exception as exc:
        _LOGGER.debug("Falha na pré-validação rápida da página 1 (%s): %s", caminho, exc)
        return False


def processar_linhas_cnis(linhas: list[str]) -> list[CnisCompetencia]:
    """Processa linhas de texto do CNIS extraindo competências em qualquer padrão.

    O extrato previdenciário pode organizar as remunerações ou salários de
    contribuição em múltiplas colunas paralelas, cobrindo tanto vínculos CLT
    quanto Contribuinte Individual e Cooperativas.

    Args:
        linhas: Lista de strings com o conteúdo textual bruto das páginas.

    Returns:
        Lista de competências estruturadas e validadas ordenadas cronologicamente.
    """
    pipeline = CnisParserPipeline()
    resultados: list[CnisCompetencia] = []

    for linha in linhas:
        partes = linha.split()
        if not partes:
            continue
        itens_linha = pipeline.extrair_linha(partes)
        if itens_linha:
            resultados.extend(itens_linha)

    resultados.sort(key=_chave_ordenacao_competencia)
    return resultados


def consolidar_competencias_maior_valor(
    competencias: list[CnisCompetencia],
) -> list[CnisCompetencia]:
    """Consolida competências mantendo a ocorrência de maior valor monetário.

    Em casos de vínculos concomitantes no mesmo mês/ano (ex: CLT simultâneo a
    Contribuinte Individual), preserva-se o registro de maior remuneração/salário
    para evitar tempo em dobro e subavaliação do cálculo de benefícios.

    Args:
        competencias: Lista de competências extraídas, podendo conter repetições.

    Returns:
        Lista ordenada cronologicamente contendo apenas uma competência por mês/ano.
    """
    mapa: dict[str, CnisCompetencia] = {}
    for item in competencias:
        chave = item.data_competencia
        if chave not in mapa or float(item.valor) > float(mapa[chave].valor):
            mapa[chave] = item

    resultado = list(mapa.values())
    resultado.sort(key=_chave_ordenacao_competencia)
    return resultado


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


def extrair_dados_pdf(
    caminho_arquivo: Path | str,
    consolidar: bool = False,
) -> list[CnisCompetencia]:
    """Extrai texto de todas as páginas do PDF e processa as competências.

    Realiza validação rápida (Fail-Fast) na primeira página para abortar
    imediatamente a leitura caso o documento não seja um extrato CNIS.

    Args:
        caminho_arquivo: Caminho do arquivo PDF do extrato CNIS a ser lido.
        consolidar: Se True, consolida competências concomitantes pelo maior valor.

    Returns:
        Lista de competências identificadas no documento.
    """
    caminho = Path(caminho_arquivo)
    todas_as_linhas: list[str] = []

    with pdfplumber.open(caminho) as pdf:
        if not pdf.pages:
            return []
        texto_pag1 = pdf.pages[0].extract_text() or ""
        if not validar_texto_cabecalho_cnis(texto_pag1):
            _LOGGER.info("Fail-Fast: Página 1 de %s não contém cabeçalho CNIS.", caminho.name)
            return []
        todas_as_linhas.extend(texto_pag1.split("\n"))

        for pagina in pdf.pages[1:]:
            texto = pagina.extract_text()
            if texto:
                todas_as_linhas.extend(texto.split("\n"))

    dados = processar_linhas_cnis(todas_as_linhas)
    if consolidar:
        return consolidar_competencias_maior_valor(dados)
    return dados

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
