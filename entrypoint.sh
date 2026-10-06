#!/bin/bash
set -e

echo "=========================================================="
echo "      INICIANDO BACKEND DE COLEGIO - SIGEN (DOCKER)       "
echo "=========================================================="

CONFIG_PATH="${SCHOOL_CONFIG_PATH:-config/school.default.yml}"
APP_PORT="${PORT:-8001}"

echo "[1/3] Configuración activa: ${CONFIG_PATH}"

# Si la base de datos es PostgreSQL, esperar a que esté lista
if [[ "$DATABASE_URL" == *"postgres"* ]]; then
    echo "[2/3] Verificando conexión con PostgreSQL..."
    python - << 'EOF'
import os, sys, time
import urllib.parse
import psycopg2

db_url = os.getenv("DATABASE_URL", "")
# Reemplazar driver sqlalchemy si está presente para psycopg2
clean_url = db_url.replace("postgresql+psycopg2://", "postgresql://").replace("postgresql+psycopg://", "postgresql://")

max_retries = 30
for attempt in range(1, max_retries + 1):
    try:
        conn = psycopg2.connect(clean_url)
        conn.close()
        print(f" Conexión a PostgreSQL establecida con éxito.")
        sys.exit(0)
    except Exception as e:
        print(f" Esperando a PostgreSQL (intento {attempt}/{max_retries}): {e}")
        time.sleep(2)

print(" Error: No se pudo conectar a PostgreSQL tras varios intentos.")
sys.exit(1)
EOF
else
    echo "[2/3] Usando base de datos SQLite..."
fi

# Inicialización limpia de la escuela (Tablas, Roles, Permisos y Superadmin)
echo "[3/3] Inicializando base de datos y verificando Super Admin..."
python bootstrap_school.py "$CONFIG_PATH" --non-interactive

echo "=========================================================="
echo " Backend listo. Escuchando en el puerto ${APP_PORT}..."
echo "=========================================================="

exec uvicorn app.main:app --host 0.0.0.0 --port "$APP_PORT"
