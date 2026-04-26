# parse-core

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
uvicorn src.app.main:app --reload
```

Para usar em modo CLI, deve-se usar:

```bash
python3 -m app.cli --path "caminho_do_arquivo.pdf"
```

## Qual a lógica para extrair os dados?

explicar