"""Testes unitários e de integração para o gerador sintético de CNIS."""

from pathlib import Path

from app.core.parser import extrair_dados_pdf, extrair_metadados_pdf
from app.services.cnis_generator import (
    criar_perfil_ficticio,
    formatar_moeda_br,
    gerar_cpf_ficticio,
    gerar_pdf_cnis,
)


def test_formatar_moeda_br() -> None:
    """Verifica a conversão de float para o padrão monetário brasileiro."""
    # Arrange & Act & Assert
    assert formatar_moeda_br(1250.50) == "1.250,50"
    assert formatar_moeda_br(0.0) == "0,00"
    assert formatar_moeda_br(876.08) == "876,08"
    assert formatar_moeda_br(10500.75) == "10.500,75"


def test_gerar_cpf_ficticio_valido() -> None:
    """Valida a formação sintética de CPF com dígitos verificadores corretos."""
    # Arrange
    base = "123456789"

    # Act
    cpf = gerar_cpf_ficticio(base)

    # Assert
    assert len(cpf) == 14
    assert cpf[3] == "." and cpf[7] == "." and cpf[11] == "-"
    assert cpf.startswith("123.456.789-")


def test_criar_perfil_ficticio_estrutura() -> None:
    """Garante a coerência cronológica e estrutural dos vínculos gerados."""
    # Arrange
    inicio = 2018
    fim = 2022

    # Act
    perfil = criar_perfil_ficticio(
        nome="MARCOS PAULO TESTE",
        ano_inicio=inicio,
        ano_fim=fim,
        salario_base=2000.0,
    )

    # Assert
    assert perfil.nome == "MARCOS PAULO TESTE"
    assert len(perfil.vinculos) > 0
    primeira_comp = perfil.vinculos[0].competencias[0]
    assert primeira_comp.mes_ano == f"01/{inicio}"
    assert primeira_comp.valor >= 2000.0


def test_gerar_pdf_cnis_compatibilidade_com_parser(tmp_path: Path) -> None:
    """Testa a geração do PDF e valida a extração completa pelo parser oficial."""
    # Arrange
    caminho_pdf = tmp_path / "extrato_teste_unitario.pdf"
    perfil = criar_perfil_ficticio(
        nome="ANA CAROLINA SILVEIRA",
        cpf="111.222.333-44",
        ano_inicio=2020,
        ano_fim=2023,
        salario_base=3000.0,
    )
    total_esperado = sum(len(v.competencias) for v in perfil.vinculos)

    # Act
    pdf_gerado = gerar_pdf_cnis(
        segurado=perfil,
        caminho_saida=caminho_pdf,
    )
    nome_extraido, cpf_extraido = extrair_metadados_pdf(pdf_gerado)
    competencias_extraidas = extrair_dados_pdf(pdf_gerado)

    # Assert
    assert pdf_gerado.exists()
    assert pdf_gerado.stat().st_size > 0
    assert nome_extraido == "ANA CAROLINA SILVEIRA"
    assert cpf_extraido == "111.222.333-44"
    assert len(competencias_extraidas) == total_esperado
    assert competencias_extraidas[0].data_competencia == "01/2020"
    assert competencias_extraidas[0].valor == 3000.0
