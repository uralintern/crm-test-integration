FROM apache/airflow:3.3.0-python3.12

# Зависимости ETL устанавливаются в образ Airflow, чтобы задачи могли выполнять
# существующие парсеры, трансформаторы и загрузчик без отдельного окружения.
USER airflow
COPY --chown=airflow:root requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
