# RIC CRM Planner - Детальная Схема БД и Связи

## 📊 ER-диаграмма системы

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         USERS & AUTHENTICATION LAYER                        │
├─────────────────────────────────────────────────────────────────────────────┤
│
│  ┌──────────────────────────────────────────────────────────────────────┐
│  │ AUTH_USER (Django Built-in)                                          │
│  ├──────────────────────────────────────────────────────────────────────┤
│  │ id (PK)                                                              │
│  │ username (UNIQUE)                                                    │
│  │ password (hashed)                                                    │
│  │ email                                                                │
│  │ first_name                                                           │
│  │ last_name                                                            │
│  │ is_superuser, is_staff, is_active                                   │
│  │ date_joined                                                          │
│  └──────────────────────────────────────────────────────────────────────┘
│                                    │
│                    ┌───────────────┼───────────────┐
│                    │               │               │
│                    ▼               ▼               ▼
│
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  │ CRM_PROFILE      │  │ CRM_ROLE         │  │ CRM_CONTACT      │
│  ├──────────────────┤  ├──────────────────┤  ├──────────────────┤
│  │ user_id (PK,FK) ─┼─→│ user_id (FK)    │  │ id (PK)          │
│  │ surname          │  │ role_type       │  │ type             │
│  │ name             │  │ content_type_id │  │ data             │
│  │ patronymic       │  │ object_id       │  │ is_verified      │
│  │ telegram         │  └──────────────────┘  │ profile_id (FK) ──→
│  │ email            │                        └──────────────────┘
│  │ course           │
│  │ university       │
│  │ vk*              │
│  │ vk_user_id       │
│  │ vk_confirmed_at  │
│  │ job              │
│  │ workplace        │
│  │ specialty        │
│  │ about            │
│  │ password_reset*  │
│  └──────────────────┘
│
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                     REFERENCE DATA & CLASSIFICATIONS LAYER                  │
├─────────────────────────────────────────────────────────────────────────────┤
│
│  ┌──────────────────────────┐      ┌──────────────────────────┐
│  │ CRM_SPECIALIZATION       │      │ CRM_STATUS               │
│  ├──────────────────────────┤      ├──────────────────────────┤
│  │ id (PK)                  │      │ id (PK)                  │
│  │ name                     │◄─┐   │ name                     │
│  │ description              │  │   │ description              │
│  └──────────────────────────┘  │   │ is_positive              │
│                                │   └──────────────────────────┘
│                                │
│                    ┌───────────┴────────────┐
│                    │                        │
│                    ▼                        ▼
│
│  ┌──────────────────────────────────────────────────────────────────┐
│  │ CRM_EVENT_SPECIALIZATIONS (M2M)                                 │
│  ├──────────────────────────────────────────────────────────────────┤
│  │ id (PK)                                                          │
│  │ event_id (FK)                                                    │
│  │ specialization_id (FK)                                           │
│  │ UNIQUE(event_id, specialization_id)                             │
│  └──────────────────────────────────────────────────────────────────┘
│
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                    EVENTS & ORGANIZATION HIERARCHY LAYER                    │
├─────────────────────────────────────────────────────────────────────────────┤
│
│  ┌──────────────────────────────────────────────────────────────────┐
│  │ CRM_EVENT                                                        │
│  ├──────────────────────────────────────────────────────────────────┤
│  │ id (PK)                                                          │
│  │ name                                                             │
│  │ description                                                      │
│  │ stage                                                            │
│  │ specialization_id (FK, nullable)                                │
│  │ leader_id (FK, nullable) ─→ AUTH_USER.lead_events             │
│  │ organizers (M2M)            ─→ AUTH_USER.organized_events      │
│  │ start_date                                                       │
│  │ end_date                                                         │
│  │ end_app_date                                                     │
│  │ is_archived                                                      │
│  │ archived_at                                                      │
│  │ org_chat_url                                                     │
│  │ org_chat_peer_id                                                 │
│  │ application_form_fields (JSON)                                   │
│  └──────────────────────────────────────────────────────────────────┘
│                        │
│        ┌───────────────┼───────────────┐
│        │               │               │
│        ▼               ▼               ▼
│
│  ┌────────────────────────┐  ┌──────────────────┐  ┌────────────────────┐
│  │ CRM_DIRECTION          │  │ CRM_TEST         │  │ CRM_AUTOMATION_    │
│  ├────────────────────────┤  ├──────────────────┤  │ CONFIG              │
│  │ id (PK)                │  │ id (PK)          │  ├────────────────────┤
│  │ event_id (FK)          │  │ name             │  │ scope              │
│  │ name                   │  │ description      │  │ event_id (FK)      │
│  │ description            │  │ event_id (FK)*   │  │ stages (JSON)      │
│  │ leader_id (FK)*        │  │ specialization_* │  │ triggers (JSON)    │
│  └────────────────────────┘  │ entry            │  │ robots (JSON)      │
│        │                      │ is_active        │  │ updated_at         │
│        │                      │ question_count   │  └────────────────────┘
│        │                      │ passing_score    │
│        │                      │ time_limit_*     │
│        │                      │ attempts_allowed │
│        │                      └──────────────────┘
│        │                              │
│        │                    ┌─────────┴──────────┐
│        │                    │                    │
│        │                    ▼                    ▼
│        │
│        │                ┌──────────────────┐
│        │                │ CRM_QUESTION     │
│        │                ├──────────────────┤
│        │                │ id (PK)          │
│        │                │ test_id (FK)     │
│        │                │ text             │
│        │                │ order            │
│        │                │ type             │
│        │                └──────────────────┘
│        │                        │
│        │            ┌───────────┼────────────┐
│        │            │           │            │
│        │            ▼           ▼            ▼
│        │
│        │      ┌──────────────┐  ┌──────────────────────┐
│        │      │ CRM_ANSWER   │  │ CRM_TRUE_ANSWER      │
│        │      ├──────────────┤  ├──────────────────────┤
│        │      │ id (PK)      │  │ id (PK)              │
│        │      │ question_id  │  │ question_id (FK)     │
│        │      │ text         │  │ answer_id (FK)       │
│        │      │ order        │  └──────────────────────┘
│        │      └──────────────┘
│        │
│        ▼
│  ┌────────────────────────────────────┐
│  │ CRM_PROJECT                         │
│  ├────────────────────────────────────┤
│  │ id (PK)                             │
│  │ direction_id (FK)                   │
│  │ name                                │
│  │ description                         │
│  │ curator_id (FK, nullable)           │
│  │ teams                               │
│  │ created_at                          │
│  │ updated_at                          │
│  └────────────────────────────────────┘
│        │
│        ▼
│  ┌──────────────────────────────────────────────────────┐
│  │ CRM_APPLICATION                                      │
│  ├──────────────────────────────────────────────────────┤
│  │ id (PK)                                              │
│  │ user_id (FK) ──────────→ AUTH_USER                 │
│  │ event_id (FK, nullable)                             │
│  │ direction_id (FK, nullable)                         │
│  │ project_id (FK, nullable)                           │
│  │ specialization_id (FK, nullable)                    │
│  │ status_id (FK, nullable) ──→ CRM_STATUS            │
│  │ message                                              │
│  │ is_link                                              │
│  │ is_approved                                          │
│  │ comment                                              │
│  │ date_sub (created_at)                               │
│  │ date_end (deadline)                                 │
│  │ test_session_id (FK, nullable)                      │
│  │ custom_form_answers (JSON)                          │
│  └──────────────────────────────────────────────────────┘
│        │
│        └────────┬────────────────────┬────────────────────┐
│                 │                    │                    │
│                 ▼                    ▼                    ▼
│
│      ┌────────────────────┐  ┌────────────────────┐
│      │ CRM_TEST_SESSION   │  │ CRM_TEST_RESULT    │
│      ├────────────────────┤  ├────────────────────┤
│      │ id (PK)            │  │ id (PK)            │
│      │ session_id (UK)    │  │ test_id (FK)       │
│      │ application_id (FK)│  │ application_id (FK)│
│      │ test_id (FK)       │  │ session_id (FK)*   │
│      │ user_id (FK)       │  │ user_id (FK)       │
│      │ started_at         │  │ score              │
│      │ completed_at       │  │ is_passed          │
│      │ status             │  │ completed_at       │
│      │ created_at         │  │ answers_data (JSON)│
│      └────────────────────┘  └────────────────────┘
│
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                      NOTIFICATIONS & MESSAGING LAYER                        │
├─────────────────────────────────────────────────────────────────────────────┤
│
│  ┌──────────────────────────────────────────────────────┐
│  │ CRM_NOTIFICATION                                     │
│  ├──────────────────────────────────────────────────────┤
│  │ id (PK)                                              │
│  │ user_id (FK) ──→ AUTH_USER.notifications            │
│  │ title                                                │
│  │ description                                          │
│  │ message                                              │
│  │ is_read                                              │
│  │ read_at                                              │
│  │ created_at                                           │
│  └──────────────────────────────────────────────────────┘
│
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│              AUTOMATION & EXECUTION LOGGING LAYER (CRM)                     │
├─────────────────────────────────────────────────────────────────────────────┤
│
│  ┌──────────────────────────────────────────────────────────┐
│  │ CRM_AUTOMATION_CONFIG                                    │
│  ├──────────────────────────────────────────────────────────┤
│  │ id (PK)                                                  │
│  │ scope (default="crm")                                    │
│  │ event_id (FK indirect)                                   │
│  │ stages (JSON) - stage definitions                        │
│  │ triggers (JSON) - trigger definitions                    │
│  │ robots (JSON) - automation rules                         │
│  │ updated_at                                               │
│  │ UNIQUE(scope, event_id)                                 │
│  └──────────────────────────────────────────────────────────┘
│        │
│        ▼
│  ┌────────────────────────────────────────────────────────────┐
│  │ CRM_AUTOMATION_EXECUTION_LOG                               │
│  ├────────────────────────────────────────────────────────────┤
│  │ id (PK)                                                    │
│  │ config_id (FK)                                             │
│  │ event_id                                                   │
│  │ team_id (nullable)                                         │
│  │ entity_type                                                │
│  │ entity_id                                                  │
│  │ event_code                                                 │
│  │ rule_kind                                                  │
│  │ rule_id                                                    │
│  │ run_key (UNIQUE) - prevents duplicate runs                │
│  │ status (pending|success|skipped|failed)                   │
│  │ message                                                    │
│  │ context (JSON)                                             │
│  │ scheduled_for                                              │
│  │ executed_at                                                │
│  │ created_at                                                 │
│  │ INDEX: (event_id, status)                                 │
│  │ INDEX: (scheduled_for, status)                            │
│  └────────────────────────────────────────────────────────────┘
│
│  ┌────────────────────────────────────────────────────────────┐
│  │ CRM_AUTOMATION_ATTACHMENT                                  │
│  ├────────────────────────────────────────────────────────────┤
│  │ id (PK)                                                    │
│  │ config_id (FK)                                             │
│  │ file (FileField)                                           │
│  │ uploaded_at                                                │
│  │ created_by_id (FK, nullable) ──→ AUTH_USER                │
│  └────────────────────────────────────────────────────────────┘
│
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│              PLANNER & EXECUTION LOGGING LAYER (PLANNER)                    │
├─────────────────────────────────────────────────────────────────────────────┤
│
│  ┌──────────────────────────────────────────────────────────┐
│  │ CRM_PLANNER_WORKSPACE_STATE                              │
│  ├──────────────────────────────────────────────────────────┤
│  │ id (PK)                                                  │
│  │ enrollment_closed (Boolean)                              │
│  │ participants (JSON) - list of user objects               │
│  │ teams (JSON) - list of team objects                      │
│  │ parent_tasks (JSON) - list of task objects               │
│  │ subtasks (JSON) - list of subtask objects                │
│  │ columns (JSON) - kanban board columns                    │
│  │ updated_at                                               │
│  └──────────────────────────────────────────────────────────┘
│
│  ┌──────────────────────────────────────────────────────────┐
│  │ CRM_TEAM_PLANNER_DESK                                    │
│  ├──────────────────────────────────────────────────────────┤
│  │ id (PK)                                                  │
│  │ team_id (BigInt, UNIQUE)                                │
│  │ team_name                                                │
│  │ curator_id (BigInt, nullable)                            │
│  │ member_ids (JSON) - list of user IDs                     │
│  │ parent_tasks (JSON)                                      │
│  │ subtasks (JSON)                                          │
│  │ columns (JSON)                                           │
│  │ updated_at                                               │
│  └──────────────────────────────────────────────────────────┘
│        │
│        ▼
│  ┌──────────────────────────────────────────────────────────┐
│  │ CRM_PLANNER_AUTOMATION_CONFIG                            │
│  ├──────────────────────────────────────────────────────────┤
│  │ id (PK)                                                  │
│  │ scope (default="planner")                                │
│  │ event_id                                                 │
│  │ stages (JSON)                                            │
│  │ triggers (JSON)                                          │
│  │ robots (JSON)                                            │
│  │ updated_at                                               │
│  │ UNIQUE(scope, event_id)                                 │
│  └──────────────────────────────────────────────────────────┘
│        │
│        ▼
│  ┌────────────────────────────────────────────────────────────┐
│  │ CRM_PLANNER_AUTOMATION_EXECUTION_LOG                       │
│  ├────────────────────────────────────────────────────────────┤
│  │ (Same structure as CRM_AUTOMATION_EXECUTION_LOG)           │
│  │ id (PK)                                                    │
│  │ config_id (FK)                                             │
│  │ event_id                                                   │
│  │ team_id (nullable)                                         │
│  │ entity_type                                                │
│  │ entity_id                                                  │
│  │ event_code                                                 │
│  │ rule_kind                                                  │
│  │ rule_id                                                    │
│  │ run_key (UNIQUE)                                           │
│  │ status                                                     │
│  │ message                                                    │
│  │ context (JSON)                                             │
│  │ scheduled_for                                              │
│  │ executed_at                                                │
│  │ created_at                                                 │
│  │ INDEX: (event_id, status)                                 │
│  │ INDEX: (scheduled_for, status)                            │
│  └────────────────────────────────────────────────────────────┘
│
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔗 Основные связи между сущностями

### 1. User ↔ Everything

```
AUTH_USER (1) ─────→ (N) CRM_PROFILE (OneToOne, primary_key)
      │
      ├─→ (N) CRM_CONTACT (FK)
      │
      ├─→ (N) CRM_ROLE (FK)
      │
      ├─→ (N) CRM_EVENT (as leader)
      │
      ├─→ (N) CRM_EVENT (M2M as organizers)
      │
      ├─→ (N) CRM_DIRECTION (as leader)
      │
      ├─→ (N) CRM_PROJECT (as curator)
      │
      ├─→ (N) CRM_APPLICATION (as user)
      │
      ├─→ (N) CRM_TEST_SESSION (as user)
      │
      ├─→ (N) CRM_TEST_RESULT (as user)
      │
      ├─→ (N) CRM_NOTIFICATION (as user)
      │
      └─→ (N) CRM_AUTOMATION_ATTACHMENT (as created_by)
```

### 2. Event ↔ Organization

```
CRM_EVENT (1) ──→ (N) CRM_DIRECTION
      │
      ├─→ (N) CRM_APPLICATION
      │
      ├─→ (N) CRM_TEST
      │
      ├─→ (1) CRM_AUTOMATION_CONFIG
      │
      └─→ (1) CRM_PLANNER_AUTOMATION_CONFIG


CRM_EVENT (M) ←→ (N) CRM_SPECIALIZATION
      via CRM_EVENT_SPECIALIZATIONS (M2M junction table)


CRM_DIRECTION (1) ──→ (N) CRM_PROJECT
      │
      └─→ (N) CRM_APPLICATION


CRM_PROJECT (1) ──→ (N) CRM_APPLICATION
```

### 3. Application ↔ Testing

```
CRM_APPLICATION (1) ──→ (N) CRM_TEST_SESSION
      │                        │
      │                        ▼
      └──→ (N) CRM_TEST_RESULT ←──┘
                      │
                      ├─→ (1) CRM_TEST
                      │
                      └─→ (1) AUTH_USER


CRM_TEST (1) ──→ (N) CRM_QUESTION
      │              │
      │              └──→ (N) CRM_ANSWER
      │
      └──→ (N) CRM_TEST_RESULT
```

### 4. Automation Execution Chain

```
CRM_AUTOMATION_CONFIG (1) ─→ (N) CRM_AUTOMATION_EXECUTION_LOG

Event triggers automation config
      ↓
Automation scans for triggers
      ↓
Matching trigger found
      ↓
Execute automation rules
      ↓
Create execution log entry
      ↓
Log status: pending → success/failed/skipped
      ↓
Optional: Schedule follow-up actions
```

---

## 📈 Data Flow Examples

### Пример 1: Создание и обработка заявки

```
1. USER регистрируется
   CREATE AUTH_USER
   CREATE CRM_PROFILE (OneToOne с AUTH_USER)
   CREATE CRM_CONTACT (FK к CRM_PROFILE)

2. Администратор создает СОБЫТИЕ
   CREATE CRM_EVENT
   CREATE CRM_AUTOMATION_CONFIG (для события)

3. USER видит событие
   SELECT FROM CRM_EVENT WHERE is_archived = FALSE

4. USER подает ЗАЯВКУ
   CREATE CRM_APPLICATION
   event_id = event.id
   user_id = auth_user.id
   status_id = resolve_status("Прислал заявку")
   
   ↓ Trigger automation
   
   CREATE CRM_AUTOMATION_EXECUTION_LOG
   status = "pending"
   
   ↓ Automation processes
   
   UPDATE CRM_AUTOMATION_EXECUTION_LOG
   status = "success"
   executed_at = NOW()

5. Куратор одобряет заявку
   UPDATE CRM_APPLICATION
   is_approved = TRUE
   
   ↓ Second automation
   
   UPDATE CRM_APPLICATION
   status_id = resolve_status("Прохождение тестирования")
   
   CREATE CRM_TEST_SESSION
   application_id = app.id
   test_id = get_available_tests(app)[0].id

6. USER проходит тест
   TestService calls: POST /api/users/integration/testing/result/
   
   CREATE CRM_TEST_RESULT
   application_id = app.id
   test_id = test.id
   user_id = user.id
   score = 85
   is_passed = (score >= test.passing_score)
   
   UPDATE CRM_APPLICATION
   status_id = resolve_status("Прошел тестирование")
   
   CREATE CRM_AUTOMATION_EXECUTION_LOG
   event_code = "test_completed"
```

### Пример 2: Управление доской планировщика

```
1. Куратор создает КОМАНДУ
   CREATE CRM_TEAM_PLANNER_DESK
   team_id = external_team_id
   member_ids = [user1_id, user2_id, user3_id]
   columns = ["Запланировано", "В работе", "На проверке", "Готово"]

2. Члены команды получают доступ
   GET /api/planner/teams/desks/
   Фильтруются по: curatorId == user_id OR user_id IN memberIds

3. Член команды обновляет задачу
   WebSocket: ws://localhost/ws/planner/team/{team_id}/
   
   {
     type: "update_desk",
     data: {
       parentTasks: [...],
       subtasks: [{ ..., status: "В работе" }]
     }
   }
   
   ↓ Server-side
   
   UPDATE CRM_TEAM_PLANNER_DESK
   parent_tasks = [...]
   subtasks = [...]
   updated_at = NOW()
   
   ↓ Broadcast to all connected users in team
   
   {
     type: "desk_update",
     data: { teamId, parentTasks, subtasks, updatedAt }
   }

4. Автоматизация проверяет дедлайны
   POST /api/planner/automation/run-deadline-scan/
   
   FOR each TEAM_PLANNER_DESK WHERE updated_at < 24_hours_ago:
     FOR each task WITH dueDate < NOW():
       UPDATE task status to "OVERDUE"
       CREATE CRM_PLANNER_AUTOMATION_EXECUTION_LOG
```

---

## 🔍 Key Query Patterns

### Получить все заявки пользователя со статусом

```sql
SELECT 
    ca.id,
    ca.message,
    cs.name as status,
    ce.name as event_name,
    cd.name as direction_name
FROM CRM_APPLICATION ca
LEFT JOIN CRM_STATUS cs ON ca.status_id = cs.id
LEFT JOIN CRM_EVENT ce ON ca.event_id = ce.id
LEFT JOIN CRM_DIRECTION cd ON ca.direction_id = cd.id
WHERE ca.user_id = ? AND ca.deleted_at IS NULL
ORDER BY ca.date_sub DESC;
```

### Получить доступные тесты для приложения

```sql
SELECT DISTINCT ct.* FROM CRM_TEST ct
WHERE ct.is_active = TRUE
AND (
    ct.event_id IS NULL OR ct.event_id = ?  -- application.event_id
)
AND (
    ct.specialization_id IS NULL OR ct.specialization_id = ?  -- application.specialization_id
)
ORDER BY ct.entry ASC, ct.name ASC;
```

### Получить логи выполнения автоматизации с фильтром

```sql
SELECT * FROM CRM_AUTOMATION_EXECUTION_LOG
WHERE event_id = ?
AND (status = ? OR ? IS NULL)  -- status filter optional
AND created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
ORDER BY created_at DESC
LIMIT 100;
```

### Получить команды, видимые пользователю (куратор/админ)

```sql
SELECT 
    ctpd.*,
    CASE 
        WHEN ctpd.curator_id = ? THEN 'curator'
        WHEN ? = ANY(member_ids) THEN 'member'
        WHEN ce.leader_id = ? OR ? = ANY(ce.organizers) THEN 'event_organizer'
        ELSE 'none'
    END as access_level
FROM CRM_TEAM_PLANNER_DESK ctpd
LEFT JOIN CRM_EVENT ce ON ctpd.event_id = ce.id
WHERE 
    ctpd.curator_id = ?  -- Is curator
    OR ? = ANY(member_ids)  -- Is member
    OR EXISTS (  -- Is event organizer
        SELECT 1 FROM CRM_EVENT
        WHERE (leader_id = ? OR ? = ANY(organizers))
        AND id = (ctpd.parent_tasks->>'eventId')::INT
    );
```

---

## 📊 Индексирование и производительность

### Важные индексы

```sql
-- Users & Authentication
CREATE INDEX idx_crm_profile_vk_user_id ON CRM_PROFILE(vk_user_id);
CREATE INDEX idx_crm_role_user_id ON CRM_ROLE(user_id);

-- Events & Organization
CREATE INDEX idx_crm_event_leader_id ON CRM_EVENT(leader_id);
CREATE INDEX idx_crm_event_is_archived ON CRM_EVENT(is_archived);
CREATE INDEX idx_crm_direction_event_id ON CRM_DIRECTION(event_id);
CREATE INDEX idx_crm_project_direction_id ON CRM_PROJECT(direction_id);

-- Applications & Testing
CREATE INDEX idx_crm_application_user_id ON CRM_APPLICATION(user_id);
CREATE INDEX idx_crm_application_event_id ON CRM_APPLICATION(event_id);
CREATE INDEX idx_crm_application_direction_id ON CRM_APPLICATION(direction_id);
CREATE INDEX idx_crm_application_status_id ON CRM_APPLICATION(status_id);
CREATE INDEX idx_crm_test_session_application_id ON CRM_TEST_SESSION(application_id);
CREATE INDEX idx_crm_test_result_application_id ON CRM_TEST_RESULT(application_id);

-- Automation & Logging
CREATE INDEX idx_crm_automation_execution_event_status ON CRM_AUTOMATION_EXECUTION_LOG(event_id, status);
CREATE INDEX idx_crm_automation_execution_scheduled ON CRM_AUTOMATION_EXECUTION_LOG(scheduled_for, status);
CREATE INDEX idx_crm_automation_execution_run_key ON CRM_AUTOMATION_EXECUTION_LOG(run_key);

-- Planner
CREATE INDEX idx_crm_team_desk_team_id ON CRM_TEAM_PLANNER_DESK(team_id);
```

### N+1 Query Prevention

**Django ORM с `select_related` и `prefetch_related`:**

```python
# Applications with related data
applications = Application.objects.select_related(
    'user',
    'event',
    'direction',
    'project',
    'specialization',
    'status'
).prefetch_related(
    'test_sessions__test',
    'test_results'
).filter(user=user)

# Events with organizers
events = Event.objects.select_related(
    'specialization',
    'leader'
).prefetch_related('organizers').all()

# Automation logs with config
logs = PlannerAutomationExecutionLog.objects.select_related(
    'config'
).filter(event_id=event_id).order_by('-created_at')
```

---

## 🗑️ Удаление и каскадные операции

### Каскадные удаления (ON DELETE CASCADE)

```
DELETE CRM_EVENT
  ↓ CASCADE
    DELETE CRM_DIRECTION
      ↓ CASCADE
        DELETE CRM_PROJECT
          ↓ CASCADE
            DELETE CRM_APPLICATION
              ↓ CASCADE
                DELETE CRM_TEST_SESSION
                DELETE CRM_TEST_RESULT
    
    DELETE CRM_AUTOMATION_CONFIG
      ↓ CASCADE
        DELETE CRM_AUTOMATION_EXECUTION_LOG
    
    DELETE CRM_PLANNER_AUTOMATION_CONFIG
      ↓ CASCADE
        DELETE CRM_PLANNER_AUTOMATION_EXECUTION_LOG
```

### Мягкое удаление (Soft Delete)

Некоторые сущности могут требовать мягкого удаления:

```python
class SoftDeleteModel(models.Model):
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        abstract = True
    
    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        self.deleted_at = None
        self.save()

# Queries должны исключать удаленные
.filter(deleted_at__isnull=True)
```

---

## 📝 Миграция данных и версионирование

### Структура миграций

```
back/
├── users/
│   └── migrations/
│       ├── 0001_initial.py
│       ├── 0002_add_vk_fields.py
│       ├── 0003_create_crm_role.py
│       └── ...
│
└── planner/
    └── migrations/
        ├── 0001_initial.py
        ├── 0002_add_automation.py
        └── ...
```

### Запуск миграций

```bash
# Show pending migrations
python manage.py showmigrations

# Run all migrations
python manage.py migrate

# Run specific app migrations
python manage.py migrate users
python manage.py migrate planner

# Rollback last migration
python manage.py migrate users 0002

# Create new migration
python manage.py makemigrations users --name add_new_field
```

---

**Версия**: 1.0  
**Последнее обновление**: 2024-07-01
