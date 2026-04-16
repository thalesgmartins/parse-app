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

```bash
uvicorn backend.main:app --reload
```