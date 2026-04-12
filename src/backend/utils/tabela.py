"""Utilitário pra converter dados em um documento CSV."""
import csv
import logging


_LOGGER = logging.getLogger(__name__)

def convert_dict_into_csv(dados: dict):
    with open("resultado.csv", mode='w', encoding='utf-8', newline='') as arquivo:
        escritor = csv.writer(arquivo, delimiter=';')

        escritor.writerow(['Competência', 'Valor Consolidado'])
        
        for mes, valor in dados.items():

            mes_seguro = f"01/{mes}"

            valor_seguro = valor.replace('.', '')
            escritor.writerow([mes, valor_seguro])




if __name__ == "__main__":
    from backend.utils.pdf import extrair_dados_pdf

    # Como o logger não foi inicializdo na main, criamos uma config básica pra ele.
    logging.basicConfig(level=logging.INFO)
    
    dados = extrair_dados_pdf("teste.pdf")

    convert_dict_into_csv(dados)
