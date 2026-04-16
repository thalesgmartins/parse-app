#
#  _____                                           ____             _                  _ 
# |  __ \                      /\                 |  _ \           | |                | |
# | |__) |_ _ _ __ ___  ___   /  \   _ __  _ __   | |_) | __ _  ___| | _____ _ __   __| |
# |  ___/ _` | '__/ __|/ _ \ / /\ \ | '_ \| '_ \  |  _ < / _` |/ __| |/ / _ \ '_ \ / _` |
# | |  | (_| | |  \__ \  __// ____ \| |_) | |_) | | |_) | (_| | (__|   <  __/ | | | (_| |
# |_|   \__,_|_|  |___/\___/_/    \_\ .__/| .__/  |____/ \__,_|\___|_|\_\___|_| |_|\__,_|
#                                   | |   | |                                            
#                                   |_|   |_|                                                                                
FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install --no-install-recommends -y \
        build-essential \
        curl \
        ca-certificates && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copia arquivos de definição
COPY pyproject.toml README.md ./

# Copia o fonte
COPY src/backend/ ./src/backend/

# Instala o projeto e dependências
RUN pip install --no-cache-dir .

# Comando para iniciar o Monitor
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]