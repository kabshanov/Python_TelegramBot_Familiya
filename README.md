---

# Telegram Calendar Bot + Django Admin

Лёгкий календарный Telegram-бот с хранением в PostgreSQL и веб-панелью администратора на Django.
Бот управляет событиями (создание/просмотр/редактирование/удаление) через FSM-диалоги, а админка показывает реальные записи из базы и суточную статистику работы бота.

> Ключевая особенность: **бот пишет события в таблицу `events`**, а Django-модель `Event` **маппится на неё** (`managed=False`, `db_table="events"`). Статистика (`BotStatistics`) хранится и управляется через Django-миграции.

---

## Оглавление

* [Возможности](#возможности)
* [Стек технологий](#стек-технологий)
* [Инструменты и документация](#инструменты-и-документация)
* [Требования](#требования)
* [Установка и запуск](#установка-и-запуск)
* [Структура проекта](#структура-проекта)
* [Описание директорий и ключевых файлов](#описание-директорий-и-ключевых-файлов)
* [Команды бота](#команды-бота)
* [Как это работает](#как-это-работает)
* [Типичные проблемы и решения](#типичные-проблемы-и-решения)

---

## Возможности

* 📲 **Телеграм-бот**: управление личными событиями через команды и пошаговые диалоги (FSM).
* 🗄️ **PostgreSQL**: все данные хранятся в реляционной БД.
* 🖥️ **Django Admin**: просмотр событий пользователей и **суточной статистики бота**:

  * `user_count` — новые пользователи за день;
  * `event_count` — сколько событий создано;
  * `edited_events` — сколько отредактировано;
  * `cancelled_events` — сколько удалено.
* 🔐 **Чистые импорты и безопасность**: токен Telegram хранится в `secrets.py` (в `.gitignore`).
* 🧰 **Кросс-платформенно**: Windows / macOS / Linux.

---

## Стек технологий

* **Python 3.11–3.13**
* **Django 5.x** (панель администратора, ORM для статистики)
* **python-telegram-bot 13.x** (Updater/Dispatcher API)
* **PostgreSQL 14–16**
* **psycopg2** (подключение к БД из бота)
* **Logging** (базовые логи операций)

---

## Инструменты и документация

**Основные:**

* Python — [https://docs.python.org/3/](https://docs.python.org/3/)
* Django — [https://docs.djangoproject.com/](https://docs.djangoproject.com/)
* python-telegram-bot (v13) — [https://docs.python-telegram-bot.org/en/v13.15/](https://docs.python-telegram-bot.org/en/v13.15/)
* PostgreSQL — [https://www.postgresql.org/docs/](https://www.postgresql.org/docs/)
* psycopg2 — [https://www.psycopg.org/docs/](https://www.psycopg.org/docs/)

**Базовые веб-понятия (MDN):**

* HTTP — [https://developer.mozilla.org/en-US/docs/Web/HTTP](https://developer.mozilla.org/en-US/docs/Web/HTTP)
* URL — [https://developer.mozilla.org/en-US/docs/Web/API/URL](https://developer.mozilla.org/en-US/docs/Web/API/URL)
* JSON — [https://developer.mozilla.org/en-US/docs/Learn/JavaScript/Objects/JSON](https://developer.mozilla.org/en-US/docs/Learn/JavaScript/Objects/JSON)

---

## Требования

**Система**

* Python **3.11+**
* PostgreSQL **14+**
* Доступ в интернет (для Telegram API)
* Порт **8000** свободен (для Django dev server)

**Браузеры (для админ-панели)**

* Chrome/Edge/Firefox **последние версии**
* Safari **16+**

---

## Установка и запуск

### 1) Клонирование и окружение

```bash
git clone git@github.com:kabshanov/Python_TelegramBot_Kabshanov.git
cd Python_TelegramBot_Kabshanov
python -m venv .venv
# Windows PowerShell:
. .venv/Scripts/Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
```

### 2) Зависимости

```bash
pip install -r requirements_part2.txt
# (если файла нет — установите:
# pip install django==5.* python-telegram-bot==13.13 psycopg2-binary==2.*)
```

### 3) Настройка секретов и БД

1. Создайте `secrets.py` по образцу `secrets_example.py` и добавьте ваш `API_TOKEN`:

   * [`secrets_example.py`](./secrets_example.py)
   * [`secrets.py`](./secrets.py) — **не коммитится**, уже в `.gitignore`.

2. Создайте БД и пользователя PostgreSQL:

```sql
CREATE DATABASE calendar_db;
CREATE USER calendar_user WITH PASSWORD 'strong_password';
GRANT ALL PRIVILEGES ON DATABASE calendar_db TO calendar_user;
```

3. Убедитесь, что **оба слоя** смотрят в одну и ту же БД:

   * настройки Django: [`webapp/webapp/settings.py`](./webapp/webapp/settings.py) → `DATABASES`
   * подключение бота: [`db.py`](./db.py) → `get_connection()`

### 4) Миграции и суперпользователь (для админки)

```bash
python webapp/manage.py migrate
python webapp/manage.py createsuperuser
```

### 5) Запуск

В двух терминалах, из **корня репозитория**:

**Терминал A — Django admin:**

```bash
python webapp/manage.py runserver
# http://127.0.0.1:8000/  и http://127.0.0.1:8000/admin/
```

**Терминал B — Telegram-бот:**

```bash
python bot.py
```

> Если бот уже работал, откройте Telegram и проверьте команды (см. ниже).

---

## Структура проекта

```text
Python_TelegramBot_Kabshanov/
├─ bot.py                      # логика Telegram-бота (FSM, команды, статистика)
├─ db.py                       # подключение к БД и CRUD-операции для событий/пользователей
├─ secrets_example.py          # пример файла с токеном
├─ secrets.py                  # реальный токен (в .gitignore)
├─ requirements_part2.txt      # зависимости для части 2
├─ README.md                   # этот файл
├─ webapp/
│  ├─ manage.py                # Django-утилиты
│  ├─ webapp/
│  │  ├─ __init__.py
│  │  ├─ settings.py           # БД, INSTALLED_APPS, админка
│  │  ├─ urls.py
│  │  └─ wsgi.py
│  └─ calendarapp/
│     ├─ __init__.py
│     ├─ apps.py               # name="calendarapp"
│     ├─ admin.py              # регистрация Event и BotStatistics в админке
│     ├─ models.py             # Event (db_table=events), BotStatistics (ORM)
│     └─ migrations/
│        └─ 0001_initial.py    # миграции для статистики
└─ .gitignore                  # исключения (включая secrets.py, .venv, *.sqlite3, и т.д.)
```

### Описание директорий и ключевых файлов

* [`bot.py`](./bot.py) — команды `/start`, `/help`, `/register`, `/create_event`, `/display_events`, `/read_event`, `/edit_event`, `/delete_event`, `/cancel` + учёт статистики (через Django ORM).
* [`db.py`](./db.py) — функции подключения к PostgreSQL и CRUD для таблиц `users` и `events`.
* [`webapp/calendarapp/models.py`](./webapp/calendarapp/models.py)

  * `Event`: `managed=False`, `db_table="events"`, поле `tg_user_id` маппится на столбец `user_id`.
  * `BotStatistics`: стандартная Django-модель, хранится в `calendarapp_botstatistics`.
* [`webapp/calendarapp/admin.py`](./webapp/calendarapp/admin.py) — список и фильтры для Event и BotStatistics.
* [`webapp/webapp/settings.py`](./webapp/webapp/settings.py) — настройки проекта и БД.
* [`requirements_part2.txt`](./requirements_part2.txt) — список зависимостей.
* [`secrets_example.py`](./secrets_example.py) → создайте по нему приватный [`secrets.py`](./secrets.py).

---

## Команды бота

* `/register` — регистрация пользователя.
* `/create_event` — диалог: **название → дата(YYYY-MM-DD) → время(HH:MM) → описание**.
* `/display_events` — список событий текущего пользователя.
* `/read_event <id>` — одно событие по ID.
* `/edit_event <id> <новое описание>` или диалоговая версия без аргументов.
* `/delete_event <id>` или диалоговая версия без аргументов.
* `/cancel` — отмена текущего диалога.

---

## Как это работает

1. Пользователь шлёт команду в бота → [`bot.py`](./bot.py) обрабатывает через FSM.
2. Бот пишет/читает данные напрямую из PostgreSQL через [`db.py`](./db.py).
   Таблица событий — **`events`** (общая с админкой).
3. Для статистики бот использует Django ORM и модель [`BotStatistics`](./webapp/calendarapp/models.py).
   Записи появляются в админке (раздел **«Статистика бота»**).
4. Django-модель [`Event`](./webapp/calendarapp/models.py) привязана к **существующей таблице `events`** (`managed=False`),
   поэтому раздел **«События»** показывает **реальные записи**, созданные через бота.

---

## Типичные проблемы и решения

* **`ModuleNotFoundError: No module named 'calendarapp'` при runserver**
  Запускайте из корня:
  `python webapp/manage.py runserver`
  Убедитесь, что в `INSTALLED_APPS` указан `calendarapp`, а в `apps.py` — `name="calendarapp"` и есть `__init__.py` в пакетах.

* **`No module named 'webapp.settings'` при запуске бота**
  Запускайте `python bot.py` из **корня** репозитория.
  В коде бота установлено `DJANGO_SETTINGS_MODULE="webapp.settings"`; путь `webapp/` должен быть видим.
  (В боте добавлен безопасный `sys.path`-хук на папку `webapp/`.)

* **`psycopg2.errors.InsufficientPrivilege` при миграциях**
  Выдайте привилегии пользователю БД (`GRANT ALL PRIVILEGES ON DATABASE ...`),
  и на схему/таблицы при необходимости.

* **Пусто в админке «События»**
  Убедитесь, что `Event` в [`models.py`](./webapp/calendarapp/models.py) имеет:
  `managed=False`, `db_table="events"`, а поле `tg_user_id` — `db_column="user_id"`.

---

