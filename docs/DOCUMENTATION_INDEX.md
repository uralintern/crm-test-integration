# RIC CRM Planner - Документация. Индекс и обзор

## 📚 Содержание документации

Этот пакет содержит полную документацию проекта RIC CRM Planner, включающую схему БД и API контракты.

## 🗂️ Структура проекта

```
crm-test-integration/
│
├── DATABASE_AND_API_DOCUMENTATION.md      ← Главный документ
├── API_QUICK_REFERENCE.md                ← Быстрая справка
├── DATABASE_SCHEMA_DETAILED.md            ← Детальная схема
├── DOCUMENTATION_INDEX.md                 ← Этот файл
│
├── ric-crm-planner/                       ← Основной проект
│   ├── docker-compose.yml
│   ├── back/                              ← Django Backend
│   │   ├── requirements.txt
│   │   ├── manage.py
│   │   ├── api/                           ← URL конфиг
│   │   ├── users/                         ← Users app
│   │   ├── planner/                       ← Planner app
│   │   └── integrations/                  ← VK, Testing integrations
│   │
│   └── front/                             ← React Frontend
│       ├── package.json
│       ├── src/
│       │   ├── api/                       ← API clients
│       │   ├── components/                ← React components
│       │   ├── features/                  ← Feature modules
│       │   └── services/                  ← Business logic
│       │
│       └── vite.config.ts
│
└── test-constructor/                      ← Другой проект (отдельно)
    ├── backend/
    └── frontend/
```

---

## 🔑 Ключевые сущности

### Основные сущности

| Сущность | Таблица | Описание |
|----------|---------|---------|
| User | AUTH_USER | Django встроенный пользователь |
| Profile | CRM_PROFILE | Расширенный профиль с доп. информацией |
| Event | CRM_EVENT | Мероприятие/программа |
| Direction | CRM_DIRECTION | Направление внутри мероприятия |
| Project | CRM_PROJECT | Проект внутри направления |
| Application | CRM_APPLICATION | Заявка пользователя на участие |
| Test | CRM_TEST | Тест для проверки знаний |
| TestSession | CRM_TEST_SESSION | Сессия прохождения теста |
| TestResult | CRM_TEST_RESULT | Результат прохождения теста |
| Notification | CRM_NOTIFICATION | Уведомление пользователю |
| Automation | CRM_AUTOMATION_CONFIG | Конфигурация автоматизации |
| Planner | CRM_TEAM_PLANNER_DESK | Доска планировщика команды |

### Справочные сущности

| Сущность | Таблица | Описание |
|----------|---------|---------|
| Specialization | CRM_SPECIALIZATION | Справочник специализаций |
| Status | CRM_STATUS | Справочник статусов |
| Role | CRM_ROLE | Роль пользователя в системе |
| Contact | CRM_CONTACT | Контактная информация |

---

## 🌐 API Endpoints по категориям

### Аутентификация

- `POST /users/register/` - Регистрация
- `POST /users/login/` - Вход
- `POST /users/logout/` - Выход
- `POST /users/refresh/` - Обновление токена
- `POST /users/password-reset/request/` - Запрос сброса пароля
- `POST /users/password-reset/confirm/` - Подтверждение сброса
- `POST /users/confirm-email/` - Подтверждение email

### Профиль

- `GET /users/user-info/` - Информация текущего пользователя
- `GET /users/` - Список пользователей
- `GET/PUT /users/profile/` - Профиль текущего пользователя

### Мероприятия

- `GET/POST /users/events/` - CRUD для событий
- `GET/PUT/DELETE /users/events/{event_id}/` - Конкретное событие
- `GET /users/events/{event_id}/export/details.docx/` - Экспорт деталей
- `GET /users/events/{event_id}/export/applications.xlsx/` - Экспорт заявок

### Направления

- `GET/POST /users/events/{event_id}/directions/` - CRUD для направлений
- `GET/PUT/DELETE /users/events/{event_id}/directions/{direction_id}/` - Конкретное направление
- `GET /users/directions/` - Мои направления

### Проекты

- `GET/POST /users/events/{event_id}/directions/{direction_id}/projects/` - CRUD для проектов
- `GET/PUT/DELETE /users/projects/{project_id}/` - Конкретный проект
- `GET /users/projects/` - Мои проекты

### Заявки

- `GET/POST /users/events/{event_id}/directions/{direction_id}/applications/` - Подать заявку
- `GET /users/applications/` - Мои заявки
- `GET/PUT/DELETE /users/applications/{application_id}/` - Конкретная заявка

### Тестирование

- `GET /users/integration/testing/application/{application_id}/context/` - Контекст тестирования
- `POST /users/integration/testing/session/` - Создать сессию тестирования
- `POST /users/integration/testing/result/` - Загрузить результаты тестирования
- `GET /users/integration/testing/sso-link/` - Получить SSO ссылку
- `POST /users/integration/testing/sso-exchange/` - Обменять ticket на sessionId

### Уведомления

- `GET/POST /users/notifications/` - CRUD для уведомлений
- `GET/PUT/DELETE /users/notifications/{notification_id}/` - Конкретное уведомление
- `POST /users/notifications/mark-all-read/` - Отметить все как прочитанные

### Автоматизация (CRM)

- `GET/PUT /users/automation/{event_id}/` - Конфиг автоматизации события
- `GET /users/automation/{event_id}/logs/` - Логи выполнения
- `POST /users/automation/{event_id}/attachments/` - Загрузить файл
- `GET /users/automation/{event_id}/attachments/` - Список файлов
- `DELETE /users/automation/{event_id}/attachments/{attachment_id}/` - Удалить файл

### Планировщик

- `GET /api/planner/teams/desks/` - Все доски команд
- `GET/PUT /api/planner/teams/{team_id}/desk/` - Доска конкретной команды
- `GET/PUT /api/planner/automation/{event_id}/` - Конфиг автоматизации планировщика
- `GET /api/planner/automation/{event_id}/logs/` - Логи выполнения
- `POST /api/planner/automation/run-deadline-scan/` - Сканировать дедлайны (админ)
- `POST /api/planner/automation/run-pending/` - Обработать ожидающие (админ)

### Справочники

- `GET /users/specializations/` - Список специализаций
- `GET /users/statuses/` - Список статусов

### Интеграции

- `POST /api/integrations/vk/notify-application-testing-started/` - Отправить уведомление в VK

---

## 🔐 Уровни доступа

### ROLE_ADMIN

✓ Полный доступ ко всем ресурсам
✓ Управление пользователями и ролями
✓ Запуск автоматизаций
✓ Сканирование дедлайнов

### ROLE_CURATOR

✓ Создание/редактирование событий, направлений, проектов
✓ Управление заявками на свои события
✓ Настройка автоматизаций для своих событий
✓ Просмотр доски планировщика своих команд

### ROLE_PROJECTANT

✓ Просмотр доступных событий и проектов
✓ Подача заявок
✓ Просмотр собственной информации
✓ Прохождение тестов
✓ Обновление собственного профиля

### Anonymous (Unauthorized)

✓ Просмотр публичных событий
✗ Подача заявок
✗ Доступ к персональной информации
✗ Управление ресурсами

---

## 🚀 Установка и запуск

### Backend

```bash
cd ric-crm-planner/back
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### Frontend

```bash
cd ric-crm-planner/front
npm install
npm run dev
```

### Docker

```bash
docker-compose up
```

---

## 📖 Дополнительные ресурсы

### Встроенная документация

- **Swagger UI**: <http://localhost:8000/swagger/>
- **ReDoc**: <http://localhost:8000/redoc/>
- **OpenAPI JSON**: <http://localhost:8000/swagger.json>

---
