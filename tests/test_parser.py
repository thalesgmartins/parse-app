"""Testes unitários para o motor de parsing de extratos CNIS."""

from app.core.parser import (
    extrair_dados_segurado,
    extrair_metadados_pdf,
    processar_linhas_cnis,
)


def test_processar_linhas_tres_competencias_na_mesma_linha() -> None:
    """Verifica a extração correta de múltiplas competências em colunas paralelas."""
    # Arrange
    linhas = [
        "10/2024 876,08 11/2024 1.775,06 12/2024 1.753,98",
    ]

    # Act
    resultado = processar_linhas_cnis(linhas)

    # Assert
    assert len(resultado) == 3
    assert resultado[0].data_competencia == "10/2024"
    assert resultado[0].valor == 876.08
    assert resultado[1].data_competencia == "11/2024"
    assert resultado[1].valor == 1775.06
    assert resultado[2].data_competencia == "12/2024"
    assert resultado[2].valor == 1753.98


def test_processar_linhas_uma_competencia_por_linha() -> None:
    """Valida a extração de competências dispostas individualmente por linha."""
    # Arrange
    linhas = [
        "01/2021 1.100,00",
        "02/2021 1.250,50",
    ]

    # Act
    resultado = processar_linhas_cnis(linhas)

    # Assert
    assert len(resultado) == 2
    assert resultado[0].data_competencia == "01/2021"
    assert resultado[0].valor == 1100.00
    assert resultado[1].data_competencia == "02/2021"
    assert resultado[1].valor == 1250.50


def test_processar_linhas_ignora_cabecalhos_e_vazios() -> None:
    """Garante que linhas vazias e textos sem padrão MM/AAAA são ignorados."""
    # Arrange
    linhas = [
        "",
        "   ",
        "MINISTERIO DA PREVIDENCIA SOCIAL",
        "EXTRATO DE INFORMACOES DA PREVIDENCIA SOCIAL - CNIS",
        "01/2022 1.212,00",
        "Total de Remunerações no período: 1.212,00",
    ]

    # Act
    resultado = processar_linhas_cnis(linhas)

    # Assert
    assert len(resultado) == 1
    assert resultado[0].data_competencia == "01/2022"
    assert resultado[0].valor == 1212.00


def test_processar_linhas_ignora_data_completa_de_admissao() -> None:
    """Verifica que linhas de vínculos com DD/MM/AAAA não são capturadas como MM/AAAA."""
    # Arrange
    linhas = [
        "01/05/2018 31/12/2020 EMPRESA DE ENGENHARIA LTDA 12.345.678/0001-90",
        "06/2018 2.500,00 07/2018 2.600,00",
    ]

    # Act
    resultado = processar_linhas_cnis(linhas)

    # Assert
    assert len(resultado) == 2
    assert resultado[0].data_competencia == "06/2018"
    assert resultado[1].data_competencia == "07/2018"


def test_processar_linhas_valores_monetarios_diversos() -> None:
    """Valida a conversão de moedas com milhares, sem milhares e zeradas."""
    # Arrange
    linhas = [
        "01/2023 0,00 02/2023 998,50 03/2023 10.500,75",
    ]

    # Act
    resultado = processar_linhas_cnis(linhas)

    # Assert
    assert len(resultado) == 3
    assert resultado[0].valor == 0.0
    assert resultado[1].valor == 998.50
    assert resultado[2].valor == 10500.75


def test_processar_linhas_interrompe_ao_encontrar_indicador_ou_invalido() -> None:
    """Verifica que o parsing da linha para se o par não satisfazer [Data, Valor]."""
    # Arrange
    linhas = [
        "01/2024 1.412,00 INDICADOR_EXTRA OUTRO_TEXTO",
    ]

    # Act
    resultado = processar_linhas_cnis(linhas)

    # Assert
    assert len(resultado) == 1
    assert resultado[0].data_competencia == "01/2024"
    assert resultado[0].valor == 1412.00
    assert "INDICADOR_EXTRA" in resultado[0].indicadores


def test_processar_linhas_ordenacao_cronologica_estrita() -> None:
    """Verifica se competências desordenadas são retornadas em ordem cronológica."""
    # Arrange
    linhas = [
        "12/2025 2.000,00 12/2024 1.800,00",
        "11/2025 1.950,00 11/2024 1.750,00",
        "10/2024 1.700,00 01/2025 1.850,00",
    ]

    # Act
    resultado = processar_linhas_cnis(linhas)

    # Assert
    competencias = [item.data_competencia for item in resultado]
    assert competencias == [
        "10/2024",
        "11/2024",
        "12/2024",
        "01/2025",
        "11/2025",
        "12/2025",
    ]


def test_extrair_dados_segurado_cabecalho_cnis_completo() -> None:
    """Valida a identificação de Nome e CPF a partir de cabeçalho padrão CNIS."""
    # Arrange
    texto = (
        "INSTITUTO NACIONAL DO SEGURO SOCIAL - INSS\n"
        "EXTRATO DE INFORMACOES DA PREVIDENCIA SOCIAL\n"
        "NIT: 123.45678.90-1 CPF: 034.544.150-80 Nome: "
        "THALES GABRIEL FERNANDES DINIZ MARTINS\n"
        "Data de nascimento: 15/04/1990 Nome da mãe: MARIA SILVA\n"
    )

    # Act
    nome, cpf = extrair_dados_segurado(texto)

    # Assert
    assert nome == "THALES GABRIEL FERNANDES DINIZ MARTINS"
    assert cpf == "034.544.150-80"


def test_extrair_dados_segurado_cpf_sem_pontuacao() -> None:
    """Verifica a normalização de CPF sem pontos ou traço."""
    # Arrange
    texto = "CPF: 12345678901 Nome: MARIA PEREIRA SANTOS Data de nascimento: 01/01/1980"

    # Act
    nome, cpf = extrair_dados_segurado(texto)

    # Assert
    assert nome == "MARIA PEREIRA SANTOS"
    assert cpf == "123.456.789-01"


def test_extrair_dados_segurado_texto_sem_dados() -> None:
    """Verifica retorno nulo quando o texto não contém metadados de identificação."""
    # Arrange
    texto = "Texto aleatório sem menção a segurado ou cadastro previdenciário."

    # Act
    nome, cpf = extrair_dados_segurado(texto)

    # Assert
    assert nome is None
    assert cpf is None


def test_extrair_metadados_pdf_arquivo_inexistente() -> None:
    """Garante tratamento resiliente ao inspecionar arquivo que não existe."""
    # Act
    nome, cpf = extrair_metadados_pdf("/caminho/falso/nao_existe.pdf")

    # Assert
    assert nome is None
    assert cpf is None


def test_processar_linhas_contribuinte_individual_salario_contribuicao() -> None:
    """Valida extração de autônomo capturando o Salário Contribuição e indicadores."""
    # Arrange: 2 competências paralelas com data de pgto, valor pago e salário base
    linhas = [
        "01/2015 14/01/2015 144,80 724,00 PREC-MENOR-MIN 02/2015 18/03/2015 157,60 788,00",
    ]

    # Act
    resultado = processar_linhas_cnis(linhas)

    # Assert
    assert len(resultado) == 2
    # Competência 01/2015 deve pegar o salário de 724.00, NÃO a guia de 144.80
    assert resultado[0].data_competencia == "01/2015"
    assert resultado[0].valor == 724.00
    assert resultado[0].origem_vinculo == "Contribuinte Individual / Carnê"
    assert "PREC-MENOR-MIN" in resultado[0].indicadores

    # Competência 02/2015 deve pegar o salário de 788.00
    assert resultado[1].data_competencia == "02/2015"
    assert resultado[1].valor == 788.00
    assert resultado[1].origem_vinculo == "Contribuinte Individual / Carnê"


def test_processar_linhas_agrupamento_contratantes_cooperativa() -> None:
    """Valida extração de cooperativas e contratantes tomadoras de serviço."""
    # Arrange
    linhas = [
        "10/2013 89.522.064/0001-66 89.522.064/0001-66 Normal 75,00 PREM-EXT",
        "04/2014 89.522.064 89.522.064/0001-66 Não Cooperado 90,00",
    ]

    # Act
    resultado = processar_linhas_cnis(linhas)

    # Assert
    assert len(resultado) == 2
    assert resultado[0].data_competencia == "10/2013"
    assert resultado[0].valor == 75.00
    assert resultado[0].origem_vinculo == "Cooperativa / Contratante"
    assert "PREM-EXT" in resultado[0].indicadores

    assert resultado[1].data_competencia == "04/2014"
    assert resultado[1].valor == 90.00
    assert resultado[1].origem_vinculo == "Cooperativa / Contratante"


def test_consolidar_competencias_maior_valor_concomitancia() -> None:
    """Verifica que a consolidação mantém o maior valor em atividades concomitantes."""
    from app.core.parser import consolidar_competencias_maior_valor
    from app.core.schemas import CnisCompetencia

    # Arrange: mesmo mês em vínculos distintos com valores diferentes
    competencias = [
        CnisCompetencia(
            data_competencia="05/2015",
            valor=2000.00,
            origem_vinculo="CLT / Emprego",
        ),
        CnisCompetencia(
            data_competencia="05/2015",
            valor=3500.00,
            origem_vinculo="Contribuinte Individual / Carnê",
        ),
        CnisCompetencia(
            data_competencia="06/2015",
            valor=1800.00,
            origem_vinculo="CLT / Emprego",
        ),
    ]

    # Act
    consolidadas = consolidar_competencias_maior_valor(competencias)

    # Assert
    assert len(consolidadas) == 2
    mapa = {c.data_competencia: c.valor for c in consolidadas}
    assert mapa["05/2015"] == 3500.00  # O maior valor entre 2000 e 3500 deve prevalecer
    assert mapa["06/2015"] == 1800.00
