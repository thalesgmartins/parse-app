# Cnis Parse App

A ideia desse projeto partiu de um problema relatada por um advogado que possui um escritório independente, onde foi feita a construção de um MVP prévio, mas com seu desenvolvimento aprofundado para a matéria de `ARQUITETURA DE SOFTWARE SAAS` no Sexto Semestre de Engenharia de Computação.

A ferramenta consiste de um Software As a Service para extrair, vizualizar e exportar os dados de Extratos de Contribuição (CNIS), usados pelo INSS para calcular aposentadorias, pensões e auxílios.

---


## Setup

Para fazer a instalação do projeto e das dependências, usamos o ambiente virtual do python, com os comandos abaixo.

```bash
# Criando um novo ambiente virutal do python
python -m venv .venv

# Ativa o ambiente virtual
source .venv/bin/activate

# Instala o projeto no ambiente virutal
pip install -e .
```

## Como rodar

Para rodar o projeto Web, deve-se usar o comando abaixo:

```bash
uvicorn app.main:app --reload
```

Para usar em modo CLI, deve-se usar:

```bash
python3 -m app.cli --path "caminho_do_arquivo.pdf"
```

## Qual a lógica para extrair os dados?

explicar
