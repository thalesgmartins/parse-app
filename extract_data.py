import pdfplumber
import re

def extrair_remuneracoes_cnis(caminho_pdf: str) -> dict:
    resultado = {
        "filiado": {},
        "remuneracoes": [],
        "consolidado_anual": []
    }

    with pdfplumber.open(caminho_pdf) as pdf:
        # Junta o texto de todas as páginas
        texto_completo = ""
        for pagina in pdf.pages:
            texto = pagina.extract_text()
            if texto:
                texto_completo += texto + "\n"

    resultado["filiado"] = extrair_filiado(texto_completo)
    resultado["remuneracoes"] = extrair_remuneracoes(texto_completo)
    resultado["consolidado_anual"] = extrair_consolidado_anual(texto_completo)

    return resultado


def extrair_filiado(texto: str) -> dict:
    filiado = {}

    nit = re.search(r"NIT:\s*([\d.\-/]+)", texto)
    if nit:
        filiado["nit"] = nit.group(1).strip()

    cpf = re.search(r"CPF:\s*([\d.\-]+)", texto)
    if cpf:
        filiado["cpf"] = cpf.group(1).strip()

    # Nome fica entre "Nome:" e "Data de nascimento"
    nome = re.search(r"Nome:\s*(.+?)\s*(?=Data de nascimento)", texto, re.DOTALL)
    if nome:
        filiado["nome"] = nome.group(1).strip()

    nascimento = re.search(r"Data de nascimento:\s*([\d/]+)", texto)
    if nascimento:
        filiado["data_nascimento"] = nascimento.group(1).strip()

    mae = re.search(r"Nome da mãe:\s*(.+)", texto)
    if mae:
        filiado["nome_mae"] = mae.group(1).strip()

    return filiado


def extrair_remuneracoes(texto: str) -> list:
    """
    O texto bruto das remunerações tem esse formato:
    
    Competência Remuneração Indicadores Competência Remuneração ...
    10/2024 876,08 PSC-MEN-SM-   11/2024 1.775,06   12/2024 1.753,98
    EC103
    01/2025 1.808,83   02/2025 1.772,06 ...

    Estratégia: buscar todos os pares MM/AAAA + valor no texto inteiro.
    O regex captura competência e remuneração independente de colunas.
    """

    remuneracoes = []

    # Extrai só o bloco entre "Remunerações" e "Valores Consolidados"
    bloco = re.search(
        r"Remunerações\s*\n.+?Indicadores\s*\n(.+?)Valores Consolidados",
        texto,
        re.DOTALL
    )

    if not bloco:
        print("DEBUG: Bloco de remunerações não encontrado!")
        print("DEBUG: Verifique se o texto tem 'Remunerações' e 'Valores Consolidados'")
        return []

    texto_remun = bloco.group(1)

    # DEBUG: veja o bloco isolado
    # print("--- BLOCO REMUNERAÇÕES ---")
    # print(texto_remun)

    # Busca todos os pares: MM/AAAA seguido de valor no formato 0.000,00 ou 000,00
    pares = re.findall(
        r"(\d{2}/\d{4})\s+([\d.,]+)",
        texto_remun
    )

    # DEBUG: veja os pares encontrados
    # print("Pares encontrados:", pares)

    for competencia, valor_str in pares:
        # Converte "1.808,83" → 1808.83
        try:
            valor_float = float(valor_str.replace(".", "").replace(",", "."))
        except ValueError:
            valor_float = None

        mes, ano = competencia.split("/")

        remuneracoes.append({
            "competencia": competencia,
            "competencia_ord": f"{ano}/{mes}",  # Para ordenar: "2024/10"
            "remuneracao": valor_float,
            "remuneracao_str": valor_str
        })

    # Ordena por data
    remuneracoes.sort(key=lambda x: x["competencia_ord"])

    return remuneracoes


def extrair_consolidado_anual(texto: str) -> list:
    """
    Formato no texto:
    2024 876,08 1.775,06 1.753,98
    2025 1.808,83 1.772,06 ...
    """
    consolidado = []
    meses = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"]

    # Isola o bloco da tabela anual
    bloco = re.search(
        r"Ano\s+Jan\s+Fev.+?\n(.+?)(?=\nO INSS|\Z)",
        texto,
        re.DOTALL
    )

    if not bloco:
        print("DEBUG: Bloco consolidado anual não encontrado!")
        return []

    for linha in bloco.group(1).strip().split("\n"):
        linha = linha.strip()
        if not re.match(r"^\d{4}", linha):
            continue

        partes = linha.split()
        ano = partes[0]
        entry = {"ano": ano}

        # Os valores começam na posição 1
        # Descobre em quais meses há valor pelo contexto do ano
        # (anos incompletos terão menos valores)
        valores = partes[1:]

        # Para 2024: só out/nov/dez têm valor (começou em 10/2024)
        # Para 2025: todos os 12 meses
        # Para 2026: só jan/fev
        # Usamos os valores na ordem, preenchendo None onde não há
        for i, mes in enumerate(meses):
            if i < len(valores):
                try:
                    entry[mes] = float(valores[i].replace(".", "").replace(",", "."))
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
        print(f"  {r['competencia']}: R$ {r['remuneracao']:>10.2f}")

    print(f"\n=== CONSOLIDADO ANUAL ===")
    for ano_data in dados["consolidado_anual"]:
        print(f"\n  {ano_data['ano']}:")
        for mes in ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"]:
            val = ano_data.get(mes)
            if val:
                print(f"    {mes}: R$ {val:.2f}")