# Use uma imagem oficial e leve do Python
FROM python:3.11-slim

# Evita que o Python escreva arquivos .pyc no disco e bufe a saída no terminal
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8

WORKDIR /app

# Instala dependências de compilação essenciais para o sqlite e pacotes compilados
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsqlite3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia apenas o arquivo de requisitos para aproveitar a camada de cache do Docker
COPY requirements.txt .

# Atualiza o pip e instala as dependências da aplicação
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copia o restante dos arquivos do repositório para o container
COPY . .

# Garante a existência do diretório de dados persistentes para o SQLite e permissões adequadas
RUN mkdir -p /app/data

# Expõe a porta que a aplicação FastAPI escuta
EXPOSE 8000

# Define a pasta /app/data como um volume para persistir o SQLite entre restarts de containers
VOLUME ["/app/data"]

# Executa o servidor Uvicorn escutando em todas as interfaces de rede na porta 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
