"""Módulo de geração e formatação de arquivos para exportação."""

import csv
import io
from collections.abc import Sequence

from app.database.models import Contribuicao


def gerar_csv_contribuicoes(contribuicoes: Sequence[Contribuicao]) -> str:
    """Gera string CSV em padrão brasileiro (PT-BR) com BOM UTF-8 para Excel.

    Args:
        contribuicoes: Sequência de instâncias de Contribuicao a serem exportadas.

    Returns:
        String contendo os dados formatados em CSV com separador ponto e vírgula.
    """
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow(["Competência", "Remuneração (R$)"])

    for item in contribuicoes:
        valor_formatado = f"{item.valor:.2f}".replace(".", ",")
        writer.writerow([item.data_competencia, valor_formatado])

    return buffer.getvalue()
