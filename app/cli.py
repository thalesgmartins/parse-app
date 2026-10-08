"""Ponto de entrada para execução via linha de comando (CLI)."""

import argparse
import logging

from app.core.parser import extrair_dados_pdf

VERMELHO = "\033[31m"
VERDE = "\033[32m"
AZUL = "\033[34m"
RESET = "\033[0m"

logging.basicConfig(
    level=logging.INFO,
    format=f"{VERDE}%(asctime)s{RESET} | {VERMELHO}%(levelname)s{RESET} | {AZUL}%(filename)s:%(lineno)d{RESET} | %(message)s",  # noqa: E501
)
_LOGGER = logging.getLogger(__name__)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parser de documentos CNIS")
    parser.add_argument(
        "--path",
        "-p",
        type=str,
        required=True,
        help="Caminho para o arquivo PDF",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Ativa logs detalhados em modo DEBUG",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger("app").setLevel(logging.DEBUG)

    dados_extraidos = extrair_dados_pdf(args.path)

    for dado in dados_extraidos:
        _LOGGER.info(
            "Data: %s | Competência: R$ %s",
            dado.data_competencia,
            dado.valor,
        )
