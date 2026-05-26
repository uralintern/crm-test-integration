# Развертывание CRM и модуля тестирования

Этот документ описывает запуск проекта на VPS. Проект состоит из двух частей:

- CRM-модуль: мероприятия, заявки, статусы, роботы, VK-интеграция, планировщик.
- Модуль тестирования: создание тестов, назначение тестов на мероприятия, прохождение тестов проектантами, передача результата обратно в CRM.

Оба модуля запускаются вместе через общий `docker-compose.yml`.

## 1. Данные нового сервера

Основной домен CRM:

```text
meetuppoint.ru
```

IP-адрес VPS:

```text
5.181.108.146
```

Рекомендуемый домен для модуля тестирования:

```text
tests.meetuppoint.ru
```

Если заказчик хочет другой адрес для тестирования, нужно заменить `tests.meetuppoint.ru` в `.env` и DNS-записях.

## 2. DNS

У домена должны быть A-записи:

```text
meetuppoint.ru        -> 5.181.108.146
tests.meetuppoint.ru  -> 5.181.108.146
```

Без второй записи модуль тестирования не откроется по отдельному домену.

## 3. Подготовка `.env` на VPS

Файл `.env` хранится только на сервере. Его нельзя коммитить в GitHub.

На сервере:

```bash
cd ~/crm-test-integration
cp .env.example .env
nano .env
```

Основные значения для нового сервера:

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

Также в `.env` обязательно должны быть заполнены реальные секреты:

- `DJANGO_SECRET_KEY`
- `DB_PASSWORD`
- `TESTING_DB_PASSWORD`
- `TESTING_ADMIN_PASSWORD`
- `TESTING_JWT_SECRET`
- `TESTING_SERVICE_TOKEN`
- `VK_ACCESS_TOKEN`
- `VK_CALLBACK_SECRET`
- `VK_CONFIRMATION_CODE`

`TESTING_SERVICE_TOKEN` должен быть одинаковым для CRM и модуля тестирования. В текущем compose он автоматически передается в testing-backend как `CRM_TOKEN`.

## 4. Первый запуск на VPS

На сервере:

```bash
cd ~/crm-test-integration
docker compose up -d --build
docker compose exec backend python manage.py migrate
docker compose ps
```

Создать главного администратора/организатора CRM:

```bash
docker compose exec backend python manage.py createsuperuser
```

После запуска открыть:

```text
https://meetuppoint.ru
https://tests.meetuppoint.ru
```

Caddy автоматически выпустит HTTPS-сертификаты, если DNS уже указывает на VPS.

## 5. Локальный запуск

Для локального запуска без HTTPS и без изменения файла hosts:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

Открыть CRM:

```text
http://localhost
```

## 6. Ручное обновление на VPS

Если CI/CD временно не используется, обновить проект можно вручную:

```bash
cd ~/crm-test-integration
git pull
docker compose up -d --build
docker compose exec backend python manage.py migrate
docker compose ps
```

## 7. CI/CD

Автоматический деплой настроен в файле:

```text
.github/workflows/ci-cd.yml
```

После каждого push в ветку `main` GitHub Actions:

1. Проверяет `docker-compose.yml`.
2. Собирает Docker-образы.
3. Подключается к VPS по SSH.
4. Выполняет `git pull`.
5. Пересобирает и перезапускает сервисы.
6. Запускает миграции CRM backend.

Для работы CI/CD в GitHub нужно добавить Repository Secrets:

- `VPS_HOST`
- `VPS_USER`
- `VPS_SSH_KEY`
- `VPS_PROJECT_PATH`

Для нового сервера значения такие:

```text
VPS_HOST = 5.181.108.146
VPS_USER = root
VPS_PROJECT_PATH = /root/crm-test-integration
```

Если пользователь на сервере не `root`, путь будет другим, например:

```text
/home/username/crm-test-integration
```

## 8. Как создать SSH-ключ для GitHub Actions

Если заказчик дал логин и пароль от VPS, для CI/CD лучше создать отдельный SSH-ключ специально для GitHub Actions.

На своем компьютере в PowerShell:

```powershell
ssh-keygen -t ed25519 -C "github-actions-meetuppoint" -f "$env:USERPROFILE\.ssh\github_actions_meetuppoint"
```

Если спросит passphrase, можно просто нажать Enter, чтобы ключ был без пароля. Для GitHub Actions это проще.

После этого появятся два файла:

```text
C:\Users\<имя_пользователя>\.ssh\github_actions_meetuppoint
C:\Users\<имя_пользователя>\.ssh\github_actions_meetuppoint.pub
```

- `github_actions_meetuppoint` - приватный ключ. Его нужно добавить в GitHub Secret `VPS_SSH_KEY`.
- `github_actions_meetuppoint.pub` - публичный ключ. Его нужно добавить на VPS в `~/.ssh/authorized_keys`.

Показать публичный ключ:

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

В файл `authorized_keys` нужно вставить содержимое `.pub` файла одной строкой.

Показать приватный ключ для GitHub Secret:

```powershell
Get-Content "$env:USERPROFILE\.ssh\github_actions_meetuppoint" -Raw
```

В GitHub Secret `VPS_SSH_KEY` вставляется весь текст, включая строки:

```text
-----BEGIN OPENSSH PRIVATE KEY-----
...
-----END OPENSSH PRIVATE KEY-----
```

## 9. Как работает SSO между CRM и тестированием

1. Пользователь находится в CRM.
2. CRM создает одноразовый ticket через `/api/users/integration/testing/sso-link/`.
3. Пользователь переходит в модуль тестирования по ссылке `/sso?ticket=...`.
4. Testing backend отправляет ticket обратно в CRM на `/api/users/integration/testing/sso-exchange/`.
5. CRM проверяет ticket и возвращает данные пользователя.
6. Модуль тестирования создает или обновляет локального пользователя.
7. Если пользователь организатор CRM, в тестировании он становится `manager`.
8. Если пользователь проектант CRM, в тестировании он становится `intern`.
9. После прохождения теста testing backend отправляет результат обратно в CRM.
