"""Настройки для запуска тестов.

PostgreSQL берётся из тех же переменных окружения, что и в api.settings.
Имя тестовой базы можно переопределить через TEST_DB_NAME, чтобы параллельные
прогоны не мешали друг другу.

Запуск:
    python manage.py test --settings=api.settings_test
"""

import os

from api.settings import *  # noqa: F401,F403
from api.settings import DATABASES

DATABASES["default"]["TEST"] = {"NAME": os.getenv("TEST_DB_NAME", "test_crm_bd")}

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Тесты никогда не ходят в настоящий VK, даже если в локальном .env он включён.
VK_ENABLED = False
VK_ACCESS_TOKEN = ""
