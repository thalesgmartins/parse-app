"""Script utilitário para geração de extrato CNIS com dados fictícios.

Permite gerar um documento PDF completo e idêntico ao modelo oficial emitido
pelo INSS/Gov.br, ideal para apresentações, demonstrações em reuniões e testes
sem expor dados pessoais protegidos pela LGPD.
"""

from __future__ import annotations

import argparse
import logging
import sys

from app.core.parser import extrair_dados_pdf, extrair_metadados_pdf
from app.services.cnis_generator import (
    criar_perfil_ficticio,
    gerar_pdf_cnis,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
_LOGGER = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    """Executa a rotina de linha de comando para gerar o extrato CNIS.

    Args:
        argv: Lista opcional de argumentos da CLI.

    Returns:
        Código de saída do processo (0 para sucesso, 1 para falha).
    """
    parser = argparse.ArgumentParser(
        description="Gera extrato CNIS sintético em PDF com leiaute oficial do INSS.",
    )
    parser.add_argument(
        "--saida",
        "-o",
        type=str,
        default="extrato_apresentacao.pdf",
        help="Caminho de saída do arquivo PDF (padrão: extrato_apresentacao.pdf)",
    )
    parser.add_argument(
        "--nome",
        "-n",
        type=str,
        default="CARLOS EDUARDO SILVA SANTOS",
        help="Nome fictício do segurado",
    )
    parser.add_argument(
        "--cpf",
        "-c",
        type=str,
        default=None,
        help="CPF fictício formatado (000.000.000-00); gerado automaticamente se omitido",
    )
    parser.add_argument(
        "--inicio",
        "-i",
        type=int,
        default=2015,
        help="Ano inicial da série contributiva (padrão: 2015)",
    )
    parser.add_argument(
        "--fim",
        "-f",
        type=int,
        default=2026,
        help="Ano final da série contributiva (padrão: 2026)",
    )
    parser.add_argument(
        "--salario",
        "-s",
        type=float,
        default=2400.0,
        help="Salário base inicial para progressão salarial (padrão: 2400.00)",
    )

    args = parser.parse_args(argv)

    try:
        _LOGGER.info("Configurando perfil sintético para %s...", args.nome)
        perfil = criar_perfil_ficticio(
            nome=args.nome,
            cpf=args.cpf,
            ano_inicio=args.inicio,
            ano_fim=args.fim,
            salario_base=args.salario,
        )

        total_competencias = sum(len(v.competencias) for v in perfil.vinculos)
        _LOGGER.info(
            "Gerando PDF com %d vínculos e %d competências (%d a %d)...",
            len(perfil.vinculos),
            total_competencias,
            args.inicio,
            args.fim,
        )

        caminho_gerado = gerar_pdf_cnis(
            segurado=perfil,
            caminho_saida=args.saida,
        )
        _LOGGER.info("Arquivo PDF gerado em: %s", caminho_gerado)

        # Validação automática com o parser oficial do projeto
        _LOGGER.info("Validando integridade com o parser do ParseApp...")
        nome_ext, cpf_ext = extrair_metadados_pdf(caminho_gerado)
        dados_extraidos = extrair_dados_pdf(caminho_gerado)

        _LOGGER.info(
            "Parser validado: Nome='%s' | CPF='%s' | Competências=%d",
            nome_ext,
            cpf_ext,
            len(dados_extraidos),
        )

        if len(dados_extraidos) != total_competencias:
            _LOGGER.error(
                "Atenção: Esperadas %d competências, extraídas %d",
                total_competencias,
                len(dados_extraidos),
            )
            return 1

        _LOGGER.info("Sucesso! O documento está 100%% compatível com o ParseApp.")
        return 0

    except Exception as exc:
        _LOGGER.error("Falha ao gerar extrato fictício: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
