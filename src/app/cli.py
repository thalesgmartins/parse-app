import argparse
import logging

from app.core.parser import extrair_dados_pdf

logging.basicConfig(level=logging.INFO)

_LOGGER = logging.getLogger(__name__)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parser de documentos CNIS")
    parser.add_argument("--path", "-p", type=str, required=True, help="Caminho para o arquivo PDF")
    parser.add_argument("--verbose", "-v", action="store_true", help="Caminho para o arquivo PDF")

    args = parser.parse_args()

    if args.verbose:
        _LOGGER.setLevel(logging.DEBUG)

    extrair_dados_pdf(args.path)
