import pdfplumber
import re

def extrair_remuneracoes_cnis(caminho_pdf: str) -> dict:
    resultado = {
        "filiado": {},
        "remuneracoes": [],
        "consolidado_anual": []
    }

    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text()
            if not texto:
                continue

            # Extrai dados do filiado apenas uma vez
            if not resultado["filiado"]:
                resultado["filiado"] = extrair_filiado(texto)

            # Extrai tabelas da página
            tabelas = pagina.extract_tables()

            # DEBUG essencial — rode isso primeiro!
            # print(f"\n--- Página ---")
            # print(f"Tabelas encontradas: {len(tabelas)}")
            # for i, t in enumerate(tabelas):
            #     print(f"\nTabela {i}:")
            #     for linha in t:
            #         print(linha)

            for tabela in tabelas:
                if not tabela:
                    continue

                # Identifica o tipo de tabela pelo cabeçalho
                cabecalho = [c.strip() if c else "" for c in tabela[0]]
                cabecalho_str = " ".join(cabecalho).lower()

                if "competência" in cabecalho_str and "remuneração" in cabecalho_str:
                    remuneracoes = processar_tabela_remuneracoes(tabela)
                    resultado["remuneracoes"].extend(remuneracoes)

                elif "ano" in cabecalho_str and "jan" in cabecalho_str:
                    consolidado = processar_tabela_anual(tabela)
                    resultado["consolidado_anual"].extend(consolidado)

    # Ordena remunerações por data ao final
    resultado["remuneracoes"].sort(key=lambda x: x.get("competencia_ord", ""))

    return resultado


def extrair_filiado(texto: str) -> dict:
    filiado = {}

    nit = re.search(r"NIT[:\s]+([\d.\-/]+)", texto)
    if nit:
        filiado["nit"] = nit.group(1).strip()

    cpf = re.search(r"CPF[:\s]+([\d.\-]+)", texto)
    if cpf:
        filiado["cpf"] = cpf.group(1).strip()

    nome = re.search(r"Nome[:\s]+([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ ]+?)(?=\s{2,}|Nome da)", texto, re.IGNORECASE)
    if nome:
        filiado["nome"] = nome.group(1).strip()

    nascimento = re.search(r"Data de nascimento[:\s]+([\d/]+)", texto, re.IGNORECASE)
    if nascimento:
        filiado["data_nascimento"] = nascimento.group(1).strip()

    return filiado


def processar_tabela_remuneracoes(tabela: list) -> list:
    """
    A tabela de remunerações tem 3 grupos de colunas lado a lado:
    [Competência | Remuneração | Indicadores] x3

    O pdfplumber geralmente retorna isso como uma linha com 9 colunas.
    Ex: ['10/2024', '876,08', 'PSC...', '11/2024', '1.775,06', '', '12/2024', '1.753,98', '']
    """
    remuneracoes = []

    for linha in tabela[1:]:  # Pula cabeçalho
        if not linha or not any(linha):
            continue

        # DEBUG: veja o que cada linha tem
        # print("Linha bruta:", linha)

        # Limpa valores None
        linha = [c.strip() if c else "" for c in linha]

        # A tabela tem 9 colunas (3 grupos de 3)
        # Itera de 3 em 3 para pegar cada grupo
        for i in range(0, len(linha), 3):
            competencia = linha[i] if i < len(linha) else ""
            remuneracao = linha[i+1] if i+1 < len(linha) else ""
            indicadores = linha[i+2] if i+2 < len(linha) else ""

            # Valida se a competência tem formato MM/AAAA
            if not re.match(r"\d{2}/\d{4}", competencia):
                continue

            # Converte remuneração de string BR para float
            # "1.808,83" -> 1808.83
            valor_float = None
            if remuneracao:
                try:
                    valor_float = float(
                        remuneracao.replace(".", "").replace(",", ".")
                    )
                except ValueError:
                    pass  # Deixa None se não conseguir converter

            # Cria chave de ordenação no formato AAAA/MM
            mes, ano = competencia.split("/")
            competencia_ord = f"{ano}/{mes}"

            remuneracoes.append({
                "competencia": competencia,        # "10/2024"
                "competencia_ord": competencia_ord, # "2024/10" (para ordenar)
                "remuneracao": valor_float,         # 876.08 (float)
                "remuneracao_str": remuneracao,     # "876,08" (original)
                "indicadores": indicadores
            })

    return remuneracoes


def processar_tabela_anual(tabela: list) -> list:
    """
    Tabela: Ano | Jan | Fev | Mar | Abr | Mai | Jun | Jul | Ago | Set | Out | Nov | Dez
    """
    consolidado = []
    meses = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"]

    for linha in tabela[1:]:
        if not linha or not linha[0]:
            continue

        linha = [c.strip() if c else "" for c in linha]
        ano = linha[0]

        if not re.match(r"\d{4}", ano):
            continue

        entry = {"ano": ano}
        for i, mes in enumerate(meses):
            valor_str = linha[i+1] if i+1 < len(linha) else ""
            if valor_str:
                try:
                    entry[mes] = float(valor_str.replace(".", "").replace(",", "."))
                except ValueError:
                    entry[mes] = None
            else:
                entry[mes] = None

        consolidado.append(entry)

    return consolidado


if __name__ == "__main__":
    dados = extrair_remuneracoes_cnis("teste.pdf")

    print("=== FILIADO ===")
    for k, v in dados["filiado"].items():
        print(f"  {k}: {v}")

    print(f"\n=== REMUNERAÇÕES ({len(dados['remuneracoes'])} registros) ===")
    for r in dados["remuneracoes"]:
        ind = f" [{r['indicadores']}]" if r['indicadores'] else ""
        print(f"  {r['competencia']}: R$ {r['remuneracao']:>10.2f}{ind}")

    print(f"\n=== CONSOLIDADO ANUAL ===")
    for ano in dados["consolidado_anual"]:
        valores = [f"{v:.2f}" if v else "   -  " for v in list(ano.values())[1:]]
        print(f"  {ano['ano']}: {' | '.join(valores)}")