# RIC CRM Planner - Быстрая Справка для Разработчиков

## ⚡ Быстрый старт

### Установка и запуск

```bash
# Backend
cd ric-crm-planner/back
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

# Frontend
cd ric-crm-planner/front
npm install
npm run dev
```

### Доступ к документации

- Swagger UI: <http://localhost:8000/swagger/>
- ReDoc: <http://localhost:8000/redoc/>
- API Base: <http://localhost:8000/api/>

---

## 🔐 Аутентификация

### JWT Flow

```javascript
// 1. Вход
POST /api/users/login/
Body: { username, password }
Response: { user, access, refresh }
// Cookies: access_token, refresh_token (HTTP-only)

// 2. Использование в запросах
Header: Authorization: Bearer {access_token}

// 3. Обновление токена
POST /api/users/refresh/
Response: { access, refresh }
```

### Пример на JavaScript

```javascript
import client from './api/client';

// Вход
const response = await client.post('/api/users/login/', {
  username: 'user@example.com',
  password: 'password'
});

// Автоматический refresh токена происходит в client.ts

// Использование токена
const data = await client.get('/api/users/events/');
```

---

## 📊 Основные сущности и их CRUD операции

### Events (Мероприятия)

```javascript
// List all
GET /api/users/events/

// Create
POST /api/users/events/
Body: { name, description, stage, start_date, end_date, end_app_date, ... }

// Read
GET /api/users/events/{event_id}/

// Update
PUT /api/users/events/{event_id}/
Body: { name, description, ... }

// Delete
DELETE /api/users/events/{event_id}/

// Export
GET /api/users/events/{event_id}/export/details.docx/
GET /api/users/events/{event_id}/export/applications.xlsx/
```

### Directions (Направления)

```javascript
// List for event
GET /api/users/events/{event_id}/directions/

// Create
POST /api/users/events/{event_id}/directions/
Body: { name, description, leader }

// Read
GET /api/users/events/{event_id}/directions/{direction_id}/

// Update
PUT /api/users/events/{event_id}/directions/{direction_id}/

// Delete
DELETE /api/users/events/{event_id}/directions/{direction_id}/

// My directions
GET /api/users/directions/
```

### Projects (Проекты)

```javascript
// List for direction
GET /api/users/events/{event_id}/directions/{direction_id}/projects/

// Create
POST /api/users/events/{event_id}/directions/{direction_id}/projects/
Body: { name, description, curator, teams }

// Read
GET /api/users/projects/{project_id}/

// Update
PUT /api/users/projects/{project_id}/

// Delete
DELETE /api/users/projects/{project_id}/

// My projects
GET /api/users/projects/
```

### Applications (Заявки)

```javascript
// List my applications
GET /api/users/applications/

// Create application
POST /api/users/events/{event_id}/directions/{direction_id}/applications/
Body: { message, specialization, custom_form_answers }

// Read
GET /api/users/applications/{application_id}/

// Update application (approve/comment)
PUT /api/users/applications/{application_id}/
Body: { is_approved, comment }

// Delete
DELETE /api/users/applications/{application_id}/
```

---

## 🧪 Тестирование

### Получение контекста

```javascript
// Get available tests and current session
GET /api/users/integration/testing/application/{application_id}/context/

Response: {
  applicationId,
  availableTests: [{ id, title, questionCount, passingScore, ... }],
  currentSession: { sessionId, testId, status, ... },
  latestResult: { score, isPassed, ... }
}
```

### Управление сессией

```javascript
// Create/Update session
POST /api/users/integration/testing/session/
Body: {
  application_id,
  test_id,
  session_id,
  status: "in_progress" | "completed"
}

Response: {
  id,
  sessionId,
  testId,
  status,
  startedAt
}
```

### Загрузка результатов

```javascript
// Submit test result
POST /api/users/integration/testing/result/
Body: {
  application_id,
  test_id,
  session_id,
  score,
  is_passed,
  answers_data: {}
}

Response: {
  id,
  testId,
  applicationId,
  score,
  isPassed,
  completedAt
}
```

### SSO Integration

```javascript
// Get SSO link for testing service
GET /api/users/integration/testing/sso-link/?application_id={id}

Response: {
  url: "https://testing-service.com/auth?ticket=...",
  ticket,
  expiresIn
}

// Exchange ticket for sessionId
POST /api/users/integration/testing/sso-exchange/
Body: { ticket }

Response: {
  user: { id, firstName, lastName, specializations },
  sessionId,
  expiresIn
}
```

---

## 🔔 Уведомления

```javascript
// List notifications
GET /api/users/notifications/

// Get one
GET /api/users/notifications/{notification_id}/

// Create (admin/curator only)
POST /api/users/notifications/
Body: { user_id, title, description, message }

// Mark as read
PUT /api/users/notifications/{notification_id}/
Body: { is_read: true }

// Mark all as read
POST /api/users/notifications/mark-all-read/

// Delete
DELETE /api/users/notifications/{notification_id}/

// Clear all
POST /api/users/notifications/clear-all/
```

---

## 🤖 Автоматизация

### CRM Automation

```javascript
// Get automation config
GET /api/users/automation/{event_id}/

Response: {
  id,
  scope: "crm",
  eventId,
  stages: [],
  triggers: [],
  robots: [],
  updatedAt
}

// Update config
PUT /api/users/automation/{event_id}/
Body: {
  eventId,
  stages: [{ id, name, transitions: [...] }],
  triggers: [{ id, event, condition, ... }],
  robots: [{ id, name, trigger, actions: [...] }]
}

// View logs
GET /api/users/automation/{event_id}/logs/?status=success

Response: [{
  id,
  eventId,
  entityType,
  entityId,
  status,
  message,
  executedAt,
  createdAt
}]

// Upload attachment
POST /api/users/automation/{event_id}/attachments/
Content-Type: multipart/form-data
File: document.pdf

Response: {
  id,
  file,
  uploadedAt,
  createdBy
}

// Delete attachment
DELETE /api/users/automation/{event_id}/attachments/{attachment_id}/
```

### Planner Automation

```javascript
// Similar to CRM but prefix /api/planner/

// Get config
GET /api/planner/automation/{event_id}/

// Update config
PUT /api/planner/automation/{event_id}/

// View logs
GET /api/planner/automation/{event_id}/logs/

// Run deadline scan (admin only)
POST /api/planner/automation/run-deadline-scan/

// Run pending automations (admin only)
POST /api/planner/automation/run-pending/
```

---

## 📋 Планировщик

### Team Desks

```javascript
// List all team desks
GET /api/planner/teams/desks/

Response: [{
  teamId,
  teamName,
  curatorId,
  memberIds,
  parentTasks,
  subtasks,
  columns,
  updatedAt
}]

// Get team desk
GET /api/planner/teams/{team_id}/desk/

// Update team desk
PUT /api/planner/teams/{team_id}/desk/
Body: {
  teamName,
  curatorId,
  memberIds,
  parentTasks: [...],
  subtasks: [...],
  columns
}
```

### WebSocket Real-time Updates

```javascript
// Connect
ws://localhost:8000/ws/planner/team/{team_id}/?token={JWT_TOKEN}

// Server sends
{
  type: "desk_update",
  data: { teamId, teamName, parentTasks, subtasks, updatedAt }
}

{
  type: "user_joined",
  data: { userId, userName, timestamp }
}

{
  type: "user_left",
  data: { userId, userName, timestamp }
}

// Client sends
{
  type: "update_desk",
  data: { parentTasks, subtasks, columns }
}

{
  type: "ping"
}
```

---

## 👤 Профили и пользователи

```javascript
// Get current user info
GET /api/users/user-info/

Response: {
  id,
  username,
  email,
  firstName,
  lastName,
  profile: { surname, name, patronymic, telegram, email, ... },
  managedEventIds: [1, 2, 3]
}

// List all users
GET /api/users/

// Get my profile
GET /api/users/profile/

// Update my profile
PUT /api/users/profile/
Body: { surname, name, email, telegram, ... }

// Get specializations
GET /api/users/specializations/

Response: [{ id, name: "Frontend" }]

// Get statuses
GET /api/users/statuses/

Response: [
  { id, name: "Прислал заявку", description, isPositive }
]
```

---

## 🔐 Пароль

```javascript
// Request password reset
POST /api/users/password-reset/request/
Body: { email }

// Confirm password reset
POST /api/users/password-reset/confirm/
Body: { token, new_password }

// Confirm email
POST /api/users/confirm-email/
Body: { token }
```

---

## 📤 Интеграции

### VK Integration

```javascript
// Send testing started notification (service-to-service)
POST /api/integrations/vk/notify-application-testing-started/
Headers: X-Service-Token: {shared_token}
Body: { application_id, peer_id }

Response: { message: "Notification sent" }
```

---

## 🚀 Успешные сценарии

### Сценарий 1: Создание события и подача заявки

```javascript
// 1. Login
const loginRes = await client.post('/api/users/login/', {
  username: 'curator@example.com',
  password: 'password'
});

// 2. Create event
const eventRes = await client.post('/api/users/events/', {
  name: 'Summer Bootcamp',
  stage: 'Hiring',
  start_date: '2024-06-01',
  end_date: '2024-08-31',
  end_app_date: '2024-05-31T23:59:59Z'
});

// 3. Create direction
const directionRes = await client.post(
  `/api/users/events/${eventRes.id}/directions/`,
  { name: 'Backend Track', description: '...' }
);

// 4. Create project
const projectRes = await client.post(
  `/api/users/events/${eventRes.id}/directions/${directionRes.id}/projects/`,
  { name: 'Project Alpha', curator: 1, teams: 3 }
);

// 5. Apply as participant
const appRes = await client.post(
  `/api/users/events/${eventRes.id}/directions/${directionRes.id}/applications/`,
  { message: 'I want to join', specialization: 1 }
);
```

### Сценарий 2: Тестирование приложения

```javascript
// 1. Get testing context
const context = await client.get(
  `/api/users/integration/testing/application/${applicationId}/context/`
);

// 2. Get SSO link for testing service
const ssoRes = await client.get(
  `/api/users/integration/testing/sso-link/?application_id=${applicationId}`
);

// 3. User goes to testing service via ssoRes.url
// Testing service exchanges ticket
const sessionRes = await fetch('http://localhost:8000/api/users/integration/testing/sso-exchange/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ ticket: ssoRes.ticket })
});

// 4. Testing service posts results
const resultRes = await fetch(
  'http://localhost:8000/api/users/integration/testing/result/',
  {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Service-Token': process.env.SERVICE_TOKEN
    },
    body: JSON.stringify({
      application_id: applicationId,
      test_id: testId,
      session_id: sessionId,
      score: 85,
      is_passed: true,
      answers_data: {}
    })
  }
);
```

### Сценарий 3: Планировщик с real-time

```javascript
// 1. Connect to WebSocket
const ws = new WebSocket(
  `ws://localhost:8000/ws/planner/team/${teamId}/?token=${jwtToken}`
);

// 2. Listen for updates
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  if (message.type === 'desk_update') {
    // Update UI with new desk state
    updateDeskUI(message.data);
  } else if (message.type === 'user_joined') {
    // Show user joined notification
    showNotification(`${message.data.userName} joined`);
  }
};

// 3. Send updates
function updateDesk(parentTasks, subtasks) {
  ws.send(JSON.stringify({
    type: 'update_desk',
    data: { parentTasks, subtasks, columns }
  }));
}

// 4. Keep connection alive
setInterval(() => {
  ws.send(JSON.stringify({ type: 'ping' }));
}, 30000);
```

---

## 🔧 Распространенные операции

### Трансформация данных (snake_case → camelCase)

Frontend автоматически трансформирует:

```javascript
// Backend response
{
  user_id: 1,
  first_name: "Ivan",
  last_name: "Petrov",
  vk_user_id: 123456,
  start_date: "2024-01-01",
  end_app_date: "2024-01-31T23:59:59Z"
}

// Frontend receives
{
  userId: 1,
  firstName: "Ivan",
  lastName: "Petrov",
  vkUserId: 123456,
  startDate: "2024-01-01",
  applyDeadline: "2024-01-31T23:59:59Z"
}
```

### Работа с ошибками

```javascript
try {
  const response = await client.post('/api/users/events/', eventData);
} catch (error) {
  // Error response format
  {
    field_name: ["Error message 1", "Error message 2"],
    non_field_errors: ["General error"]
  }
}
```

### Пагинация (если включена)

```javascript
// Some endpoints support pagination
GET /api/users/events/?page=1&limit=10

Response: {
  count: 100,
  next: "?page=2",
  previous: null,
  results: [...]
}
```

---

## 📋 Таблица разрешений

| Endpoint | Anon | Auth | Curator | Admin |
|----------|------|------|---------|-------|
| POST /events/ | ✗ | ✗ | ✓ | ✓ |
| GET /events/ | ✓ | ✓ | ✓ | ✓ |
| PUT /events/{id}/ | ✗ | ✗ | ✓* | ✓ |
| DELETE /events/{id}/ | ✗ | ✗ | ✓* | ✓ |
| POST /applications/ | ✗ | ✓ | ✓ | ✓ |
| GET /applications/ | ✗ | ✓* | ✓ | ✓ |
| PUT /automation/{id}/ | ✗ | ✗ | ✓* | ✓ |
| POST /planner/automation/run-* | ✗ | ✗ | ✗ | ✓ |

*для своих ресурсов

---

## 🐛 Отладка

### Enable detailed logging

```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
}
```

### Inspect requests

```javascript
// Add logging middleware
const originalFetch = fetch;
window.fetch = function(...args) {
  console.log('Request:', args[0], args[1]);
  return originalFetch(...args)
    .then(res => {
      console.log('Response:', res.status, res.statusText);
      return res;
    });
};
```

### Database queries

```bash
# Enable query logging
python manage.py shell
>>> from django.db import connection
>>> connection.queries  # Shows all executed SQL queries
```

---

## 📚 Полезные ссылки

- **Документация**: [DATABASE_AND_API_DOCUMENTATION.md](./DATABASE_AND_API_DOCUMENTATION.md)
- **Swagger UI**: <http://localhost:8000/swagger/>
- **ReDoc**: <http://localhost:8000/redoc/>
- **Django Docs**: <https://docs.djangoproject.com/>
- **DRF Docs**: <https://www.django-rest-framework.org/>
- **React Docs**: <https://react.dev/>
- **TypeScript Docs**: <https://www.typescriptlang.org/docs/>

---

**Версия**: 1.0  
**Обновлено**: 2024-07-01
