# Развертывание CRM и модуля тестирования

Этот документ описывает промышленный вариант запуска проекта на VPS. Проект состоит из двух частей:

- CRM-модуль: мероприятия, направления, проекты, заявки, статусы, роботы, VK-интеграция, планировщик.
- Модуль тестирования: создание тестов, назначение тестов на мероприятия, прохождение тестов проектантами и передача результата обратно в CRM.

Оба модуля запускаются вместе. Разделять их в production не нужно.

## 1. Как теперь устроен деплой

Нормальная схема для сервера такая:

1. GitHub Actions собирает Docker-образы.
2. GitHub Actions публикует образы в GitHub Container Registry: `ghcr.io`.
3. VPS подключается по SSH.
4. На VPS выполняется `git pull`, чтобы забрать новый `docker-compose.prod.yml` и конфигурацию.
5. VPS скачивает готовые образы через `docker compose pull`.
6. VPS перезапускает контейнеры через `docker compose up -d`.
7. VPS запускает миграции CRM backend.

Главная разница: на VPS больше не выполняется тяжелая сборка `docker compose up -d --build`. Серверу не нужно держать Node.js/Go/Python build cache, поэтому деплой быстрее и меньше забивает диск.

## 2. Домены и сервер

Основной домен CRM:

```text
meetuppoint.ru
```

Домен модуля тестирования:

```text
tests.meetuppoint.ru
```

IP VPS:

```text
5.181.108.146
```

DNS должен указывать оба домена на VPS:

```text
meetuppoint.ru        -> 5.181.108.146
tests.meetuppoint.ru  -> 5.181.108.146
```

Если `tests.meetuppoint.ru` не создан, модуль тестирования по отдельному адресу не откроется.

## 3. Файлы compose

В проекте используются два compose-файла:

```text
docker-compose.yml
```

Используется для локальной разработки и ручной сборки на тестовом сервере. В нем есть секции `build`, поэтому Docker собирает образы из исходников.

```text
docker-compose.prod.yml
```

Используется для production-деплоя. В нем нет секций `build`, только готовые `image` из GHCR. Именно этот файл использует CI/CD на VPS.

## 4. Подготовка VPS

Зайти на сервер:

```bash
ssh corleone@5.181.108.146
```

Установить Docker, если он еще не установлен:

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg git
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
```

После `usermod` нужно выйти с сервера и зайти снова, чтобы группа `docker` применилась.

Клонировать проект:

```bash
cd ~
git clone <URL_РЕПОЗИТОРИЯ> crm-test-integration
cd ~/crm-test-integration
```

## 5. Файл `.env` на VPS

Файл `.env` хранится только на сервере. Его нельзя коммитить в GitHub.

Создать файл:

```bash
cd ~/crm-test-integration
cp .env.example .env
nano .env
```

Основные значения для production:

```env
APP_DOMAIN=meetuppoint.ru
TESTING_DOMAIN=tests.meetuppoint.ru

VITE_API_BASE=
VITE_USE_MOCK=false
VITE_TESTING_URL=https://tests.meetuppoint.ru

DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=meetuppoint.ru,5.181.108.146,localhost,127.0.0.1,backend
DJANGO_CSRF_TRUSTED_ORIGINS=https://meetuppoint.ru
DJANGO_CORS_ALLOW_ALL_ORIGINS=0
DJANGO_CORS_ALLOWED_ORIGINS=https://meetuppoint.ru,https://tests.meetuppoint.ru

TESTING_SERVICE_URL=https://tests.meetuppoint.ru
VK_CHAT_LINK_BASE_URL=https://meetuppoint.ru
VK_BOT_FRONTEND_URL=https://meetuppoint.ru
```

Обязательно заполнить реальными значениями:

- `DJANGO_SECRET_KEY`
- `DB_PASSWORD`
- `TESTING_DB_PASSWORD`
- `TESTING_ADMIN_PASSWORD`
- `TESTING_JWT_SECRET`
- `TESTING_SERVICE_TOKEN`
- `VK_ACCESS_TOKEN`
- `VK_CALLBACK_SECRET`
- `VK_CONFIRMATION_CODE`

Суперпользователь CRM через `.env` не создается. Его нужно создать вручную после первого запуска.

## 6. GitHub Secrets для CI/CD

В GitHub открыть:

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

Добавить секреты:

```text
VPS_HOST
```

Значение:

```text
5.181.108.146
```

```text
VPS_USER
```

Значение:

```text
corleone
```

```text
VPS_PROJECT_PATH
```

Значение:

```text
/home/corleone/crm-test-integration
```

```text
VPS_SSH_KEY
```

Значение: приватный SSH-ключ целиком, включая строки:

```text
-----BEGIN OPENSSH PRIVATE KEY-----
...
-----END OPENSSH PRIVATE KEY-----
```

Ключ вставляется многострочно, не в одну строку.

Знак `=` в GitHub Secrets писать не нужно. В поле `Name` пишется имя секрета, в поле `Secret` только значение.

## 7. SSH-ключ для GitHub Actions

На локальном компьютере создать ключ:

```powershell
ssh-keygen -t ed25519 -C "github-actions-meetuppoint" -f "$env:USERPROFILE\.ssh\github_actions_meetuppoint"
```

Публичный ключ вывести так:

```powershell
Get-Content "$env:USERPROFILE\.ssh\github_actions_meetuppoint.pub"
```

На VPS добавить публичный ключ:

```bash
mkdir -p ~/.ssh
nano ~/.ssh/authorized_keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

В `authorized_keys` вставляется содержимое `.pub` файла одной строкой.

Приватный ключ вывести так:

```powershell
Get-Content "$env:USERPROFILE\.ssh\github_actions_meetuppoint" -Raw
```

Его нужно вставить в GitHub Secret `VPS_SSH_KEY`.

## 8. Первый production-запуск через CI/CD

После настройки `.env`, DNS и GitHub Secrets достаточно сделать push в `main`.

GitHub Actions выполнит:

1. Проверку compose-файлов.
2. Сборку четырех образов: CRM backend, CRM frontend, testing backend, testing frontend.
3. Публикацию образов в GHCR.
4. Подключение к VPS по SSH.
5. `docker compose -f docker-compose.prod.yml pull`.
6. `docker compose -f docker-compose.prod.yml up -d`.
7. Миграции CRM backend.

Проверить контейнеры на VPS:

```bash
cd ~/crm-test-integration
docker compose -f docker-compose.prod.yml ps
```

Создать суперпользователя CRM:

```bash
docker compose -f docker-compose.prod.yml exec backend python manage.py createsuperuser
```

## 9. Ручной production-деплой без сборки на VPS

Если нужно вручную перезапустить production без GitHub Actions:

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

Если GHCR-пакеты приватные, перед `pull` нужно выполнить login:

```bash
echo <GHCR_TOKEN> | docker login ghcr.io -u <GITHUB_USERNAME> --password-stdin
```

Для ручного pull нужен GitHub token с правом `read:packages`.

## 10. Локальный запуск

Для локальной проверки используется обычный compose с локальным override:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

Открыть CRM:

```text
http://localhost
```

## 11. Если сайт не открывается

Проверить DNS:

```bash
nslookup meetuppoint.ru
nslookup tests.meetuppoint.ru
```

Оба домена должны возвращать:

```text
5.181.108.146
```

Проверить контейнеры:

```bash
cd ~/crm-test-integration
docker compose -f docker-compose.prod.yml ps
```

Проверить Caddy:

```bash
docker compose -f docker-compose.prod.yml logs --tail=100 web
```

Проверить backend:

```bash
docker compose -f docker-compose.prod.yml logs --tail=100 backend
```