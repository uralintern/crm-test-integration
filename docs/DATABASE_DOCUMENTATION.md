# RIC CRM Planner - Документация

## 1. СХЕМА БАЗЫ ДАННЫХ

### 1.1 Таблица AUTH_USER (встроенная Django)

Встроенная модель Django User с дополнительными полями.

```
AUTH_USER
├── id (PK)
├── username (UNIQUE)
├── password
├── email
├── first_name
├── last_name
├── is_superuser
├── is_staff
├── is_active
└── date_joined
```

---

### 1.2 ПРОФИЛИ И КОНТАКТЫ

#### CRM_PROFILE

Расширенный профиль пользователя с дополнительной информацией.

```
CRM_PROFILE
├── user_id (PK, FK → AUTH_USER)
├── surname (VARCHAR 150)
├── name (VARCHAR 150)
├── patronymic (VARCHAR 150, blank)
├── telegram (VARCHAR 150, blank)
├── email
├── course (PositiveInt, blank)
├── university (VARCHAR 255, blank)
├── vk (VARCHAR 255, blank)
├── vk_user_id (BigInt, blank, indexed)
├── vk_confirmed_at (DateTime, blank)
├── job (VARCHAR 255, blank)
├── workplace (VARCHAR 255, blank)
├── specialty (VARCHAR 255, blank)
├── about (Text, blank)
├── password_reset_token (VARCHAR 255, blank)
└── password_reset_token_created (DateTime, blank)
```

**Связь**: OneToOne с AUTH_USER (primary_key=True)

#### CRM_CONTACT

Контактная информация пользователя (email, phone, Telegram, VK).

```
CRM_CONTACT
├── id (PK, BigInt)
├── type (VARCHAR 50) - choices: email, phone, tg, vk
├── data (VARCHAR 255)
├── is_verified (Boolean, default=False)
├── verified_token (VARCHAR 255, blank)
├── token_created_at (DateTime, blank)
└── profile_id (FK → CRM_PROFILE)
```

**Связь**: ForeignKey → CRM_PROFILE (related_name="contacts")

---

### 1.3 РОЛИ И РАЗРЕШЕНИЯ

#### CRM_ROLE

Система ролей с поддержкой generic relations.

```
CRM_ROLE
├── id (PK, BigInt)
├── role_type (VARCHAR 50) - choices: admin, curator, projectant
├── user_id (FK → AUTH_USER, related_name="crm_roles")
├── content_type_id (FK → ContentType)
├── object_id (PositiveInt)
└── content_object (GenericForeignKey)
```

**Роли:**

- `admin` - Администратор системы
- `curator` - Куратор проекта/направления
- `projectant` - Участник проекта

**Связь**: ForeignKey → AUTH_USER (related_name="crm_roles")

#### CRM_STATUS

Справочник статусов для приложений.

```
CRM_STATUS
├── id (PK, BigInt)
├── name (VARCHAR 150, unique)
├── description (Text, blank)
└── is_positive (Boolean, default=True)
```

**Стандартные статусы:**

- "Прислал заявку"
- "Прохождение тестирования"
- "Не перешёл к тестированию"
- "Не прошел тестирование"
- "Отправлена ссылка на орг. чат"
- "Не добавился в орг чат"
- "Добавился в орг. чат"
- "Набор завершён"
- "Приступил к ПШ"
- "Отказался от ПШ"
- "Удален с ПШ"

---

### 1.4 МЕРОПРИЯТИЯ И НАПРАВЛЕНИЯ

#### CRM_SPECIALIZATION

Справочник специализаций.

```
CRM_SPECIALIZATION
├── id (PK, BigInt)
├── name (VARCHAR 255)
└── description (Text, blank)
```

#### CRM_EVENT

Мероприятие/событие в системе CRM.

```
CRM_EVENT
├── id (PK, BigInt)
├── name (VARCHAR 255)
├── description (Text, blank)
├── specialization_id (FK → CRM_SPECIALIZATION, blank)
├── leader_id (FK → AUTH_USER, related_name="lead_events", blank)
├── organizers (M2M → AUTH_USER, related_name="organized_events")
├── stage (VARCHAR 100)
├── start_date (Date)
├── end_date (Date)
├── end_app_date (DateTime)
├── is_archived (Boolean, default=False)
├── archived_at (DateTime, blank)
├── org_chat_url (URL, blank)
├── org_chat_peer_id (BigInt, default=0)
└── application_form_fields (JSON, default=[])
```

**Связи:**

- ForeignKey: specialization (OneToMany)
- ForeignKey: leader (OneToMany)
- ManyToMany: organizers

#### CRM_EVENT_SPECIALIZATIONS

Связь события и специализаций (M2M промежуточная таблица).

```
CRM_EVENT_SPECIALIZATIONS
├── id (PK, BigInt)
├── event_id (FK → CRM_EVENT)
└── specialization_id (FK → CRM_SPECIALIZATION)
```

**Constraint**: UNIQUE(event_id, specialization_id)

#### CRM_DIRECTION

Направление внутри мероприятия.

```
CRM_DIRECTION
├── id (PK, BigInt)
├── event_id (FK → CRM_EVENT, related_name="directions")
├── name (VARCHAR 255)
├── description (Text, blank)
└── leader_id (FK → AUTH_USER, related_name="lead_directions", blank)
```

**Связи:**

- ForeignKey: event (OneToMany)
- ForeignKey: leader (OneToMany, nullable)

---

### 1.5 ПРОЕКТЫ И ПРИЛОЖЕНИЯ

#### CRM_PROJECT

Проект внутри направления.

```
CRM_PROJECT
├── id (PK)
├── direction_id (FK → CRM_DIRECTION, related_name="projects")
├── name (VARCHAR 255)
├── description (Text, blank)
├── curator_id (FK → AUTH_USER, related_name="curated_projects", blank)
├── teams (PositiveInt, blank)
├── created_at (DateTime, auto_now_add)
└── updated_at (DateTime, auto_now)
```

**Связи:**

- ForeignKey: direction (OneToMany)
- ForeignKey: curator (OneToMany, nullable)

#### CRM_APPLICATION

Заявка пользователя на участие.

```
CRM_APPLICATION
├── id (PK, BigInt)
├── user_id (FK → AUTH_USER, related_name="applications")
├── event_id (FK → CRM_EVENT, related_name="applications", blank)
├── direction_id (FK → CRM_DIRECTION, related_name="applications", blank)
├── project_id (FK → CRM_PROJECT, related_name="applications", blank)
├── specialization_id (FK → CRM_SPECIALIZATION, blank)
├── status_id (FK → CRM_STATUS, blank)
├── message (Text, blank)
├── is_link (Boolean, default=False)
├── is_approved (Boolean, default=False)
├── comment (Text, blank)
├── date_sub (DateTime)
├── date_end (DateTime)
├── test_session_id (BigInt, blank)
└── custom_form_answers (JSON, default={})
```

**Связи:**

- ForeignKey: user (OneToMany)
- ForeignKey: event (OneToMany, nullable)
- ForeignKey: direction (OneToMany, nullable)
- ForeignKey: project (OneToMany, nullable)
- ForeignKey: specialization (OneToMany, nullable)
- ForeignKey: status (OneToMany, nullable)

---

### 1.6 ТЕСТИРОВАНИЕ

#### CRM_TEST

Тест для проверки знаний.

```
CRM_TEST
├── id (PK, BigInt)
├── name (VARCHAR 255)
├── description (Text, blank)
├── event_id (FK → CRM_EVENT, blank)
├── specialization_id (FK → CRM_SPECIALIZATION, blank)
├── entry (PositiveInt, default=0)
├── is_active (Boolean, default=True)
├── question_count (PositiveInt, default=0)
├── passing_score (PositiveInt)
├── time_limit_minutes (PositiveInt, blank)
└── attempts_allowed (PositiveInt, blank)
```

#### CRM_QUESTION

Вопрос теста.

```
CRM_QUESTION
├── id (PK, BigInt)
├── test_id (FK → CRM_TEST, related_name="questions")
├── text (Text)
├── order (PositiveInt)
└── type (VARCHAR 50)
```

#### CRM_ANSWER

Вариант ответа на вопрос.

```
CRM_ANSWER
├── id (PK, BigInt)
├── question_id (FK → CRM_QUESTION, related_name="answers")
├── text (Text)
└── order (PositiveInt)
```

#### CRM_TRUE_ANSWER

Правильный ответ на вопрос.

```
CRM_TRUE_ANSWER
├── id (PK, BigInt)
├── question_id (FK → CRM_QUESTION, related_name="true_answers")
└── answer_id (FK → CRM_ANSWER)
```

#### CRM_TEST_SESSION

Сессия прохождения теста пользователем.

```
CRM_TEST_SESSION
├── id (PK, BigInt)
├── session_id (BigInt, unique)
├── application_id (FK → CRM_APPLICATION, related_name="test_sessions")
├── test_id (FK → CRM_TEST)
├── user_id (FK → AUTH_USER)
├── started_at (DateTime)
├── completed_at (DateTime, blank)
├── status (VARCHAR 20) - choices: in_progress, completed, timeout
└── created_at (DateTime, auto_now_add)
```

#### CRM_TEST_RESULT

Результат прохождения теста.

```
CRM_TEST_RESULT
├── id (PK, BigInt)
├── test_id (FK → CRM_TEST)
├── application_id (FK → CRM_APPLICATION, related_name="test_results")
├── session_id (FK → CRM_TEST_SESSION, related_name="result", blank)
├── user_id (FK → AUTH_USER)
├── score (PositiveInt)
├── is_passed (Boolean)
├── completed_at (DateTime, auto_now_add)
└── answers_data (JSON)
```

---

### 1.7 УВЕДОМЛЕНИЯ

#### CRM_NOTIFICATION

Система уведомлений для пользователей.

```
CRM_NOTIFICATION
├── id (PK, BigInt)
├── user_id (FK → AUTH_USER, related_name="notifications")
├── title (VARCHAR 255)
├── description (Text, blank)
├── message (Text)
├── is_read (Boolean, default=False)
├── read_at (DateTime, blank)
└── created_at (DateTime, auto_now_add)
```

---

### 1.8 АВТОМАТИЗАЦИЯ CRM

#### CRM_AUTOMATION_CONFIG

Конфигурация правил автоматизации для мероприятий.

```
CRM_AUTOMATION_CONFIG
├── id (PK, BigInt)
├── scope (VARCHAR 32, default="crm")
├── event_id (BigInt, FK indirect)
├── stages (JSON)
├── triggers (JSON)
├── robots (JSON)
└── updated_at (DateTime, auto_now)
```

**Constraint**: UNIQUE(scope, event_id)

#### CRM_AUTOMATION_EXECUTION_LOG

Логи выполнения правил автоматизации.

```
CRM_AUTOMATION_EXECUTION_LOG
├── id (PK, BigInt)
├── config_id (FK → CRM_AUTOMATION_CONFIG)
├── event_id (BigInt)
├── team_id (BigInt, blank)
├── entity_type (VARCHAR 32)
├── entity_id (VARCHAR 64)
├── event_code (VARCHAR 100)
├── rule_kind (VARCHAR 16)
├── rule_id (VARCHAR 120)
├── run_key (VARCHAR 255, unique)
├── status (VARCHAR 16) - choices: pending, success, skipped, failed
├── message (Text, blank)
├── context (JSON)
├── scheduled_for (DateTime, blank)
├── executed_at (DateTime, blank)
└── created_at (DateTime, auto_now_add)
```

**Индексы:**

- (event_id, status)
- (scheduled_for, status)

#### CRM_AUTOMATION_ATTACHMENT

Прикрепленные файлы для автоматизации.

```
CRM_AUTOMATION_ATTACHMENT
├── id (PK, BigInt)
├── config_id (FK → CRM_AUTOMATION_CONFIG)
├── file (FileField)
├── uploaded_at (DateTime, auto_now_add)
└── created_by_id (FK → AUTH_USER, blank)
```

---

### 1.9 ПЛАНИРОВЩИК (PLANNER)

#### CRM_PLANNER_WORKSPACE_STATE

Состояние рабочего пространства планировщика.

```
CRM_PLANNER_WORKSPACE_STATE
├── id (PK)
├── enrollment_closed (Boolean, default=False)
├── participants (JSON, default=[])
├── teams (JSON, default=[])
├── parent_tasks (JSON, default=[])
├── subtasks (JSON, default=[])
├── columns (JSON, default=["Запланировано", "В работе", "На проверке", "Готово"])
└── updated_at (DateTime, auto_now)
```

#### CRM_TEAM_PLANNER_DESK

Доска планировщика для команды.

```
CRM_TEAM_PLANNER_DESK
├── id (PK)
├── team_id (BigInt, unique)
├── team_name (VARCHAR 255, blank)
├── curator_id (BigInt, blank)
├── member_ids (JSON, default=[])
├── parent_tasks (JSON, default=[])
├── subtasks (JSON, default=[])
├── columns (JSON, default=["Запланировано", "В работе", "На проверке", "Готово"])
└── updated_at (DateTime, auto_now)
```

#### CRM_PLANNER_AUTOMATION_CONFIG

Конфигурация автоматизации планировщика.

```
CRM_PLANNER_AUTOMATION_CONFIG
├── id (PK, BigInt)
├── scope (VARCHAR 32, default="planner")
├── event_id (BigInt)
├── stages (JSON)
├── triggers (JSON)
├── robots (JSON)
└── updated_at (DateTime, auto_now)
```

**Constraint**: UNIQUE(scope, event_id)

#### CRM_PLANNER_AUTOMATION_EXECUTION_LOG

Логи выполнения автоматизации планировщика.

```
CRM_PLANNER_AUTOMATION_EXECUTION_LOG
├── id (PK, BigInt)
├── config_id (FK → CRM_PLANNER_AUTOMATION_CONFIG)
├── event_id (BigInt)
├── team_id (BigInt, blank)
├── entity_type (VARCHAR 32)
├── entity_id (VARCHAR 64)
├── event_code (VARCHAR 100)
├── rule_kind (VARCHAR 16)
├── rule_id (VARCHAR 120)
├── run_key (VARCHAR 255, unique)
├── status (VARCHAR 16) - choices: pending, success, skipped, failed
├── message (Text, blank)
├── context (JSON)
├── scheduled_for (DateTime, blank)
├── executed_at (DateTime, blank)
└── created_at (DateTime, auto_now_add)
```
