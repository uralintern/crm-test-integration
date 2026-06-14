# Сопровождение CRM и модуля тестирования

Документ нужен для разработчиков и администратора, которые будут поддерживать сервис после передачи проекта.

## 1. Где находится проект

На production VPS:

```bash
/home/corleone/crm-test-integration
```

Основные файлы:

- `docker-compose.prod.yml` - production запуск из готовых GHCR-образов.
- `docker-compose.yml` - локальная или ручная сборка из исходников.
- `docker-compose.local.yml` - локальный override без HTTPS.
- `.env` - реальные настройки сервера, не хранится в GitHub.
- `.env.example` - шаблон переменных.
- `.github/workflows/ci-cd.yml` - CI/CD.
- `ric-crm-planner/` - CRM.
- `test-constructor/` - модуль тестирования.

## 2. Проверка состояния сервиса

```bash
cd ~/crm-test-integration
docker compose -f docker-compose.prod.yml ps
```

В норме запущены:

- `db`;
- `backend`;
- `automation`;
- `testing-db`;
- `testing-backend`;
- `testing-web`;
- `web`.

## 3. Просмотр логов

Все сервисы:

```bash
docker compose -f docker-compose.prod.yml logs --tail=100
```

CRM backend:

```bash
docker compose -f docker-compose.prod.yml logs --tail=100 backend
```

CRM frontend, Caddy, HTTPS:

```bash
docker compose -f docker-compose.prod.yml logs --tail=100 web
```

Automation worker:

```bash
docker compose -f docker-compose.prod.yml logs --tail=100 automation
```

Testing backend:

```bash
docker compose -f docker-compose.prod.yml logs --tail=100 testing-backend
```

Следить за логами в реальном времени:

```bash
docker compose -f docker-compose.prod.yml logs -f backend
```

## 4. Перезапуск

Перезапустить все сервисы:

```bash
cd ~/crm-test-integration
docker compose -f docker-compose.prod.yml restart
```

Перезапустить только CRM backend и automation:

```bash
docker compose -f docker-compose.prod.yml restart backend automation
```

Перезапустить Caddy/frontend:

```bash
docker compose -f docker-compose.prod.yml restart web testing-web
```

После изменения `.env` лучше выполнить:

```bash
docker compose -f docker-compose.prod.yml up -d
```

## 5. Обновление через CI/CD

Обычный порядок обновления:

1. Разработчик вносит изменения.
2. Делает commit и push в `main`.
3. GitHub Actions собирает Docker-образы.
4. GitHub Actions публикует образы в GHCR.
5. GitHub Actions подключается к VPS и перезапускает контейнеры.

Проверить результат на VPS:

```bash
cd ~/crm-test-integration
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=100 backend
```

## 6. Ручное обновление production

Использовать, если workflow не запускался или нужно вручную подтянуть готовые образы.

```bash
cd ~/crm-test-integration
git pull
export IMAGE_PREFIX=ghcr.io/<github_owner>/<repo_name>
export IMAGE_TAG=latest
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec -T backend python manage.py migrate
docker compose -f docker-compose.prod.yml ps
```

Если получаете `denied` при pull:

```bash
echo <GHCR_TOKEN> | docker login ghcr.io -u <GITHUB_USERNAME> --password-stdin
```

## 7. Миграции Django

Запустить миграции CRM:

```bash
docker compose -f docker-compose.prod.yml exec -T backend python manage.py migrate
```

Проверить список миграций:

```bash
docker compose -f docker-compose.prod.yml exec backend python manage.py showmigrations
```

## 8. Создание администратора CRM

```bash
docker compose -f docker-compose.prod.yml exec backend python manage.py createsuperuser
```

Админка:

```text
https://meetuppoint.ru/admin/
```

Если появляется CSRF ошибка, проверить `.env`:

```env
DJANGO_CSRF_TRUSTED_ORIGINS=https://meetuppoint.ru
DJANGO_ALLOWED_HOSTS=meetuppoint.ru,5.181.108.146,localhost,127.0.0.1,backend
```

После изменения `.env`:

```bash
docker compose -f docker-compose.prod.yml up -d
```

## 9. Настройки VK

VK-настройки находятся в `.env` на VPS:

```env
VK_ENABLED=1
VK_GROUP_ID=...
VK_ACCESS_TOKEN=...
VK_CALLBACK_SECRET=...
VK_CONFIRMATION_CODE=...
VK_CHAT_LINK_BASE_URL=https://meetuppoint.ru
VK_BOT_FRONTEND_URL=https://meetuppoint.ru
VK_ORG_CHAT_URL=...
VK_ORG_CHAT_PEER_ID=...
```

После изменения:

```bash
docker compose -f docker-compose.prod.yml up -d
```

Если VK-сообщения не отправляются, смотреть:

```bash
docker compose -f docker-compose.prod.yml logs --tail=100 backend
docker compose -f docker-compose.prod.yml logs --tail=100 automation
```

## 10. Модуль тестирования

CRM открывает тестирование через SSO-ссылку. Ссылку создает backend CRM, frontend только запрашивает ее и открывает пользователю.

Проверить testing services:

```bash
docker compose -f docker-compose.prod.yml ps testing-backend testing-web testing-db
```

Логи:

```bash
docker compose -f docker-compose.prod.yml logs --tail=100 testing-backend
```

Если CRM не предлагает пройти тест, проверить:

- есть ли активные тесты в модуле тестирования;
- назначены ли тесты на мероприятие/специализацию;
- возвращает ли заявка поле наличия доступных тестов;
- корректны ли `TESTING_SERVICE_URL` и `TESTING_SERVICE_TOKEN`.

## 11. Планировщик и WebSocket

Планировщик хранит общее состояние workspace и отдельные доски команд. Для задач используется endpoint команды и WebSocket:

```text
PUT /api/planner/teams/{team_id}/desk/
wss://meetuppoint.ru/ws/planner/teams/{team_id}/
```

Если изменения задач не появляются у другого пользователя без обновления страницы:

1. Открыть DevTools -> Network -> Socket.
2. Проверить подключение к `wss://meetuppoint.ru/ws/planner/teams/<id>/`.
3. Проверить, что статус WebSocket `101 Switching Protocols`.
4. Посмотреть логи backend:

```bash
docker compose -f docker-compose.prod.yml logs --tail=100 backend
```

## 12. Бэкап CRM базы

Создать папку для бэкапов:

```bash
mkdir -p ~/backups
```

Сделать dump CRM базы:

```bash
cd ~/crm-test-integration
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > ~/backups/crm_$(date +%F_%H-%M).sql
```

Если переменные из `.env` не подставились в shell, выполнить явно:

```bash
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U crm_user crm_bd > ~/backups/crm_$(date +%F_%H-%M).sql
```

## 13. Бэкап базы тестирования

```bash
cd ~/crm-test-integration
docker compose -f docker-compose.prod.yml exec -T testing-db pg_dump -U "$TESTING_DB_USER" "$TESTING_DB_NAME" > ~/backups/testing_$(date +%F_%H-%M).sql
```

Или явно:

```bash
docker compose -f docker-compose.prod.yml exec -T testing-db pg_dump -U testing_user test_constructor > ~/backups/testing_$(date +%F_%H-%M).sql
```

## 14. Восстановление базы

Восстановление перезаписывает данные. Перед восстановлением сделать свежий backup.

CRM:

```bash
cd ~/crm-test-integration
docker compose -f docker-compose.prod.yml exec -T db psql -U crm_user crm_bd < ~/backups/crm_BACKUP.sql
```

Testing:

```bash
docker compose -f docker-compose.prod.yml exec -T testing-db psql -U testing_user test_constructor < ~/backups/testing_BACKUP.sql
```

## 15. Проверка места на сервере

```bash
df -h
docker system df
```

Подробно по Docker:

```bash
docker system df -v
```

## 16. Очистка Docker

Безопасная очистка неиспользуемых образов:

```bash
docker image prune -f
```

Очистка build cache:

```bash
docker builder prune -f
```

Очистка остановленных контейнеров, сетей и dangling images:

```bash
docker system prune -f
```

Не выполнять без понимания последствий:

```bash
docker volume prune
```

Volumes содержат базы PostgreSQL. Удаление volumes может удалить данные CRM и тестирования.

## 17. Проверка DNS и HTTPS

```bash
nslookup meetuppoint.ru
nslookup test.meetuppoint.ru
```

Проверить сертификат:

```bash
curl -Iv https://meetuppoint.ru
curl -Iv https://test.meetuppoint.ru
```

Проверить Caddy:

```bash
docker compose -f docker-compose.prod.yml logs --tail=100 web
```

Если Google Chrome пишет, что сайт опасный, но сертификат корректный, это может быть Google Safe Browsing. Тогда нужно проверять статус в Google Search Console и отправлять запрос на повторную проверку после удаления подозрительного контента.

## 18. Частые проблемы

### `required variable IMAGE_PREFIX is missing`

Вы запустили `docker-compose.prod.yml` вручную без переменных образов.

```bash
export IMAGE_PREFIX=ghcr.io/<github_owner>/<repo_name>
export IMAGE_TAG=latest
docker compose -f docker-compose.prod.yml up -d
```

### `error from registry: denied`

Нет доступа к GHCR.

```bash
echo <GHCR_TOKEN> | docker login ghcr.io -u <GITHUB_USERNAME> --password-stdin
```

### `no space left on device`

Проверить место:

```bash
df -h
docker system df
```

Очистить:

```bash
docker image prune -f
docker builder prune -f
```

### Backend не подключается к базе

Проверить `.env`:

```env
DB_NAME=crm_bd
DB_USER=crm_user
DB_PASSWORD=...
DB_HOST=db
DB_PORT=5432
```

Проверить контейнеры:

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=100 db backend
```

### После изменения `.env` ничего не поменялось

Пересоздать контейнеры:

```bash
docker compose -f docker-compose.prod.yml up -d
```