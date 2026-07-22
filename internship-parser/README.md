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
3. Откройте Airflow: `
`. Логин и пароль задаются переменными
   `AIRFLOW_ADMIN_USERNAME` и `AIRFLOW_ADMIN_PASSWORD` в `.env`. Если оставить
   `AIRFLOW_ADMIN_PASSWORD` пустым, Airflow создаст пароль при первом запуске; его
   можно посмотреть командой: `docker compose exec airflow-api-server cat
   /opt/airflow/simple_auth_manager_passwords.json.generated`.
4. В интерфейсе Airflow выберите DAG `internships_etl` и нажмите **Trigger DAG**,
   чтобы выполнить ETL сразу. Для запуска из терминала:
   `docker compose exec airflow-scheduler airflow dags trigger internships_etl`.

Статусы задач и их логи доступны на странице запуска DAG в Airflow. Остановить
сервисы можно командой `docker compose down`; данные PostgreSQL и метаданные
Airflow сохраняются в Docker volumes.
