# FastAPI Backend Documentation

## Обзор

Полнофункциональный REST API для поиска и фильтрации стажировок, реализованный на FastAPI.

## Возможности

✅ **Список стажировок** - получение списка с пагинацией
✅ **Фильтрация** - по городам, формату работы, типу занятости
✅ **Детали стажировки** - получение полной информации по UUID
✅ **Пагинация** - 20 записей на страницу
✅ **Валидация UUID** - автоматическая проверка формата UUID
✅ **Обработка ошибок** - 404 для не найденных записей, 500 для ошибок сервера
✅ **CORS** - включена поддержка кросс-доменных запросов
✅ **Документация** - автоматическая документация Swagger UI

## Структура проекта

```
app/
├── __init__.py              # Инициализация пакета
├── main.py                  # Точка входа FastAPI приложения
├── schemas.py               # Pydantic модели для ответов
├── test_examples.py         # Примеры и curl команды
├── api/
│   ├── __init__.py
│   └── routes/
│       ├── __init__.py
│       └── internships.py   # Маршруты для стажировок
```

## API Эндпоинты

### 1. Получение списка стажировок

```
GET /api/internship
```

**Параметры запроса:**
- `page` (integer, опционально): Номер страницы (по умолчанию 1)
- `city` (array[string], опционально): Города для фильтрации
- `format` (array[string], опционально): Форматы работы (office, hybrid, remote)
- `employment` (array[string], опционально): Тип занятости (full-time, part-time)

**Ответ успеха (200):**
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

**Примеры:**
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

**Параметры пути:**
- `internshipUuid` (string, UUID): UUID стажировки

**Ответ успеха (200):**
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

**Ответ 404:**
```json
{
  "detail": "Internship not found"
}
```

## Запуск приложения

### 1. Установка зависимостей

```bash
pip install fastapi uvicorn psycopg2-binary sqlalchemy pydantic python-dotenv
```

### 2. Убедитесь, что PostgreSQL запущен

```bash
docker-compose up -d  # или другой способ запуска БД
```

### 3. Убедитесь, что данные загружены в БД

```bash
python loader.py
```

### 4. Запуск сервера

```bash
# Режим разработки с автоперезагрузкой
uvicorn app.main:app --reload

# Или без автоперезагрузки
python app/main.py
```

Сервер будет доступен по адресу: `http://localhost:8000`

## Документация API

### Swagger UI
```
http://localhost:8000/docs
```

### ReDoc
```
http://localhost:8000/redoc
```

## Примеры использования

### Python (requests)

```python
import requests

# Получить все стажировки
response = requests.get("http://localhost:8000/api/internship")
data = response.json()

# Получить стажировки в Москве
response = requests.get(
    "http://localhost:8000/api/internship",
    params={"city": ["Москва"]}
)

# Получить стажировку по UUID
response = requests.get(
    "http://localhost:8000/api/internship/550e8400-e29b-41d4-a716-446655440000"
)
```

### cURL

```bash
# Все стажировки
curl http://localhost:8000/api/internship

# Вторая страница
curl 'http://localhost:8000/api/internship?page=2'

# По городам
curl 'http://localhost:8000/api/internship?city=Москва&city=Санкт-Петербург'

# По формату работы
curl 'http://localhost:8000/api/internship?format=hybrid&format=remote'

# По UUID
curl 'http://localhost:8000/api/internship/550e8400-e29b-41d4-a716-446655440000'

# Проверка здоровья
curl http://localhost:8000/health
```

### JavaScript/TypeScript (fetch)

```javascript
// Получить все стажировки
const response = await fetch('http://localhost:8000/api/internship');
const data = await response.json();

// С параметрами
const params = new URLSearchParams({
  page: 2,
  city: 'Москва'
});
const response = await fetch(
  `http://localhost:8000/api/internship?${params}`
);
```

## Коды ошибок

| Код | Описание |
|-----|---------|
| 200 | Успешный ответ |
| 404 | Стажировка не найдена (при запросе по UUID) |
| 400 | Неверные параметры запроса |
| 500 | Ошибка сервера |

## Фильтры

### Города (city)
Доступные города:
- Москва
- Санкт-Петербург
- Екатеринбург
- и другие...

### Формат работы (format)
- `office` - Офис
- `hybrid` - Гибрид
- `remote` - Удалённая работа

### Тип занятости (employment)
- `full-time` - Полная занятость
- `part-time` - Частичная занятость

## Пагинация

Результаты возвращаются с пагинацией:
- **page_size**: 20 записей на странице
- **total_pages**: Рассчитывается автоматически

Для получения следующей страницы используйте параметр `page`:
```bash
GET /api/internship?page=1  # Первая страница
GET /api/internship?page=2  # Вторая страница
GET /api/internship?page=3  # Третья страница
```

## Разработка

### Запуск тестов примеров

```bash
python app/test_examples.py
```

### Логирование

Логи содержат информацию:
- Количество получённых записей
- Номер страницы
- Общее количество записей
- Ошибки при обработке запросов

## Переменные окружения

Убедитесь, что .env файл содержит:
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=internships
DB_USER=postgres
DB_PASSWORD=1111
```

## Производство

Для развёртывания в production используйте:

```bash
# С использованием gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app

# Или другой production-grade сервер
```

## Лицензия

Проект внутреннего использования.
