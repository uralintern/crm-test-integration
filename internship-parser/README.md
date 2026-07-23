# internship-parser
Парсер IT стажировок России

http://127.0.0.1:8080/docs

## Apache Airflow и ежедневный ETL

Docker Compose поднимает Airflow вместе с API и PostgreSQL. DAG `internships_etl`
ежедневно запускает три операции в порядке: сбор данных, трансформацию и загрузку
в БД. Пропущенные запуски не выполняются задним числом.

1. Добавьте переменные `AIRFLOW_*` из `.env.example` в `.env`. Перед развёртыванием
   вне локальной машины обязательно задайте уникальные `AIRFLOW_FERNET_KEY` и
   `AIRFLOW_JWT_SECRET`.
2. Запустите сервисы: `docker compose up -d --build`.
3. Откройте Airflow UI. Логин и пароль задаются переменными
   `AIRFLOW_ADMIN_USERNAME` и `AIRFLOW_ADMIN_PASSWORD` в `.env`. Если оставить
   `AIRFLOW_ADMIN_PASSWORD` пустым, Airflow создаст пароль при первом запуске; его
   можно посмотреть командой:
   `docker compose exec airflow-api-server cat
   /opt/airflow/simple_auth_manager_passwords.json.generated`.
4. В интерфейсе Airflow выберите DAG `internships_etl` и нажмите **Trigger DAG**,
   чтобы выполнить ETL сразу. Для запуска из терминала:
   `docker compose exec airflow-scheduler airflow dags trigger internships_etl`.

Статусы задач и их логи доступны на странице запуска DAG в Airflow. Остановить
сервисы можно командой `docker compose down`; данные PostgreSQL и метаданные
Airflow сохраняются в Docker volumes.

## REST API

Микросервис FastAPI доступен по адресу `/parser/api`.

Эндпоинты:
- `GET /parser/api/internship` — список стажировок с пагинацией
- `GET /parser/api/internship/{id}` — детали стажировки по UUID
- `GET /parser/api/internship/export?format=csv|excel|word` — экспорт данных в файл

Фильтры для списка:
- `city` — город или несколько городов
- `format` — office, hybrid, remote
- `employment` — full-time, part-time

## Поддерживаемые источники

Парсеры реализованы для компаний: Альфа-Банк, Beeline, Контур, МТС, Naumen, Озон, Ростелеком, Т-Банк, ВКонтакте, Яндекс.

Каждый парсер сохраняет сырые данные в `ETL/data/parsed/{company}.json`.
Трансформаторы приводят данные к единому формату и сохраняют в `ETL/data/transformed/{company}.json`.
Загрузчик `ETL/loader.py` переносит данные из JSON в PostgreSQL.

## Структура проекта

```
internship-parser/
├── app/
│   ├── main.py
│   ├── schemas.py
│   └── api/
│       └── routes/
│           └── internships.py
├── utils/
│   ├── config.py
│   ├── export.py
│   └── internships_db.py
├── models/
│   └── internship.py
├── ETL/
│   ├── parsers/
│   ├── transforms/
│   │   ├── base.py
│   │   └── run_transformers.py
│   ├── loader.py
│   └── clear_db.py
├── airflow/
│   └── dags/
│       └── internships_etl.py
└── pyproject.toml
```

## Переменные окружения

Файл `.env` должен содержать переменные для подключения к PostgreSQL и настройки API.
Пример переменных БД:

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=internships
DB_USER=postgres
DB_PASSWORD=1111
```

## Запуск без Docker

1. Установите зависимости: `poetry install`
2. Запустите PostgreSQL
3. Выполните ETL: `python ETL/loader.py`
4. Запустите API: `uvicorn app.main:app --host 0.0.0.0 --port 8080`
