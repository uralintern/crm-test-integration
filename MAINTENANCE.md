# Инструкция по сопровождению проекта

Файл нужен для будущих разработчиков и администратора заказчика. Здесь собраны основные команды для production-сервера.

## 1. Где находится проект

На VPS проект должен лежать здесь:

```bash
/home/corleone/crm-test-integration
```

Основные файлы:

- `docker-compose.yml` - compose для локальной разработки и ручной сборки.
- `docker-compose.prod.yml` - compose для production, использует готовые образы из GHCR.
- `.env` - реальные настройки и секреты сервера, не хранится в GitHub.
- `.env.example` - шаблон переменных окружения.
- `ric-crm-planner/` - CRM и планировщик.
- `test-constructor/` - модуль тестирования.
- `.github/workflows/ci-cd.yml` - автоматическая сборка и деплой.

## 2. Как работает production-деплой

Production-деплой не собирает проект на VPS.

Правильная схема:

```text
GitHub Actions -> сборка Docker images -> публикация в GHCR -> VPS pull -> VPS up
```

Это сделано для экономии ресурсов VPS. Сборка frontend через Node.js и backend через Go/Python может занимать много RAM и диска. На слабом VPS это приводит к ошибкам `no space left on device`, зависаниям `npm ci` и высокой нагрузке.

## 3. Автоматический деплой

Автоматический деплой запускается после push в ветку `main`.

Workflow:

```text
.github/workflows/ci-cd.yml
```

GitHub Actions делает следующее:

1. Проверяет `docker-compose.yml`.
2. Проверяет `docker-compose.prod.yml`.
3. Собирает Docker-образы.
4. Публикует образы в `ghcr.io`.
5. Подключается к VPS по SSH.
6. Выполняет `git pull`.
7. Скачивает новые образы.
8. Перезапускает контейнеры.
9. Запускает миграции CRM backend.

Нужные GitHub Secrets:

- `VPS_HOST` - IP сервера, например `5.181.108.146`.
- `VPS_USER` - SSH-пользователь, например `corleone`.
- `VPS_PROJECT_PATH` - путь к проекту, например `/home/corleone/crm-test-integration`.
- `VPS_SSH_KEY` - приватный SSH-ключ для подключения к серверу.

## 4. Проверка состояния контейнеров

На VPS:

```bash
cd ~/crm-test-integration
docker compose -f docker-compose.prod.yml ps
```

В норме должны быть запущены:

- `db`
- `backend`
- `automation`
- `testing-db`
- `testing-backend`
- `testing-web`
- `web`

## 5. Просмотр логов

Все логи:

```bash
docker compose -f docker-compose.prod.yml logs --tail=100
```

CRM frontend и Caddy:

```bash
docker compose -f docker-compose.prod.yml logs --tail=100 web
```

CRM backend:

```bash
docker compose -f docker-compose.prod.yml logs --tail=100 backend
```

CRM automation worker:

```bash
docker compose -f docker-compose.prod.yml logs --tail=100 automation
```

Testing backend:

```bash
docker compose -f docker-compose.prod.yml logs --tail=100 testing-backend
```

## 6. Перезапуск сервисов

Перезапустить все сервисы:

```bash
docker compose -f docker-compose.prod.yml restart
```

Перезапустить только CRM backend:

```bash
docker compose -f docker-compose.prod.yml restart backend automation
```

Перезапустить только frontend/Caddy:

```bash
docker compose -f docker-compose.prod.yml restart web testing-web
```

После изменения `.env` лучше выполнить:

```bash
docker compose -f docker-compose.prod.yml up -d
```

Сборку добавлять не нужно. В production не используется `--build`.

## 7. Ручное обновление production

Если нужно обновить сервер вручную без запуска GitHub Actions:

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

Если GHCR-пакеты приватные, сначала выполнить:

```bash
echo <GHCR_TOKEN> | docker login ghcr.io -u <GITHUB_USERNAME> --password-stdin
```

Token должен иметь право `read:packages`.

## 8. Локальный или тестовый запуск со сборкой

Если нужно собрать проект прямо на сервере или локально, используется обычный compose:

```bash
docker compose up -d --build
```

Для локального запуска без HTTPS:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

Важно: этот вариант тяжелее по ресурсам, потому что Docker собирает образы из исходников.

## 9. Очистка Docker на VPS

Посмотреть использование места:

```bash
docker system df
```

Удалить неиспользуемые образы:

```bash
docker image prune -f
```

Удалить build cache:

```bash
docker builder prune -f
```

Полная очистка неиспользуемых Docker-ресурсов:

```bash
docker system prune -f
```

Не использовать `docker volume prune`, если не нужно удалить базы данных. Volumes хранят PostgreSQL-данные.

## 10. Создание главного организатора

Создать Django superuser:

```bash
docker compose -f docker-compose.prod.yml exec backend python manage.py createsuperuser
```

После этого можно зайти в админку:

```text
https://meetuppoint.ru/admin/
```

## 11. Настройки VK

VK-настройки находятся в `.env` на VPS:

- `VK_ENABLED`
- `VK_GROUP_ID`
- `VK_ACCESS_TOKEN`
- `VK_CALLBACK_SECRET`
- `VK_CONFIRMATION_CODE`
- `VK_CHAT_LINK_BASE_URL`
- `VK_BOT_FRONTEND_URL`
- `VK_ORG_CHAT_URL`
- `VK_ORG_CHAT_PEER_ID`

После изменения `.env` выполнить:

```bash
docker compose -f docker-compose.prod.yml up -d
```

## 12. Проверка DNS и HTTPS

Проверить DNS:

```bash
nslookup meetuppoint.ru
nslookup tests.meetuppoint.ru
```

Оба домена должны возвращать IP VPS:

```text
5.181.108.146
```

Caddy сам выпускает HTTPS-сертификаты, если DNS уже указывает на VPS и открыты порты `80` и `443`.

Проверить порты:

```bash
sudo ufw status
```

Если firewall включен, открыть порты:

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```