# FastAPI Backend Documentation

## Обзор

REST API для поиска и фильтрации стажировок, реализованный на FastAPI.

## Возможности

- Список стажировок с пагинацией
- Фильтрация по городам, формату работы, типу занятости
- Детали стажировки по UUID
- Экспорт данных в CSV, Excel и Word
- Валидация входных параметров
- Обработка ошибок 404 и 500
- CORS

## Структура проекта

```
app/
├── main.py                  # Точка входа FastAPI приложения
├── schemas.py               # Pydantic модели для ответов
├── api/
│   └── routes/
│       └── internships.py   # Маршруты для стажировок
```

## API Эндпоинты

### 1. Получение списка стажировок

```
GET /api/internship
```

Параметры запроса:
- `page` (integer, опционально): Номер страницы (по умолчанию 1)
- `city` (array[string], опционально): Города для фильтрации
- `format` (array[string], опционально): Форматы работы (office, hybrid, remote)
- `employment` (array[string], опционально): Тип занятости (full-time, part-time)

Ответ успеха (200):
```json
{
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Python Developer",
      "direction": "Разработка",
      "company": "Яндекс",
      "city": "Москва",
      "work_format": "Гибрид",
      "link": "https://example.com/vacancy/1",
      "salary_from": 50000,
      "description": "Разработка бэкенда на Python"
    }
  ],
  "pagination": {
    "total": 139,
    "page": 1,
    "page_size": 20,
    "total_pages": 7
  }
}
```

Примеры:
```bash
# Все стажировки, первая страница
GET /api/internship

# Вторая страница
GET /api/internship?page=2

# Фильтр по городам
GET /api/internship?city=Москва&city=Санкт-Петербург

# Фильтр по формату работы
GET /api/internship?format=hybrid&format=remote

# Комбинированный фильтр
GET /api/internship?city=Москва&format=office
```

### 2. Получение полной информации о стажировке

```
GET /api/internship/{internshipUuid}
```

Параметры пути:
- `internshipUuid` (string, UUID): UUID стажировки

Ответ успеха (200):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Python Developer",
  "direction": "Разработка",
  "company": "Яндекс",
  "city": "Москва",
  "work_format": "Гибрид",
  "link": "https://example.com/vacancy/1",
  "salary_from": 50000,
  "description": "Разработка бэкенда на Python"
}
```

Ответ 404:
```json
{
  "detail": "Internship not found"
}
```

### 3. Экспорт данных в файл

```
GET /api/internship/export?format=csv|excel|word
```

Параметры запроса:
- `format` (string, обязательный): Формат файла — `csv`, `excel` или `word`

Ответ успеха (200) с заголовком `Content-Disposition: attachment` и соответствующим MIME-типом.

## Запуск приложения

### 1. Установка зависимостей

```bash
pip install fastapi uvicorn psycopg2-binary sqlalchemy pydantic python-dotenv openpyxl python-docx
```

### 2. Убедитесь, что PostgreSQL запущен

```bash
docker compose up -d
```

### 3. Загрузите данные в БД

```bash
python ETL/loader.py
```

### 4. Запуск сервера

```bash
uvicorn app.main:app --reload
```

Сервер будет доступен по адресу: `http://localhost:8080`

## Документация API

- Swagger UI: `/docs`
- ReDoc: `/redoc`

## Переменные окружения

Убедитесь, что `.env` файл содержит:
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=internships
DB_USER=postgres
DB_PASSWORD=1111
APP_HOST=0.0.0.0
APP_PORT=8080
```

## Производство

Для развёртывания в production используйте:

```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app
```
