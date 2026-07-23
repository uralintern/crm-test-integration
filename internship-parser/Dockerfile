FROM python:3.12-slim

# Не создавать .pyc и не буферизовать вывод — удобнее для логов в докере
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    PIP_DEFAULT_TIMEOUT=120

WORKDIR /app

# Системные зависимости для psycopg2-binary (обычно не нужны, но на всякий случай
# оставляем build-essential, если понадобится собрать что-то из исходников)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Сначала копируем только файлы зависимостей — так слой с зависимостями кешируется
# и не пересобирается при каждом изменении кода
COPY pyproject.toml poetry.lock ./
RUN pip install --no-cache-dir poetry \
    && poetry install --no-ansi --without dev

# Теперь копируем остальной код
COPY . .

# Скрипт запуска: сначала грузим данные в БД, потом стартуем сервер
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE ${APP_PORT}

ENTRYPOINT ["/entrypoint.sh"]
