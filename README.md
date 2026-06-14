# CRM для набора проектантов и модуль тестирования

Репозиторий содержит единый сервис для организации практик, стажировок и проектных школ. Сервис закрывает процесс от публикации мероприятия и сбора заявок до автоматизации статусов, тестирования, формирования команд и ведения задач в планировщике.

## Что входит в сервис

- CRM: мероприятия, направления, проекты, заявки, статусы, роли, профиль пользователя, экспорт данных.
- Автоматизация CRM: роботы и триггеры для обработки заявок, отправки VK-сообщений и изменения статусов.
- Планировщик: формирование команд, бэклог, канбан, диаграмма Ганта, WebSocket-обновления задач между пользователями.
- Модуль тестирования: создание тестов, прохождение тестов проектантами, SSO-переход из CRM, возврат результатов в CRM.
- VK-интеграция: подтверждение VK, отправка сообщений, ссылки в оргчат, подтверждение участия в проектной школе.
- CI/CD: сборка Docker-образов в GitHub Actions, публикация в GitHub Container Registry и деплой на VPS.

## Основные адреса production

- CRM: `https://meetuppoint.ru`
- Модуль тестирования: `https://test.meetuppoint.ru`
- VPS: `5.181.108.146`
- Путь проекта на VPS: `/home/corleone/crm-test-integration`

Если проект передается другому владельцу, домены, IP и путь могут измениться. В этом случае нужно обновить `.env` на VPS, DNS-записи и GitHub Secrets.

## Структура репозитория

```text
.
|-- .github/workflows/ci-cd.yml       # GitHub Actions: сборка образов и деплой
|-- docker-compose.yml                # локальная/ручная сборка из исходников
|-- docker-compose.local.yml          # override для локального запуска без HTTPS
|-- docker-compose.prod.yml           # production запуск из готовых GHCR-образов
|-- .env.example                      # шаблон переменных окружения для всего сервиса
|-- DEPLOY_INTEGRATION.md             # первый деплой и настройка CI/CD
|-- MAINTENANCE.md                    # обслуживание production-сервера
|-- ric-crm-planner/
|   |-- back/                         # Django backend CRM
|   `-- front/                        # React + TypeScript frontend CRM
`-- test-constructor/
    |-- backend/                      # Go backend модуля тестирования
    `-- frontend/                     # React frontend модуля тестирования
```

## Production-сервисы Docker

В production используется `docker-compose.prod.yml`. Он не собирает проект на сервере, а скачивает готовые образы из GHCR.

Сервисы:

- `db` - PostgreSQL для CRM.
- `backend` - Django API CRM.
- `automation` - воркер автоматизации CRM и планировщика.
- `testing-db` - PostgreSQL для модуля тестирования.
- `testing-backend` - backend конструктора тестов.
- `testing-web` - frontend конструктора тестов.
- `web` - Caddy, frontend CRM, HTTPS, reverse proxy к backend и модулю тестирования.

## Как работает CI/CD

Схема:

```text
push в main
  -> GitHub Actions
  -> сборка Docker-образов
  -> публикация в ghcr.io
  -> SSH на VPS
  -> git pull
  -> docker compose pull
  -> docker compose up -d
  -> миграции Django
```

На VPS не выполняется `docker compose up -d --build`. Это сделано специально: сборка frontend/backend на слабом VPS быстро забивает диск и оперативную память.

Подробная настройка CI/CD описана в `DEPLOY_INTEGRATION.md`.

## Быстрый локальный запуск

Нужны Docker и Docker Compose plugin.

1. Создать `.env`:

```bash
cp .env.example .env
```

2. Заполнить обязательные пароли и токены в `.env`.

3. Запустить локально:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

4. Открыть CRM:

```text
http://localhost
```

5. Открыть модуль тестирования:

```text
http://testing.localhost
```

Если `testing.localhost` не открывается, проверьте, что браузер и ОС корректно резолвят `*.localhost`.

## Быстрая проверка production

На VPS:

```bash
cd ~/crm-test-integration
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=100 backend
docker compose -f docker-compose.prod.yml logs --tail=100 web
```

Проверить DNS:

```bash
nslookup meetuppoint.ru
nslookup test.meetuppoint.ru
```

Оба домена должны указывать на IP VPS.

## Где хранятся настройки

- `.env.example` хранится в GitHub и содержит только шаблон.
- `.env` хранится только локально или на VPS и не должен попадать в GitHub.
- GitHub Secrets хранят SSH-доступ к VPS для CI/CD.
- GitHub Container Registry хранит Docker-образы.

## Что нельзя коммитить

- реальный `.env`;
- приватные SSH-ключи;
- токены VK;
- пароли баз данных;
- токены GHCR;
- дампы production-базы.

## Основные команды

Production restart:

```bash
cd ~/crm-test-integration
docker compose -f docker-compose.prod.yml up -d
```

Миграции CRM:

```bash
docker compose -f docker-compose.prod.yml exec -T backend python manage.py migrate
```

Создать администратора CRM:

```bash
docker compose -f docker-compose.prod.yml exec backend python manage.py createsuperuser
```

Логи:

```bash
docker compose -f docker-compose.prod.yml logs --tail=100
```

Очистка ненужных Docker-образов:

```bash
docker image prune -f
docker builder prune -f
```

## Документация

- `DEPLOY_INTEGRATION.md` - установка Docker, настройка VPS, DNS, `.env`, GitHub Secrets и CI/CD.
- `MAINTENANCE.md` - обновление сервиса, ручной deploy, логи, бэкапы, чистка места, передача проекта.