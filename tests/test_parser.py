"""Testes unitários para o motor de parsing de extratos CNIS."""

from app.core.parser import processar_linhas_cnis


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
