#!/bin/sh
set -e

echo "Ожидаю доступность PostgreSQL (${DB_HOST}:${DB_PORT})..."

python - <<'PYEOF'
import os
import sys
import time
import psycopg2

host = os.environ["DB_HOST"]
port = os.environ["DB_PORT"]
user = os.environ["DB_USER"]
password = os.environ["DB_PASSWORD"]
dbname = os.environ["DB_NAME"]

for attempt in range(30):
    try:
        conn = psycopg2.connect(
            host=host, port=port, user=user, password=password, dbname=dbname
        )
        conn.close()
        print("PostgreSQL доступен.")
        sys.exit(0)
    except psycopg2.OperationalError:
        print(f"Попытка {attempt + 1}/30: БД ещё не готова, жду...")
        time.sleep(1)

print("Не удалось дождаться PostgreSQL.", file=sys.stderr)
sys.exit(1)
PYEOF

echo "Загружаю данные в БД..."
python ETL/loader.py

echo "Запускаю uvicorn..."
if [ "$RELOAD" = "true" ]; then
    exec uvicorn app.main:app --host "${APP_HOST}" --port "${APP_PORT}" --reload
else
    exec uvicorn app.main:app --host "${APP_HOST}" --port "${APP_PORT}"
fi