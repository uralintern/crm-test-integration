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
