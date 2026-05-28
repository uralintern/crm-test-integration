# Инструкция по сопровождению проекта

Этот файл нужен для будущих разработчиков или администратора заказчика. Здесь собраны основные команды для обслуживания сервиса на VPS.

## 1. Где находится проект

На новом сервере проект должен лежать здесь:

```bash
~/crm-test-integration
```

Если вход выполнен под пользователем `corleone`, полный путь будет:

```bash
/root/crm-test-integration
```

Основные файлы:

- `docker-compose.yml` - описание всех Docker-сервисов.
- `.env` - реальные настройки и секреты сервера.
- `ric-crm-planner/` - CRM-модуль.
- `test-constructor/` - модуль тестирования.
- `.github/workflows/ci-cd.yml` - автоматический деплой через GitHub Actions.

Файл `.env` нельзя выкладывать в GitHub.

## 2. Домены и сервер

CRM:

```text
https://meetuppoint.ru
```

Модуль тестирования:

```text
https://tests.meetuppoint.ru
```

VPS:

```text
5.181.108.146
```

DNS должен указывать оба домена на этот IP.

## 3. Автоматический деплой

Автоматический деплой выполняется через GitHub Actions после каждого push в ветку `main`.

Workflow:

```text
.github/workflows/ci-cd.yml
```

GitHub Secrets, которые нужны для деплоя:

- `VPS_HOST` - IP сервера - `5.181.108.146`.
- `VPS_USER` - SSH-пользователь - `corleone`.
- `VPS_SSH_KEY` - приватный SSH-ключ для подключения к серверу.
- `VPS_PROJECT_PATH` - путь до проекта, для нового VPS `/corleone/crm-test-integration`.

Секреты добавляются в GitHub так:

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

В поле `Name` пишется только имя, например:

```text
VPS_HOST
```

В поле `Secret` пишется только значение, например:

```text
5.181.108.146
```

Не нужно писать `VPS_HOST=5.181.108.146`. Знак `=` в GitHub Secrets не используется.

## 4. Как создать SSH-ключ для GitHub Actions

Если CI/CD настраивается с нуля, нужен SSH-ключ. GitHub Actions будет подключаться к VPS по этому ключу.

На своем компьютере в PowerShell:

```powershell
ssh-keygen -t ed25519 -C "github-actions-meetuppoint" -f "$env:USERPROFILE\.ssh\github_actions_meetuppoint"
```

Будут созданы два файла:

- приватный ключ: `github_actions_meetuppoint`
- публичный ключ: `github_actions_meetuppoint.pub`

Публичный ключ нужно добавить на VPS:

```bash
mkdir -p ~/.ssh
nano ~/.ssh/authorized_keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

Приватный ключ нужно добавить в GitHub Secret `VPS_SSH_KEY`.

Команда для вывода приватного ключа:

```powershell
Get-Content "$env:USERPROFILE\.ssh\github_actions_meetuppoint" -Raw
```

Команда для вывода публичного ключа:

```powershell
Get-Content "$env:USERPROFILE\.ssh\github_actions_meetuppoint.pub"
```

## 5. Ручное обновление на VPS

Если автоматический деплой не сработал, можно обновить вручную:

```bash
cd ~/crm-test-integration
git pull
docker compose up -d --build
docker compose exec backend python manage.py migrate
docker compose ps
```

## 6. Проверка состояния контейнеров

```bash
cd ~/crm-test-integration
docker compose ps
```

Все основные сервисы должны быть в статусе `Up`:

- `db`
- `backend`
- `automation`
- `testing-db`
- `testing-backend`
- `testing-web`
- `web`

## 7. Просмотр логов

CRM frontend / Caddy:

```bash
docker compose logs --tail=100 web
```

CRM backend:

```bash
docker compose logs --tail=100 backend
```

CRM automation worker:

```bash
docker compose logs --tail=100 automation
```

Testing backend:

```bash
docker compose logs --tail=100 testing-backend
```

Все логи сразу:

```bash
docker compose logs --tail=100
```

## 8. Перезапуск сервисов

Перезапустить все сервисы:

```bash
docker compose restart
```

Перезапустить только CRM backend:

```bash
docker compose restart backend
```

Перезапустить только frontend/Caddy:

```bash
docker compose restart web
```

## 9. Создать главного организатора

Создать суперпользователя Django:

```bash
docker compose exec backend python manage.py createsuperuser
```

После этого можно войти в Django admin:

```text
https://meetuppoint.ru/admin/
```

Чтобы сделать обычного пользователя главным организатором CRM, нужно в админке назначить ему CRM-роль `curator` или `admin`, в зависимости от текущей модели ролей проекта.

## 10. Где менять настройки VK

Все VK-настройки лежат в `.env` на VPS:

- `VK_ENABLED`
- `VK_GROUP_ID`
- `VK_ACCESS_TOKEN`
- `VK_CALLBACK_SECRET`
- `VK_CONFIRMATION_CODE`
- `VK_CHAT_LINK_BASE_URL`
- `VK_BOT_FRONTEND_URL`
- `VK_ORG_CHAT_URL`
- `VK_ORG_CHAT_PEER_ID`

После изменения `.env` нужно перезапустить backend и automation:

```bash
docker compose up -d --build backend automation web
```

## 11. Что делать, если сайт не открывается

Проверить контейнеры:

```bash
docker compose ps
```

Проверить Caddy:

```bash
docker compose logs --tail=100 web
```

Проверить backend:

```bash
docker compose logs --tail=100 backend
```

Проверить DNS:

```bash
nslookup meetuppoint.ru
nslookup tests.meetuppoint.ru
```

Оба домена должны возвращать IP:

```text
5.181.108.146
```
