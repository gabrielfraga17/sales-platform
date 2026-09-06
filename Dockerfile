# Dockerfile para a Sales Platform (FastAPI no Cloud Run)
FROM python:3.11-slim

# Evita geração de arquivos .pyc e força stdout/stderr sem buffer
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

# Instala dependências do sistema necessárias
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala as dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código-fonte da aplicação
COPY app/ ./app/

# Expõe a porta da aplicação
EXPOSE 8080

# Comando para iniciar o servidor uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
