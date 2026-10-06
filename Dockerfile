FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente y la configuración
COPY . .

# Asegurar permisos de ejecución en entrypoint
RUN chmod +x /app/entrypoint.sh

# Directorio para archivos subidos y base de datos local
RUN mkdir -p /app/data/archivos

EXPOSE 8001

ENTRYPOINT ["/bin/bash", "/app/entrypoint.sh"]
