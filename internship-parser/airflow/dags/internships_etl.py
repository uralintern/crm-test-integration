"""Ежедневный ETL-процесс данных о стажировках.

Для каждой из 9 компаний создаётся 3 последовательные задачи:
  parse_{company} → transform_{company} → load_{company}

Все цепочки выполняются параллельно (независимо друг от друга).
"""
from datetime import datetime, timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG


PROJECT_ROOT = "/opt/airflow/project"
ETL_ROOT = f"{PROJECT_ROOT}/ETL"

# Все компании с их именами для файлов и CLI-аргументов
COMPANIES = (
    "alfabank",
    "beeline",
    "kontur",
    "mts",
    "naumen",
    "ozon",
    "rostelekom",
    "t-bank",
    "vk",
    "yandex",
)

with DAG(
    dag_id="internships_etl",
    description="Сбор, трансформация и загрузка данных о стажировках",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    default_args={
        "owner": "internship-parser",
        "retries": 2,
        "retry_delay": timedelta(minutes=10),
    },
    tags=["internships", "etl"],
) as internships_etl:

    # Очистка БД перед запуском всех цепочек
    clear_db = BashOperator(
        task_id="clear_db",
        bash_command=(
            "set -euo pipefail\n"
            f"cd {PROJECT_ROOT}\n"
            "python ETL/clear_db.py"
        ),
    )

    # Список первых задач (parse) для связывания с clear_db
    first_tasks = []

    for company in COMPANIES:
        # 1. Парсинг
        parse_task = BashOperator(
            task_id=f"parse_{company}",
            bash_command=(
                "set -euo pipefail\n"
                f"cd {ETL_ROOT}\n"
                f"python parsers/{company}.py"
            ),
        )

        # 2. Трансформация
        transform_task = BashOperator(
            task_id=f"transform_{company}",
            bash_command=(
                "set -euo pipefail\n"
                f"cd {PROJECT_ROOT}\n"
                f"python -m ETL.transforms.run_transformers {company}"
            ),
        )

        # 3. Загрузка в БД
        load_task = BashOperator(
            task_id=f"load_{company}",
            bash_command=(
                "set -euo pipefail\n"
                f"cd {PROJECT_ROOT}\n"
                f"python ETL/loader.py {company}"
            ),
        )

        # Последовательность внутри компании
        parse_task >> transform_task >> load_task

        # Запоминаем первую задачу для связки с clear_db
        first_tasks.append(parse_task)

    # Очистка БД выполняется перед всеми цепочками
    clear_db >> first_tasks
