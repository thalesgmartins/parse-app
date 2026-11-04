"""Utilitário para converter dados de competências em um documento CSV."""

import csv
import logging
from typing import TextIO

_LOGGER = logging.getLogger(__name__)


def convert_dict_into_csv(dados: dict[str, str], arquivo: TextIO) -> None:
    """Escreve dados de competências e valores em formato CSV delimitado por ponto e vírgula.

    Args:
        dados: Dicionário contendo pares de competência (MM/AAAA) e valores formatados.
        arquivo: Objeto de arquivo de texto aberto para escrita.
    """
    escritor = csv.writer(arquivo, delimiter=";")
    escritor.writerow(["Competência", "Valor Consolidado"])

    for mes, valor in dados.items():
        mes_seguro = f"01/{mes}"
        valor_seguro = valor.replace(".", "")
        escritor.writerow([mes_seguro, valor_seguro])
