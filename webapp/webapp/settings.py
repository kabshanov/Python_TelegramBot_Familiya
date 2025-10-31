"""
settings.py
============

Глобальные настройки Django-проекта **Calendar WebApp**.

Назначение:
- определяет конфигурацию Django (БД, middleware, приложения и др.);
- связывает веб-часть (админку, REST API) с Telegram-ботом через общую БД;
- используется при запуске как через `manage.py`, так и при WSGI-развёртывании.

Примечание:
Файл настроек предназначен для режима разработки (DEBUG=True).
Для продакшена рекомендуется вынести ключи и пароли в переменные окружения.
"""

import os
from pathlib import Path


# ---------------------------------------------------------------------------
# Базовая конфигурация проекта
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "dev-secret-key-change-this"  # заменить для продакшена
DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]


# ---------------------------------------------------------------------------
# Приложения (Django apps)
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    # --- системные приложения Django ---
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # --- кастомные приложения проекта ---
    "calendarapp",   # календарь, события, встречи

    # --- сторонние библиотеки ---
    "rest_framework",  # для будущего REST API
]


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ---------------------------------------------------------------------------
# URL / Templates / WSGI
# ---------------------------------------------------------------------------

ROOT_URLCONF = "webapp.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],  # при необходимости можно добавить путь к шаблонам
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "webapp.wsgi.application"


# ---------------------------------------------------------------------------
# База данных
# ---------------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "calendar_db",
        "USER": "calendar_user",
        "PASSWORD": "calendar_password",
        "HOST": "localhost",
        "PORT": "5432",
    }
}


# ---------------------------------------------------------------------------
# Аутентификация и безопасность
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ---------------------------------------------------------------------------
# Локализация и время
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"

USE_I18N = True
USE_TZ = True  # хранение в UTC, отображение в локальном времени


# ---------------------------------------------------------------------------
# Статика
# ---------------------------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"


# ---------------------------------------------------------------------------
# Прочее
# ---------------------------------------------------------------------------

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
# Экспорт календаря (Task 6)
SITE_BASE_URL = os.getenv("SITE_BASE_URL", "http://127.0.0.1:8000")
# сколько живёт токен выгрузки (секунды) — по умолчанию 15 минут
EXPORT_TOKEN_MAX_AGE = int(os.getenv("EXPORT_TOKEN_MAX_AGE", "900"))
