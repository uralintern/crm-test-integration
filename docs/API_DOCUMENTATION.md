# 1. ОСНОВНАЯ КОНФИГУРАЦИЯ API

## 1.1 Базовые параметры

| Параметр | Значение |
|----------|----------|
| **Base URL** | `/api` |
| **Host** | `localhost:8000` (dev) или домен (prod) |
| **Default Port** | `8000` |
| **Protocol** | HTTP/HTTPS |
| **Content-Type** | `application/json` |
| **Accept** | `application/json` |

### 1.2 Документация API

**Встроенная интерактивная документация:**

- **Swagger UI**: `/swagger/` - Интерактивный интерфейс для тестирования
- **ReDoc**: `/redoc/` - Красивая читаемая документация
- **OpenAPI JSON**: `/swagger.json` - Спецификация в формате OpenAPI 3.0
- **OpenAPI YAML**: `/swagger.yaml` - Спецификация в формате YAML

Доступ: <http://localhost:8000/swagger/>

### 1.3 Аутентификация

**Тип**: JWT (JSON Web Token)

**Методы передачи токена:**

```
# В header Authorization
Authorization: Bearer {access_token}

# Или в HTTP-only cookie (автоматически)
Cookie: access_token={token}
```

### 1.4 Трансформация данных (Client-Side)

Фронтенд автоматически трансформирует `snake_case` → `camelCase`:

| Backend | Frontend |
|---------|----------|
| `first_name` | `firstName` |
| `last_name` | `lastName` |
| `start_date` | `startDate` |
| `end_date` | `endDate` |
| `event_id` | `eventId` |
| `direction_id` | `directionId` |
| `project_id` | `projectId` |
| `user_id` | `userId` |
| `name` (Event/Direction/Project) | `title` |
| `end_app_date` | `applyDeadline` |
| `leader` | `organizer` |
| `date_sub` | `createdAt` |
| `is_approved` | `isApproved` |
| `is_positive` | `isPositive` |
| `is_active` | `isActive` |
| `vk_user_id` | `vkUserId` |
| `vk_confirmed_at` | `vkConfirmedAt` |

### 1.5 Стандартные Headers

```json
{
  "Content-Type": "application/json",
  "Accept": "application/json",
  "Authorization": "Bearer {token}",
  "X-Service-Token": "{token}" // для интеграций
}
```

---

## 2. АУТЕНТИФИКАЦИЯ И СЕССИЯ

### 2.1 POST /users/register/

**Назначение**: Регистрация нового пользователя в системе

**Метод**: `POST`

**URL**: `/api/users/register/`

**Аутентификация**: Не требуется

**Request Body** (application/json):

```json
{
  "username": "string (required, 3-150 символов, уникален)",
  "email": "user@example.com (required, валидный email, уникален)",
  "password": "string (required, минимум 8 символов, содержать буквы и цифры)",
  "password_confirm": "string (required, должен совпадать с password)",
  "surname": "string (required, 1-150 символов)",
  "name": "string (required, 1-150 символов)",
  "patronymic": "string (optional, 0-150 символов)"
}
```

**Response 201** (Created):

```json
{
  "id": 1,
  "username": "johndoe",
  "email": "john@example.com",
  "firstName": "John",
  "lastName": "Doe"
}
```

**Response 400** (Bad Request):

```json
{
  "username": ["Username already exists"],
  "email": ["User with this email already exists"],
  "password": ["Password must be at least 8 characters"],
  "non_field_errors": ["Password confirmation does not match"]
}
```

**cURL пример:**

```bash
curl -X POST http://localhost:8000/api/users/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "johndoe",
    "email": "john@example.com",
    "password": "SecurePass123",
    "password_confirm": "SecurePass123",
    "surname": "Doe",
    "name": "John"
  }'
```

---

### 2.2 POST /users/login/

**Назначение**: Вход в систему (получение JWT токена)

**Метод**: `POST`

**URL**: `/api/users/login/`

**Аутентификация**: Не требуется

**Request Body** (application/json):

```json
{
  "username": "string (required, username или email)",
  "password": "string (required, 1-128 символов)"
}
```

**Response 200** (OK):

```json
{
  "user": {
    "id": 1,
    "username": "johndoe",
    "email": "john@example.com",
    "firstName": "John",
    "lastName": "Doe",
    "managedEventIds": [1, 2, 3]
  },
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Set-Cookie** (HTTP-only):

```
access_token={token}; HttpOnly; SameSite=Lax
refresh_token={token}; HttpOnly; SameSite=Lax
```

**Response 401** (Unauthorized):

```json
{
  "detail": "No active account found with the given credentials"
}
```

**Response 400** (Bad Request):

```json
{
  "username": ["This field is required"],
  "password": ["This field is required"]
}
```

**cURL пример:**

```bash
curl -X POST http://localhost:8000/api/users/login/ \
  -H "Content-Type: application/json" \
  -c cookies.txt \
  -d '{
    "username": "johndoe",
    "password": "SecurePass123"
  }'
```

---

### 2.3 POST /users/logout/

**Назначение**: Выход из системы (инвалидация токена)

**Метод**: `POST`

**URL**: `/api/users/logout/`

**Аутентификация**: JWT Bearer Token (обязательно)

**Request Body**: `{}` (пусто)

**Response 200** (OK):

```json
{
  "message": "Successfully logged out"
}
```

**Response 401** (Unauthorized):

```json
{
  "detail": "Authentication credentials were not provided"
}
```

**cURL пример:**

```bash
curl -X POST http://localhost:8000/api/users/logout/ \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json"
```

---

### 2.4 POST /users/refresh/

**Назначение**: Обновление access_token используя refresh_token

**Метод**: `POST`

**URL**: `/api/users/refresh/`

**Аутентификация**: Не требуется (используется refresh_token из cookie)

**Request Body**: `{}` (пусто)

**Response 200** (OK):

```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Set-Cookie** (HTTP-only):

```
access_token={new_token}; HttpOnly; SameSite=Lax
refresh_token={token}; HttpOnly; SameSite=Lax
```

**Response 401** (Unauthorized):

```json
{
  "detail": "Token is invalid or expired"
}
```

**cURL пример:**

```bash
curl -X POST http://localhost:8000/api/users/refresh/ \
  -H "Content-Type: application/json" \
  -b cookies.txt
```

---

### 2.5 POST /users/password-reset/request/

**Назначение**: Запрос на сброс пароля (отправка ссылки на email)

**Метод**: `POST`

**URL**: `/api/users/password-reset/request/`

**Аутентификация**: Не требуется

**Request Body** (application/json):

```json
{
  "email": "user@example.com (required, валидный email)"
}
```

**Response 200** (OK):

```json
{
  "message": "Password reset link sent to your email"
}
```

**Response 400** (Bad Request):

```json
{
  "email": ["This field is required"],
  "non_field_errors": ["User with this email not found"]
}
```

**Письмо с ссылкой:**

```
Привет, {name}!

Для сброса пароля перейдите по ссылке:
http://localhost:3000/password-reset/{token}

Ссылка действительна 24 часа.
```

**cURL пример:**

```bash
curl -X POST http://localhost:8000/api/users/password-reset/request/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com"
  }'
```

---

### 2.6 POST /users/password-reset/confirm/

**Назначение**: Подтверждение сброса пароля (установка нового пароля)

**Метод**: `POST`

**URL**: `/api/users/password-reset/confirm/`

**Аутентификация**: Не требуется

**Request Body** (application/json):

```json
{
  "token": "string (required, token из письма, 40 символов)",
  "new_password": "string (required, минимум 8 символов)"
}
```

**Response 200** (OK):

```json
{
  "message": "Password successfully reset"
}
```

**Response 400** (Bad Request):

```json
{
  "token": ["Invalid or expired token"],
  "new_password": ["Password must be at least 8 characters"]
}
```

**cURL пример:**

```bash
curl -X POST http://localhost:8000/api/users/password-reset/confirm/ \
  -H "Content-Type: application/json" \
  -d '{
    "token": "abc123def456...",
    "new_password": "NewSecurePass456"
  }'
```

---

### 2.7 POST /users/confirm-email/

**Назначение**: Подтверждение email адреса пользователя

**Метод**: `POST`

**URL**: `/api/users/confirm-email/`

**Аутентификация**: Не требуется

**Request Body** (application/json):

```json
{
  "token": "string (required, token из письма верификации, 40 символов)"
}
```

**Response 200** (OK):

```json
{
  "message": "Email confirmed"
}
```

**Response 400** (Bad Request):

```json
{
  "token": ["Invalid or expired token"]
}
```

**cURL пример:**

```bash
curl -X POST http://localhost:8000/api/users/confirm-email/ \
  -H "Content-Type: application/json" \
  -d '{
    "token": "abc123def456..."
  }'
```

---

## 3. ПОЛЬЗОВАТЕЛИ И ПРОФИЛИ

### 3.1 GET /users/user-info/

**Назначение**: Получить полную информацию о текущем пользователе

**Метод**: `GET`

**URL**: `/api/users/user-info/`

**Аутентификация**: JWT Bearer Token (обязательно)

**Query Parameters**: Нет

**Response 200** (OK):

```json
{
  "id": 1,
  "username": "johndoe",
  "email": "john@example.com",
  "firstName": "John",
  "lastName": "Doe",
  "profile": {
    "surname": "Doe",
    "name": "John",
    "patronymic": "Alexander",
    "telegram": "@johndoe",
    "email": "john@example.com",
    "course": 2,
    "university": "Moscow State University",
    "vk": "https://vk.com/johndoe",
    "vkUserId": 123456789,
    "vkConfirmedAt": "2024-01-15T10:30:00Z",
    "job": "Software Developer",
    "workplace": "Tech Company Inc",
    "specialty": "Backend Development",
    "about": "Passionate about Python and Django"
  },
  "managedEventIds": [1, 2, 3],
  "crm_roles": [
    {
      "roleType": "admin",
      "contentType": "event",
      "objectId": 1
    }
  ]
}
```

**Response 401** (Unauthorized):

```json
{
  "detail": "Authentication credentials were not provided"
}
```

**cURL пример:**

```bash
curl -X GET http://localhost:8000/api/users/user-info/ \
  -H "Authorization: Bearer {access_token}"
```

---

### 3.2 GET /users/

**Назначение**: Получить список всех пользователей системы

**Метод**: `GET`

**URL**: `/api/users/`

**Аутентификация**: JWT Bearer Token (обязательно)

**Query Parameters**:

- `search` (string, optional) - поиск по username, first_name, last_name, email. Минимум 2 символа.

**Response 200** (OK):

```json
[
  {
    "id": 1,
    "username": "johndoe",
    "email": "john@example.com",
    "firstName": "John",
    "lastName": "Doe"
  },
  {
    "id": 2,
    "username": "janedoe",
    "email": "jane@example.com",
    "firstName": "Jane",
    "lastName": "Doe"
  }
]
```

**Response 401** (Unauthorized):

```json
{
  "detail": "Authentication credentials were not provided"
}
```

**cURL пример:**

```bash
# Все пользователи
curl -X GET http://localhost:8000/api/users/ \
  -H "Authorization: Bearer {access_token}"

# Поиск
curl -X GET "http://localhost:8000/api/users/?search=john" \
  -H "Authorization: Bearer {access_token}"
```

---

### 3.3 GET/PUT /users/profile/

**Назначение**: Получить или обновить профиль текущего пользователя

**Метод**: `GET`, `PUT`

**URL**: `/api/users/profile/`

**Аутентификация**: JWT Bearer Token (обязательно)

#### GET - Получить профиль

**Response 200** (OK):

```json
{
  "surname": "Doe",
  "name": "John",
  "patronymic": "Alexander",
  "telegram": "@johndoe",
  "email": "john@example.com",
  "course": 2,
  "university": "Moscow State University",
  "vk": "https://vk.com/johndoe",
  "vkUserId": 123456789,
  "vkConfirmedAt": "2024-01-15T10:30:00Z",
  "job": "Software Developer",
  "workplace": "Tech Company Inc",
  "specialty": "Backend Development",
  "about": "Passionate about Python and Django"
}
```

#### PUT - Обновить профиль

**Request Body** (application/json, все поля опциональны):

```json
{
  "surname": "string (0-150 символов)",
  "name": "string (0-150 символов)",
  "patronymic": "string (0-150 символов)",
  "telegram": "string (0-150 символов)",
  "email": "string (валидный email)",
  "course": "integer (0-999)",
  "university": "string (0-255 символов)",
  "vk": "string (0-255 символов, URL)",
  "job": "string (0-255 символов)",
  "workplace": "string (0-255 символов)",
  "specialty": "string (0-255 символов)",
  "about": "string (0-10000 символов, Text)"
}
```

**Response 200** (OK): Same as GET

**Response 400** (Bad Request):

```json
{
  "email": ["Enter a valid email address"],
  "course": ["Ensure this value is less than or equal to 999"]
}
```

**cURL примеры:**

```bash
# Получить профиль
curl -X GET http://localhost:8000/api/users/profile/ \
  -H "Authorization: Bearer {access_token}"

# Обновить профиль
curl -X PUT http://localhost:8000/api/users/profile/ \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "surname": "Smith",
    "telegram": "@john_smith",
    "specialty": "Full Stack Development"
  }'
```

---

## 4. СПРАВОЧНИКИ

### 4.1 GET /users/specializations/

**Назначение**: Получить список всех доступных специализаций

**Метод**: `GET`

**URL**: `/api/users/specializations/`

**Аутентификация**: Не требуется (публичный эндпоинт)

**Query Parameters**: Нет

**Response 200** (OK):

```json
[
  {
    "id": 1,
    "name": "Frontend",
    "description": "Frontend development with React, Vue, Angular"
  },
  {
    "id": 2,
    "name": "Backend",
    "description": "Backend development with Python, Node.js, Java"
  },
  {
    "id": 3,
    "name": "Full Stack",
    "description": "Full stack web development"
  },
  {
    "id": 4,
    "name": "DevOps",
    "description": "DevOps, CI/CD, Infrastructure"
  }
]
```

**cURL пример:**

```bash
curl -X GET http://localhost:8000/api/users/specializations/
```

---

### 4.2 GET /users/statuses/

**Назначение**: Получить список всех статусов приложений

**Метод**: `GET`

**URL**: `/api/users/statuses/`

**Аутентификация**: JWT Bearer Token (обязательно)

**Query Parameters**: Нет

**Response 200** (OK):

```json
[
  {
    "id": 1,
    "name": "Прислал заявку",
    "description": "Пользователь подал заявку",
    "isPositive": true
  },
  {
    "id": 2,
    "name": "Прохождение тестирования",
    "description": "Пользователь проходит тест",
    "isPositive": true
  },
  {
    "id": 3,
    "name": "Не перешёл к тестированию",
    "description": "",
    "isPositive": false
  },
  {
    "id": 4,
    "name": "Не прошел тестирование",
    "description": "Пользователь не набрал нужный балл",
    "isPositive": false
  },
  {
    "id": 5,
    "name": "Отправлена ссылка на орг. чат",
    "description": "",
    "isPositive": true
  },
  {
    "id": 6,
    "name": "Не добавился в орг чат",
    "description": "",
    "isPositive": false
  },
  {
    "id": 7,
    "name": "Добавился в орг. чат",
    "description": "",
    "isPositive": true
  },
  {
    "id": 8,
    "name": "Набор завершён",
    "description": "Завершен набор на программу",
    "isPositive": false
  }
]
```

**cURL пример:**

```bash
curl -X GET http://localhost:8000/api/users/statuses/ \
  -H "Authorization: Bearer {access_token}"
```

---

## 5. МЕРОПРИЯТИЯ (EVENTS)

### 5.1 GET /users/events/

**Назначение**: Получить список всех мероприятий

**Метод**: `GET`

**URL**: `/api/users/events/`

**Аутентификация**: JWT Bearer Token (обязательно)

**Query Parameters**:

- `search` (string, optional) - поиск по названию события. Минимум 2 символа.
- `is_archived` (boolean, optional) - фильтр по статусу архивирования. Значения: `true`, `false`.
- `specialization` (integer, optional) - фильтр по ID специализации
- `ordering` (string, optional) - сортировка: `name`, `-name`, `start_date`, `-start_date`, `created_at`, `-created_at`

**Response 200** (OK):

```json
[
  {
    "id": 1,
    "title": "Summer Bootcamp 2024",
    "description": "Intensive 3-month Python backend development program",
    "stage": "Hiring",
    "startDate": "2024-06-01",
    "endDate": "2024-08-31",
    "applyDeadline": "2024-05-31T23:59:59Z",
    "isArchived": false,
    "archivedAt": null,
    "specializationId": 2,
    "organizer": 5,
    "organizers": [5, 6, 7],
    "orgChatUrl": "https://vk.com/summerbootcamp2024",
    "orgChatPeerId": 123456789,
    "applicationFormFields": [
      {
        "name": "experience_level",
        "type": "select",
        "options": ["beginner", "intermediate", "advanced"]
      }
    ]
  }
]
```

**cURL пример:**

```bash
# Все события
curl -X GET http://localhost:8000/api/users/events/ \
  -H "Authorization: Bearer {access_token}"

# Поиск и фильтры
curl -X GET "http://localhost:8000/api/users/events/?search=bootcamp&is_archived=false&specialization=2" \
  -H "Authorization: Bearer {access_token}"
```

---

### 5.2 POST /users/events/

**Назначение**: Создать новое мероприятие

**Метод**: `POST`

**URL**: `/api/users/events/`

**Аутентификация**: JWT Bearer Token (обязательно, требуется роль curator или admin)

**Request Body** (application/json):

```json
{
  "name": "string (required, 1-255 символов, название события)",
  "description": "string (optional, 0-10000 символов, описание)",
  "stage": "string (required, 1-100 символов, текущий этап: Hiring, Active, Completion, Finished и т.д.)",
  "start_date": "date (required, YYYY-MM-DD формат)",
  "end_date": "date (required, YYYY-MM-DD формат, должна быть >= start_date)",
  "end_app_date": "datetime (required, YYYY-MM-DDTHH:MM:SSZ формат, дедлайн подачи заявок)",
  "specialization": "integer (optional, ID специализации из справочника)",
  "leader": "integer (optional, ID пользователя-лидера)",
  "organizers": "array of integers (optional, массив ID организаторов)",
  "org_chat_url": "string (optional, URL, например https://vk.com/groupname)",
  "org_chat_peer_id": "integer (optional, VK peer ID)",
  "application_form_fields": "array of objects (optional, поля для заявки)"
}
```

**Response 201** (Created):

```json
{
  "id": 1,
  "title": "Summer Bootcamp 2024",
  "description": "...",
  "stage": "Hiring",
  "startDate": "2024-06-01",
  "endDate": "2024-08-31",
  "applyDeadline": "2024-05-31T23:59:59Z",
  "isArchived": false,
  "specializationId": 2,
  "organizer": 5,
  "organizers": [5],
  "orgChatUrl": "https://vk.com/...",
  "orgChatPeerId": 0,
  "applicationFormFields": []
}
```

**Response 400** (Bad Request):

```json
{
  "name": ["This field is required"],
  "start_date": ["Ensure this field has no more than 255 characters"],
  "end_date": ["end_date must be >= start_date"],
  "end_app_date": ["Invalid datetime format"]
}
```

**Response 403** (Forbidden):

```json
{
  "detail": "You do not have permission to perform this action."
}
```

**cURL пример:**

```bash
curl -X POST http://localhost:8000/api/users/events/ \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Python Summer Camp",
    "description": "Learn Python from scratch",
    "stage": "Hiring",
    "start_date": "2024-06-01",
    "end_date": "2024-08-31",
    "end_app_date": "2024-05-31T23:59:59Z",
    "specialization": 2,
    "org_chat_url": "https://vk.com/pythoncamp"
  }'
```

---

### 5.3 GET /users/events/{event_id}/

**Назначение**: Получить информацию о конкретном мероприятии

**Метод**: `GET`

**URL**: `/api/users/events/{event_id}/`

**Параметры пути**:

- `event_id` (integer, required) - ID мероприятия

**Response 200** (OK): Same as list item

**Response 404** (Not Found):

```json
{
  "detail": "Not found."
}
```

**cURL пример:**

```bash
curl -X GET http://localhost:8000/api/users/events/1/ \
  -H "Authorization: Bearer {access_token}"
```

---

### 5.4 PUT /users/events/{event_id}/

**Назначение**: Обновить информацию о мероприятии

**Метод**: `PUT`

**URL**: `/api/users/events/{event_id}/`

**Аутентификация**: JWT Bearer Token (обязательно, требуется быть куратором/админом события)

**Request Body**: Same as POST (все поля опциональны для PATCH, обязательны для PUT)

**Response 200** (OK): Same as GET

**Response 403** (Forbidden):

```json
{
  "detail": "You do not have permission to perform this action."
}
```

**cURL пример:**

```bash
curl -X PUT http://localhost:8000/api/users/events/1/ \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "stage": "Active",
    "description": "Updated description"
  }'
```

---

### 5.5 DELETE /users/events/{event_id}/

**Назначение**: Удалить мероприятие

**Метод**: `DELETE`

**URL**: `/api/users/events/{event_id}/`

**Аутентификация**: JWT Bearer Token (обязательно, требуется роль curator/admin)

**Response 204** (No Content): Пусто

**Response 403** (Forbidden):

```json
{
  "detail": "You do not have permission to perform this action."
}
```

**cURL пример:**

```bash
curl -X DELETE http://localhost:8000/api/users/events/1/ \
  -H "Authorization: Bearer {access_token}"
```

---

### 5.6 GET /users/events/{event_id}/export/details.docx/

**Назначение**: Экспортировать детали события в DOCX файл

**Метод**: `GET`

**URL**: `/api/users/events/{event_id}/export/details.docx/`

**Response 200** (OK): Binary DOCX файл

**Response 404** (Not Found):

```json
{
  "detail": "Not found."
}
```

**cURL пример:**

```bash
curl -X GET http://localhost:8000/api/users/events/1/export/details.docx/ \
  -H "Authorization: Bearer {access_token}" \
  -o event_details.docx
```

---

### 5.7 GET /users/events/{event_id}/export/applications.xlsx/

**Назначение**: Экспортировать список приложений события в XLSX файл

**Метод**: `GET`

**URL**: `/api/users/events/{event_id}/export/applications.xlsx/`

**Response 200** (OK): Binary XLSX файл

**cURL пример:**

```bash
curl -X GET http://localhost:8000/api/users/events/1/export/applications.xlsx/ \
  -H "Authorization: Bearer {access_token}" \
  -o applications.xlsx
```

---

## 6. НАПРАВЛЕНИЯ (DIRECTIONS)

### 6.1 GET /users/events/{event_id}/directions/

**Назначение**: Получить список направлений мероприятия

**Метод**: `GET`

**URL**: `/api/users/events/{event_id}/directions/`

**Response 200** (OK):

```json
[
  {
    "id": 1,
    "eventId": 1,
    "title": "Backend Track",
    "description": "Python backend development with Django",
    "leaderId": 5,
    "organizer": 5
  }
]
```

**cURL пример:**

```bash
curl -X GET http://localhost:8000/api/users/events/1/directions/ \
  -H "Authorization: Bearer {access_token}"
```

---

### 6.2 POST /users/events/{event_id}/directions/

**Назначение**: Создать новое направление

**Метод**: `POST`

**URL**: `/api/users/events/{event_id}/directions/`

**Request Body** (application/json):

```json
{
  "name": "string (required, 1-255 символов)",
  "description": "string (optional, текст описания)",
  "leader": "integer (optional, ID пользователя-лидера)"
}
```

**Response 201** (Created): Same as GET list item

**cURL пример:**

```bash
curl -X POST http://localhost:8000/api/users/events/1/directions/ \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Backend Track",
    "description": "Python backend development",
    "leader": 5
  }'
```

---

### 6.3 GET /users/events/{event_id}/directions/{direction_id}/

**Назначение**: Получить информацию о направлении

**Метод**: `GET`

**URL**: `/api/users/events/{event_id}/directions/{direction_id}/`

**Response 200** (OK): Same as list item

---

### 6.4 PUT /users/events/{event_id}/directions/{direction_id}/

**Назначение**: Обновить направление

**Метод**: `PUT`

**URL**: `/api/users/events/{event_id}/directions/{direction_id}/`

**Request Body**: Same as POST

**Response 200** (OK): Same as GET

---

### 6.5 DELETE /users/events/{event_id}/directions/{direction_id}/

**Назначение**: Удалить направление

**Метод**: `DELETE`

**URL**: `/api/users/events/{event_id}/directions/{direction_id}/`

**Response 204** (No Content): Пусто

---

### 6.6 GET /users/directions/

**Назначение**: Получить все направления текущего пользователя

**Метод**: `GET`

**URL**: `/api/users/directions/`

**Query Parameters**:

- `event` (integer, optional) - фильтр по ID события

**Response 200** (OK): Array of direction objects

**cURL пример:**

```bash
curl -X GET http://localhost:8000/api/users/directions/ \
  -H "Authorization: Bearer {access_token}"
```

---

## 7. ПРОЕКТЫ (PROJECTS)

### 7.1 GET /users/events/{event_id}/directions/{direction_id}/projects/

**Назначение**: Получить список проектов в направлении

**Метод**: `GET`

**URL**: `/api/users/events/{event_id}/directions/{direction_id}/projects/`

**Response 200** (OK):

```json
[
  {
    "id": 1,
    "directionId": 1,
    "title": "E-commerce Platform",
    "description": "Build an e-commerce platform with Django",
    "curator": 10,
    "teams": 3,
    "createdAt": "2024-01-01T10:00:00Z",
    "updatedAt": "2024-01-15T10:00:00Z"
  }
]
```

**cURL пример:**

```bash
curl -X GET http://localhost:8000/api/users/events/1/directions/1/projects/ \
  -H "Authorization: Bearer {access_token}"
```

---

### 7.2 POST /users/events/{event_id}/directions/{direction_id}/projects/

**Назначение**: Создать новый проект

**Метод**: `POST`

**URL**: `/api/users/events/{event_id}/directions/{direction_id}/projects/`

**Request Body** (application/json):

```json
{
  "name": "string (required, 1-255 символов)",
  "description": "string (optional)",
  "curator": "integer (optional, ID куратора проекта)",
  "teams": "integer (optional, количество команд, 0-999)"
}
```

**Response 201** (Created): Same as GET list item

---

### 7.3 GET /users/projects/{project_id}/

**Назначение**: Получить информацию о проекте

**Метод**: `GET`

**URL**: `/api/users/projects/{project_id}/`

**Response 200** (OK): Same as list item

---

### 7.4 PUT /users/projects/{project_id}/

**Назначение**: Обновить проект

**Метод**: `PUT`

**URL**: `/api/users/projects/{project_id}/`

**Request Body**: Same as POST

**Response 200** (OK): Same as GET

---

### 7.5 DELETE /users/projects/{project_id}/

**Назначение**: Удалить проект

**Метод**: `DELETE`

**URL**: `/api/users/projects/{project_id}/`

**Response 204** (No Content): Пусто

---

### 7.6 GET /users/projects/

**Назначение**: Получить проекты текущего пользователя

**Метод**: `GET`

**URL**: `/api/users/projects/`

**Query Parameters**:

- `curator` (integer, optional) - фильтр по куратору
- `direction` (integer, optional) - фильтр по направлению

**Response 200** (OK): Array of project objects

---

## 8. ЗАЯВКИ (APPLICATIONS)

### 8.1 GET /users/applications/

**Назначение**: Получить список заявок пользователя

**Метод**: `GET`

**URL**: `/api/users/applications/`

**Аутентификация**: JWT Bearer Token (обязательно)

**Query Parameters**:

- `status` (string, optional) - фильтр по статусу
- `event` (integer, optional) - фильтр по событию
- `is_approved` (boolean, optional) - фильтр по одобрению

**Response 200** (OK):

```json
[
  {
    "id": 1,
    "userId": 1,
    "eventId": 1,
    "directionId": 1,
    "projectId": null,
    "specializationId": 2,
    "status": "Прошел тестирование",
    "message": "I'm very interested in this program",
    "isLink": false,
    "isApproved": true,
    "comment": "Good candidate, recommended for acceptance",
    "createdAt": "2024-01-01T10:00:00Z",
    "dateEnd": "2024-01-31T23:59:59Z",
    "testSessionId": 123456,
    "customFormAnswers": {
      "experience_level": "intermediate"
    }
  }
]
```

**cURL пример:**

```bash
curl -X GET http://localhost:8000/api/users/applications/ \
  -H "Authorization: Bearer {access_token}"

# С фильтрами
curl -X GET "http://localhost:8000/api/users/applications/?status=Прошел%20тестирование&event=1" \
  -H "Authorization: Bearer {access_token}"
```

---

### 8.2 POST /users/events/{event_id}/directions/{direction_id}/applications/

**Назначение**: Создать новую заявку (подать заявку на участие)

**Метод**: `POST`

**URL**: `/api/users/events/{event_id}/directions/{direction_id}/applications/`

**Аутентификация**: JWT Bearer Token (обязательно, пользователь не должен иметь уже открытую заявку)

**Request Body** (application/json):

```json
{
  "message": "string (optional, текст сопроводительного письма, 0-10000 символов)",
  "specialization": "integer (optional, ID специализации)",
  "custom_form_answers": "object (optional, ответы на доп. вопросы события)"
}
```

**Response 201** (Created): Same as GET list item with status "Прислал заявку"

**Response 400** (Bad Request):

```json
{
  "non_field_errors": ["You already have an active application for this event"]
}
```

**cURL пример:**

```bash
curl -X POST http://localhost:8000/api/users/events/1/directions/1/applications/ \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am very interested in this opportunity",
    "specialization": 2,
    "custom_form_answers": {
      "experience_level": "intermediate",
      "portfolio_url": "https://github.com/johndoe"
    }
  }'
```

---

### 8.3 GET /users/applications/{application_id}/

**Назначение**: Получить информацию о конкретной заявке

**Метод**: `GET`

**URL**: `/api/users/applications/{application_id}/`

**Response 200** (OK): Same as list item

**Response 404** (Not Found):

```json
{
  "detail": "Not found."
}
```

---

### 8.4 PUT /users/applications/{application_id}/

**Назначение**: Обновить заявку (одобрение, комментарии)

**Метод**: `PUT`

**URL**: `/api/users/applications/{application_id}/`

**Аутентификация**: JWT Bearer Token (обязательно, требуется быть куратором/админом)

**Request Body** (application/json):

```json
{
  "is_approved": "boolean (optional, одобрение заявки)",
  "comment": "string (optional, комментарий куратора, 0-10000 символов)",
  "status": "integer (optional, ID нового статуса)"
}
```

**Response 200** (OK): Updated application object

**cURL пример:**

```bash
curl -X PUT http://localhost:8000/api/users/applications/1/ \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "is_approved": true,
    "comment": "Excellent candidate, approved for testing"
  }'
```

---

### 8.5 DELETE /users/applications/{application_id}/

**Назначение**: Удалить/отозвать заявку

**Метод**: `DELETE`

**URL**: `/api/users/applications/{application_id}/`

**Response 204** (No Content): Пусто

---

## 9. ТЕСТИРОВАНИЕ (TESTING)

### 9.1 GET /users/integration/testing/application/{application_id}/context/

**Назначение**: Получить контекст для тестирования приложения (список доступных тестов, текущую сессию, результаты)

**Метод**: `GET`

**URL**: `/api/users/integration/testing/application/{application_id}/context/`

**Аутентификация**: JWT Bearer Token (обязательно)

**Response 200** (OK):

```json
{
  "applicationId": 1,
  "availableTests": [
    {
      "id": 1,
      "title": "Python Basics",
      "description": "Test your Python knowledge",
      "eventId": 1,
      "specializationId": 2,
      "entry": 0,
      "isActive": true,
      "questionCount": 20,
      "passingScore": 70,
      "timeLimitMinutes": 60,
      "attemptsAllowed": 3
    },
    {
      "id": 2,
      "title": "Django Advanced",
      "description": "Advanced Django patterns",
      "eventId": 1,
      "specializationId": 2,
      "entry": 1,
      "isActive": true,
      "questionCount": 30,
      "passingScore": 75,
      "timeLimitMinutes": 90,
      "attemptsAllowed": 2
    }
  ],
  "currentSession": {
    "id": 5,
    "sessionId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "testId": 1,
    "applicationId": 1,
    "userId": 1,
    "startedAt": "2024-01-01T10:00:00Z",
    "completedAt": null,
    "status": "in_progress",
    "createdAt": "2024-01-01T09:55:00Z"
  },
  "latestResult": {
    "id": 1,
    "testId": 1,
    "applicationId": 1,
    "sessionId": null,
    "score": 85,
    "isPassed": true,
    "completedAt": "2024-01-01T11:15:00Z"
  }
}
```

**Response 404** (Not Found):

```json
{
  "detail": "Application not found"
}
```

**cURL пример:**

```bash
curl -X GET http://localhost:8000/api/users/integration/testing/application/1/context/ \
  -H "Authorization: Bearer {access_token}"
```

---

### 9.2 POST /users/integration/testing/session/

**Назначение**: Создать или обновить сессию тестирования

**Метод**: `POST`

**URL**: `/api/users/integration/testing/session/`

**Аутентификация**: JWT Bearer Token (обязательно) или X-Service-Token для внешних сервисов

**Request Body** (application/json):

```json
{
  "application_id": "integer (required, ID заявки)",
  "test_id": "integer (required, ID теста)",
  "session_id": "string (optional, UUID сессии, генерируется если не передана)",
  "status": "string (optional, in_progress|completed|timeout, default: in_progress)"
}
```

**Response 201** (Created) или **200** (OK если обновляет):

```json
{
  "id": 5,
  "sessionId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "testId": 1,
  "applicationId": 1,
  "userId": 1,
  "startedAt": "2024-01-01T10:00:00Z",
  "completedAt": null,
  "status": "in_progress",
  "createdAt": "2024-01-01T09:55:00Z"
}
```

**Response 400** (Bad Request):

```json
{
  "application_id": ["This field is required"],
  "test_id": ["This field is required"]
}
```

**cURL пример:**

```bash
curl -X POST http://localhost:8000/api/users/integration/testing/session/ \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "application_id": 1,
    "test_id": 1,
    "status": "in_progress"
  }'
```

---

### 9.3 POST /users/integration/testing/result/

**Назначение**: Загрузить результат прохождения теста (вызывается тестирующим сервисом)

**Метод**: `POST`

**URL**: `/api/users/integration/testing/result/`

**Аутентификация**: X-Service-Token (обязательно для интеграций) или JWT Bearer Token

**Request Body** (application/json):

```json
{
  "application_id": "integer (required, ID заявки)",
  "test_id": "integer (required, ID теста)",
  "session_id": "string (optional, UUID сессии, на которой проводился тест)",
  "score": "integer (required, 0-100, балл за тест)",
  "is_passed": "boolean (required, прошел ли тест)",
  "answers_data": "object (optional, JSON с данными ответов: {question_id: answer_id, ...})"
}
```

**Response 201** (Created):

```json
{
  "id": 1,
  "testId": 1,
  "applicationId": 1,
  "sessionId": null,
  "userId": 1,
  "score": 85,
  "isPassed": true,
  "completedAt": "2024-01-01T11:15:00Z",
  "answersData": {
    "1": "1",
    "2": "3",
    "3": "2"
  }
}
```

**Response 400** (Bad Request):

```json
{
  "application_id": ["This field is required"],
  "score": ["Ensure this value is less than or equal to 100"]
}
```

**Response 403** (Forbidden - неверный X-Service-Token):

```json
{
  "detail": "Invalid service token"
}
```

**cURL пример (от тестирующего сервиса):**

```bash
curl -X POST http://localhost:8000/api/users/integration/testing/result/ \
  -H "X-Service-Token: {shared_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "application_id": 1,
    "test_id": 1,
    "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "score": 85,
    "is_passed": true,
    "answers_data": {
      "1": "1",
      "2": "3"
    }
  }'
```

---

### 9.4 GET /users/integration/testing/sso-link/

**Назначение**: Получить SSO ссылку и ticket для перехода на тестирующий сервис

**Метод**: `GET`

**URL**: `/api/users/integration/testing/sso-link/`

**Аутентификация**: JWT Bearer Token (обязательно)

**Query Parameters**:

- `application_id` (integer, optional) - ID заявки. Если не передана, используется первая доступная

**Response 200** (OK):

```json
{
  "url": "https://testing-service.com/auth?ticket=abc123def456&nonce=xyz789",
  "ticket": "abc123def456",
  "expiresIn": 3600
}
```

**Response 401** (Unauthorized):

```json
{
  "detail": "Authentication credentials were not provided"
}
```

**cURL пример:**

```bash
curl -X GET "http://localhost:8000/api/users/integration/testing/sso-link/?application_id=1" \
  -H "Authorization: Bearer {access_token}"
```

---

### 9.5 POST /users/integration/testing/sso-exchange/

**Назначение**: Обменять SSO ticket на информацию о пользователе и sessionId (вызывается тестирующим сервисом)

**Метод**: `POST`

**URL**: `/api/users/integration/testing/sso-exchange/`

**Аутентификация**: Не требуется (но может быть проверка на internal IP)

**Request Body** (application/json):

```json
{
  "ticket": "string (required, ticket полученный из /sso-link/)"
}
```

**Response 200** (OK):

```json
{
  "user": {
    "id": 1,
    "firstName": "John",
    "lastName": "Doe",
    "email": "john@example.com",
    "specializations": [1, 2, 3],
    "managedEventIds": [1, 2]
  },
  "sessionId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "expiresIn": 3600
}
```

**Response 400** (Bad Request):

```json
{
  "ticket": ["This field is required"]
}
```

**Response 401** (Unauthorized):

```json
{
  "detail": "Invalid or expired ticket"
}
```

**cURL пример (от тестирующего сервиса):**

```bash
curl -X POST http://localhost:8000/api/users/integration/testing/sso-exchange/ \
  -H "Content-Type: application/json" \
  -d '{
    "ticket": "abc123def456"
  }'
```

---

## 10. УВЕДОМЛЕНИЯ (NOTIFICATIONS)

### 10.1 GET /users/notifications/

**Назначение**: Получить список уведомлений пользователя

**Метод**: `GET`

**URL**: `/api/users/notifications/`

**Аутентификация**: JWT Bearer Token (обязательно)

**Query Parameters**:

- `is_read` (boolean, optional) - фильтр по статусу прочтения
- `ordering` (string, optional) - сортировка: `created_at`, `-created_at` (default)

**Response 200** (OK):

```json
[
  {
    "id": 1,
    "title": "Your application was approved",
    "description": "Your application for Summer Bootcamp has been approved",
    "message": "Congratulations! Your application was approved. You can now proceed to the next stage.",
    "isRead": false,
    "readAt": null,
    "createdAt": "2024-01-15T10:00:00Z"
  }
]
```

**cURL пример:**

```bash
curl -X GET http://localhost:8000/api/users/notifications/ \
  -H "Authorization: Bearer {access_token}"
```

---

### 10.2 POST /users/notifications/

**Назначение**: Создать уведомление для пользователя (только админ/куратор)

**Метод**: `POST`

**URL**: `/api/users/notifications/`

**Аутентификация**: JWT Bearer Token (требуется роль curator или admin)

**Request Body** (application/json):

```json
{
  "user_id": "integer (required, ID пользователя получателя)",
  "title": "string (required, 1-255 символов)",
  "description": "string (optional, 0-1000 символов)",
  "message": "string (required, полный текст уведомления)"
}
```

**Response 201** (Created): Same as GET list item

**Response 403** (Forbidden):

```json
{
  "detail": "You do not have permission to perform this action."
}
```

**cURL пример:**

```bash
curl -X POST http://localhost:8000/api/users/notifications/ \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "title": "Application Status Update",
    "description": "Your application was reviewed",
    "message": "Your application for the bootcamp has been approved. Next steps: complete the test."
  }'
```

---

### 10.3 GET /users/notifications/{notification_id}/

**Назначение**: Получить конкретное уведомление

**Метод**: `GET`

**URL**: `/api/users/notifications/{notification_id}/`

**Response 200** (OK): Same as list item

---

### 10.4 PUT /users/notifications/{notification_id}/

**Назначение**: Обновить уведомление (отметить как прочитанное)

**Метод**: `PUT`

**URL**: `/api/users/notifications/{notification_id}/`

**Request Body** (application/json):

```json
{
  "is_read": "boolean (required)"
}
```

**Response 200** (OK): Updated notification

**cURL пример:**

```bash
curl -X PUT http://localhost:8000/api/users/notifications/1/ \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "is_read": true
  }'
```

---

### 10.5 DELETE /users/notifications/{notification_id}/

**Назначение**: Удалить уведомление

**Метод**: `DELETE`

**URL**: `/api/users/notifications/{notification_id}/`

**Response 204** (No Content): Пусто

---

### 10.6 POST /users/notifications/mark-all-read/

**Назначение**: Пометить все уведомления как прочитанные

**Метод**: `POST`

**URL**: `/api/users/notifications/mark-all-read/`

**Request Body**: `{}` (пусто)

**Response 200** (OK):

```json
{
  "message": "All notifications marked as read"
}
```

---

### 10.7 POST /users/notifications/clear-all/

**Назначение**: Пометить все уведомления как прочитанные (альтернативный эндпоинт)

**Метод**: `POST`

**URL**: `/api/users/notifications/clear-all/`

**Response 200** (OK):

```json
{
  "message": "All notifications marked as read"
}
```

---

## 11. АВТОМАТИЗАЦИЯ (AUTOMATION)

### 11.1 GET /users/automation/{event_id}/

**Назначение**: Получить конфигурацию автоматизации события

**Метод**: `GET`

**URL**: `/api/users/automation/{event_id}/`

**Аутентификация**: JWT Bearer Token

**Response 200** (OK):

```json
{
  "id": 1,
  "scope": "crm",
  "eventId": 1,
  "stages": [
    {
      "id": "stage_1",
      "name": "Application Review",
      "description": "Review submitted applications"
    }
  ],
  "triggers": [
    {
      "id": "trigger_1",
      "event": "application_submitted",
      "condition": { "field": "specialization_id", "operator": "equals", "value": 1 }
    }
  ],
  "robots": [
    {
      "id": "robot_1",
      "name": "Auto Assign Testing",
      "trigger": "trigger_1",
      "actions": [
        { "type": "send_notification", "message": "Testing assigned" }
      ]
    }
  ],
  "updatedAt": "2024-01-15T10:00:00Z"
}
```

---

### 11.2 PUT /users/automation/{event_id}/

**Назначение**: Обновить конфигурацию автоматизации события

**Метод**: `PUT`

**URL**: `/api/users/automation/{event_id}/`

**Аутентификация**: JWT Bearer Token (требуется роль curator/admin)

**Request Body** (application/json):

```json
{
  "eventId": "integer (required)",
  "stages": "array (optional, массив определений этапов)",
  "triggers": "array (optional, массив определений триггеров)",
  "robots": "array (optional, массив определений автоматизаций)"
}
```

**Response 200** (OK): Updated config object

---

### 11.3 GET /users/automation/{event_id}/logs/

**Назначение**: Получить логи выполнения автоматизации события

**Метод**: `GET`

**URL**: `/api/users/automation/{event_id}/logs/`

**Query Parameters**:

- `status` (string, optional) - фильтр по статусу: `pending`, `success`, `skipped`, `failed`
- `entity_type` (string, optional) - фильтр по типу сущности: `application`, `test`, и т.д.
- `ordering` (string, optional) - сортировка: `created_at`, `-created_at` (default)
- `limit` (integer, optional) - максимум результатов (default: 100)

**Response 200** (OK):

```json
[
  {
    "id": 1,
    "eventId": 1,
    "teamId": null,
    "entityType": "application",
    "entityId": "123",
    "eventCode": "application_created",
    "ruleKind": "trigger",
    "ruleId": "trigger_1",
    "runKey": "app_123_trigger_1_20240101",
    "status": "success",
    "message": "Automation executed successfully",
    "context": { "application_id": 123, "status": "testing" },
    "scheduledFor": "2024-01-01T10:00:00Z",
    "executedAt": "2024-01-01T10:00:05Z",
    "createdAt": "2024-01-01T09:59:55Z"
  }
]
```

---

### 11.4 POST /users/automation/{event_id}/attachments/

**Назначение**: Загрузить прикрепленный файл для автоматизации

**Метод**: `POST`

**URL**: `/api/users/automation/{event_id}/attachments/`

**Content-Type**: `multipart/form-data`

**Form Data**:

- `file` (file, required) - Документ (DOCX, PDF, PPTX, TXT). Максимум 10MB.

**Response 201** (Created):

```json
{
  "id": 1,
  "configId": 1,
  "file": "/media/automation/2024/01/document_abc123.pdf",
  "uploadedAt": "2024-01-01T10:00:00Z",
  "createdBy": 1
}
```

---

### 11.5 GET /users/automation/{event_id}/attachments/

**Назначение**: Получить список прикрепленных файлов

**Метод**: `GET`

**URL**: `/api/users/automation/{event_id}/attachments/`

**Response 200** (OK):

```json
[
  {
    "id": 1,
    "file": "/media/automation/2024/01/document_abc123.pdf",
    "uploadedAt": "2024-01-01T10:00:00Z",
    "createdBy": 1
  }
]
```

---

### 11.6 DELETE /users/automation/{event_id}/attachments/{attachment_id}/

**Назначение**: Удалить прикрепленный файл

**Метод**: `DELETE`

**URL**: `/api/users/automation/{event_id}/attachments/{attachment_id}/`

**Response 204** (No Content): Пусто

---

## 12. ПЛАНИРОВЩИК (PLANNER)

### 12.1 GET /api/planner/teams/desks/

**Назначение**: Получить доски планировщика всех команд (доступные пользователю)

**Метод**: `GET`

**URL**: `/api/planner/teams/desks/`

**Аутентификация**: JWT Bearer Token (обязательно)

**Query Parameters**:

- `event` (integer, optional) - фильтр по событию
- `curator` (integer, optional) - фильтр по куратору

**Response 200** (OK):

```json
[
  {
    "id": 1,
    "teamId": 1,
    "teamName": "Backend Team",
    "curatorId": 5,
    "memberIds": [1, 2, 3, 4],
    "parentTasks": [
      {
        "id": "task_1",
        "title": "API Development",
        "status": "В работе",
        "assigneeId": 1
      }
    ],
    "subtasks": [
      {
        "id": "task_1_1",
        "title": "User Endpoints",
        "parentId": "task_1",
        "status": "Запланировано"
      }
    ],
    "columns": ["Запланировано", "В работе", "На проверке", "Готово"],
    "updatedAt": "2024-01-15T10:00:00Z"
  }
]
```

---

### 12.2 GET /api/planner/teams/{team_id}/desk/

**Назначение**: Получить доску планировщика конкретной команды

**Метод**: `GET`

**URL**: `/api/planner/teams/{team_id}/desk/`

**Response 200** (OK): Same as list item

---

### 12.3 PUT /api/planner/teams/{team_id}/desk/

**Назначение**: Обновить доску планировщика (обновить задачи и статусы)

**Метод**: `PUT`

**URL**: `/api/planner/teams/{team_id}/desk/`

**Аутентификация**: JWT Bearer Token (требуется быть куратором/членом команды)

**Request Body** (application/json):

```json
{
  "teamName": "string (optional, новое имя команды)",
  "curatorId": "integer (optional)",
  "memberIds": "array of integers (optional, обновить членов команды)",
  "parentTasks": "array of objects (optional, основные задачи)",
  "subtasks": "array of objects (optional, подзадачи)",
  "columns": "array of strings (optional, колонки канбан-доски)"
}
```

**Response 200** (OK): Updated desk object

**cURL пример:**

```bash
curl -X PUT http://localhost:8000/api/planner/teams/1/desk/ \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "parentTasks": [
      {
        "id": "task_1",
        "title": "API Development",
        "status": "В работе",
        "assigneeId": 1
      }
    ],
    "subtasks": [
      {
        "id": "task_1_1",
        "title": "User Endpoints",
        "parentId": "task_1",
        "status": "На проверке"
      }
    ]
  }'
```

---

### 12.4 GET /api/planner/automation/{event_id}/

**Назначение**: Получить конфигурацию автоматизации планировщика для события

**Метод**: `GET`

**URL**: `/api/planner/automation/{event_id}/`

**Response 200** (OK): Same structure as CRM automation config

---

### 12.5 PUT /api/planner/automation/{event_id}/

**Назначение**: Обновить конфигурацию автоматизации планировщика

**Метод**: `PUT`

**URL**: `/api/planner/automation/{event_id}/`

**Request Body**: Same as CRM automation

**Response 200** (OK): Updated config object

---

### 12.6 GET /api/planner/automation/{event_id}/logs/

**Назначение**: Получить логи выполнения автоматизации планировщика

**Метод**: `GET`

**URL**: `/api/planner/automation/{event_id}/logs/`

**Query Parameters**: Same as CRM automation logs

**Response 200** (OK): Array of execution log objects

---

### 12.7 POST /api/planner/automation/run-deadline-scan/

**Назначение**: Запустить сканирование дедлайнов (только администратор)

**Метод**: `POST`

**URL**: `/api/planner/automation/run-deadline-scan/`

**Аутентификация**: JWT Bearer Token (требуется роль admin)

**Request Body**: `{}` (пусто)

**Response 200** (OK):

```json
{
  "message": "Deadline scan completed",
  "tasksUpdated": 5,
  "logsCreated": 5
}
```

**cURL пример:**

```bash
curl -X POST http://localhost:8000/api/planner/automation/run-deadline-scan/ \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

### 12.8 POST /api/planner/automation/run-pending/

**Назначение**: Запустить обработку ожидающих автоматизаций (только администратор)

**Метод**: `POST`

**URL**: `/api/planner/automation/run-pending/`

**Request Body**: `{}` (пусто)

**Response 200** (OK):

```json
{
  "message": "Pending automations processed",
  "runsExecuted": 3,
  "logsCreated": 3
}
```

---

## 13. WEBSOCKET КОНТРАКТЫ

### 13.1 Подключение к WebSocket

**Протокол**: `ws://` или `wss://` (для HTTPS)

**URL**: `ws://localhost:8000/ws/planner/team/{team_id}/`

**Параметры подключения**:

- `token` (query param, required) - JWT access token

**Полный URL пример**:

```
ws://localhost:8000/ws/planner/team/1/?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Аутентификация**: JWT токен в query параметре

---

### 13.2 Сообщения от сервера

#### Обновление доски команды (desk_update)

**Когда отправляется**: Когда кто-то из команды обновит доску

```json
{
  "type": "desk_update",
  "data": {
    "teamId": 1,
    "teamName": "Backend Team",
    "curatorId": 5,
    "memberIds": [1, 2, 3, 4],
    "parentTasks": [...],
    "subtasks": [...],
    "columns": ["Запланировано", "В работе", "На проверке", "Готово"],
    "updatedAt": "2024-01-15T10:00:00Z",
    "updatedBy": 1
  }
}
```

#### Присоединение пользователя (user_joined)

**Когда отправляется**: Когда пользователь присоединился к WebSocket

```json
{
  "type": "user_joined",
  "data": {
    "userId": 1,
    "userName": "John Doe",
    "userEmail": "john@example.com",
    "timestamp": "2024-01-15T10:00:00Z"
  }
}
```

#### Отключение пользователя (user_left)

**Когда отправляется**: Когда пользователь отключился от WebSocket

```json
{
  "type": "user_left",
  "data": {
    "userId": 1,
    "userName": "John Doe",
    "timestamp": "2024-01-15T10:00:00Z"
  }
}
```

---

### 13.3 Сообщения от клиента

#### Отправить обновление доски (update_desk)

```json
{
  "type": "update_desk",
  "data": {
    "parentTasks": [
      {
        "id": "task_1",
        "title": "API Development",
        "status": "В работе",
        "assigneeId": 1
      }
    ],
    "subtasks": [
      {
        "id": "task_1_1",
        "title": "User Endpoints",
        "parentId": "task_1",
        "status": "На проверке"
      }
    ],
    "columns": ["Запланировано", "В работе", "На проверке", "Готово"]
  }
}
```

#### Пинг (ping)

**Назначение**: Поддержание соединения (keep-alive)

```json
{
  "type": "ping"
}
```

**Ответ сервера**:

```json
{
  "type": "pong"
}
```

---

## 14. ИНТЕГРАЦИИ

### 14.1 VK Integration

#### POST /api/integrations/vk/notify-application-testing-started/

**Назначение**: Отправить уведомление в VK чат при начале тестирования (вызывается внутренними системами)

**Метод**: `POST`

**URL**: `/api/integrations/vk/notify-application-testing-started/`

**Аутентификация**: X-Service-Token (обязательно)

**Request Body** (application/json):

```json
{
  "application_id": "integer (required, ID заявки)",
  "peer_id": "integer (required, VK peer ID чата)"
}
```

**Response 200** (OK):

```json
{
  "message": "Notification sent successfully",
  "notification_id": "abc123"
}
```

**Response 400** (Bad Request):

```json
{
  "detail": "Application or peer_id not found"
}
```

**Response 403** (Forbidden - неверный token):

```json
{
  "detail": "Invalid service token"
}
```

**cURL пример (от тестирующего сервиса):**

```bash
curl -X POST http://localhost:8000/api/integrations/vk/notify-application-testing-started/ \
  -H "X-Service-Token: {shared_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "application_id": 1,
    "peer_id": 123456789
  }'
```
