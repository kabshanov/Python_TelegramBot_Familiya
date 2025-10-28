---

````md
# Проект: Telegram-бот с функцией календаря
# Имя Фамилия — Михаил Кабшанов
# Логин на GitHub — kabshanov
# Telegram - @kabmik

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
* 🗓️ **Встречи между пользователями**: приглашения на события с проверкой занятости, подтверждением/отклонением через инлайн-кнопки, статусами (ожидается/подтверждено/отменено/отклонено).
* 🗄️ **PostgreSQL**: все данные хранятся в реляционной БД (общая для бота и Django).
* 🖥️ **Django Admin**: просмотр событий, встреч и **суточной статистики бота**:
  * `user_count` — новые пользователи за день;
  * `event_count` — созданные события;
  * `edited_events` — отредактированные;
  * `cancelled_events` — удалённые.
* 🔐 **Чистые импорты и безопасность**: токен Telegram хранится в `bot_secrets.py` (в `.gitignore`).
* 🧩 **Модульная архитектура**: логика бота вынесена в пакет `tgapp/` (ядро, FSM, хендлеры).
* 🧰 **Кросс-платформенно**: Windows / macOS / Linux.

---

## Стек технологий

* **Python 3.11–3.13**
* **Django 5.x** (панель администратора, ORM, миграции)
* **python-telegram-bot 13.x** (Updater/Dispatcher API)
* **PostgreSQL 14–16**
* **psycopg2** (подключение к БД из бота)
* **Django REST Framework** (заложено для будущих API)
* **Logging** (базовые логи операций)

---

## Инструменты и документация

**Основные:**
* Python — <https://docs.python.org/3/>
* Django — <https://docs.djangoproject.com/>
* python-telegram-bot (v13) — <https://docs.python-telegram-bot.org/en/v13.15/>
* PostgreSQL — <https://www.postgresql.org/docs/>
* psycopg2 — <https://www.psycopg.org/docs/>

**Базовые веб-понятия (MDN):**
* HTTP — <https://developer.mozilla.org/en-US/docs/Web/HTTP>
* URL — <https://developer.mozilla.org/en-US/docs/Web/API/URL>
* JSON — <https://developer.mozilla.org/en-US/docs/Learn/JavaScript/Objects/JSON>

---

## Требования

**Система**
* Python **3.11+**
* PostgreSQL **14+**
* Доступ в интернет (для Telegram API)
* Свободный порт **8000** (Django dev server)

**Браузеры (для админ-панели)**
* Chrome/Edge/Firefox — **последние версии**
* Safari — **16+**

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
````

### 2) Зависимости

```bash
pip install -r requirements_part2.txt
# при отсутствии файла:
# pip install django==5.* python-telegram-bot==13.13 psycopg2-binary==2.* djangorestframework==3.*
```

### 3) Секреты и БД

1. Создайте `bot_secrets.py` по образцу `secrets_example.py` и добавьте `API_TOKEN`:

   * [`secrets_example.py`](./secrets_example.py)
   * [`bot_secrets.py`](./bot_secrets.py) — **в .gitignore**.

2. Подготовьте PostgreSQL:

```sql
CREATE DATABASE calendar_db;
CREATE USER calendar_user WITH PASSWORD 'strong_password';
GRANT ALL PRIVILEGES ON DATABASE calendar_db TO calendar_user;
```

3. Проверьте единые настройки БД:

   * Django: [`webapp/webapp/settings.py`](./webapp/webapp/settings.py) → `DATABASES`
   * Бот/psycopg2: [`db.py`](./db.py) → `get_connection()`

### 4) Миграции и суперпользователь

```bash
python webapp/manage.py migrate
python webapp/manage.py createsuperuser
```

### 5) Запуск (2 процесса)

**A — Django (админка + healthcheck):**

```bash
python webapp/manage.py runserver
# http://127.0.0.1:8000/ и http://127.0.0.1:8000/admin/
```

**B — Telegram-бот:**

```bash
python bot.py
```

---

## Структура проекта

```text
Python_TelegramBot_Kabshanov/
├─ bot.py                      # точка входа бота: регистрация хендлеров, запуск Updater/Dispatcher
├─ db.py                       # psycopg2: подключение и CRUD для users/events (общая БД с Django)
├─ secrets_example.py          # шаблон секрета
├─ bot_secrets.py              # реальный токен (в .gitignore)
├─ requirements_part2.txt      # зависимости
├─ tgapp/                      # логика бота (модульно)
│  ├─ __init__.py              # описание пакета
│  ├─ core.py                  # общие утилиты, логгер, трекинг, меню команд
│  ├─ fsm.py                   # in-memory FSM (flow/step/data) + парсеры даты/времени
│  ├─ handlers_events.py       # команды и FSM по событиям (create/read/edit/delete)
│  └─ handlers_appointments.py # FSM-приглашение, коллбэки подтверждения/отклонения
├─ webapp/
│  ├─ manage.py                # CLI Django
│  ├─ webapp/
│  │  ├─ __init__.py           # описание пакета проекта
│  │  ├─ settings.py           # настройки (БД, INSTALLED_APPS, middleware, статика)
│  │  ├─ urls.py               # корневые маршруты (/admin, /)
│  │  └─ wsgi.py               # WSGI-точка
│  └─ calendarapp/
│     ├─ __init__.py           # описание пакета приложения
│     ├─ apps.py               # AppConfig (verbose_name, name="calendarapp")
│     ├─ admin.py              # админка: Event, BotStatistics, Appointment
│     ├─ models.py             # Event (managed=False, db_table="events"), BotStatistics, Appointment
│     ├─ utils.py              # занятость/создание встреч (create_pending_invite_for_event и др.)
│     ├─ urls.py               # маршруты приложения ("/" — healthcheck)
│     ├─ views.py              # healthcheck, точка расширения для API
│     └─ migrations/
│        └─ 0001_initial.py    # миграции (BotStatistics, Appointment)
└─ .gitignore                  # исключения (включая bot_secrets.py, .venv, *.sqlite3 и др.)
```

### Описание директорий и ключевых файлов

* [`bot.py`](./bot.py) — сборка и запуск Telegram-бота; регистрация команд и роутера FSM.
* [`db.py`](./db.py) — подключение к PostgreSQL и CRUD для `users`/`events` (общая таблица `events`).
* [`tgapp/core.py`](./tgapp/core.py) — логгер, меню команд, регистрация пользователей, метрики.
* [`tgapp/fsm.py`](./tgapp/fsm.py) — простая FSM (in-memory): `set_state/get_state/clear_state`, `parse_date/parse_time`.
* [`tgapp/handlers_events.py`](./tgapp/handlers_events.py) — /create_event, /display_events, /read_event, /edit_event, /delete_event, /cancel и роутер `text_router` (включая ветку `INVITE`).
* [`tgapp/handlers_appointments.py`](./tgapp/handlers_appointments.py) — FSM-диалог `/invite` и callback-обработка (✅/❌).
* [`webapp/calendarapp/models.py`](./webapp/calendarapp/models.py) — `Event` (читает существующую `events`), `BotStatistics`, `Appointment`.
* [`webapp/calendarapp/utils.py`](./webapp/calendarapp/utils.py) — `get_user_busy_slots`, `is_user_free`, `create_pending_invite_for_event`.
* [`webapp/calendarapp/admin.py`](./webapp/calendarapp/admin.py) — админ-интерфейсы Event/BotStatistics/Appointment.
* [`webapp/webapp/settings.py`](./webapp/webapp/settings.py) — БД/приложения/локаль/статик.
* [`requirements_part2.txt`](./requirements_part2.txt) — зависимости проекта.

---

## Команды бота

* `/register` — регистрация пользователя в БД.
* `/create_event` — диалог: **название → дата (YYYY-MM-DD) → время (HH:MM) → описание**.
* `/display_events` — список событий пользователя.
* `/read_event <id>` — показать событие по ID.
* `/edit_event <id> <новое описание>` — или диалог без аргументов.
* `/delete_event <id>` — или диалог без аргументов.
* `/invite` — **диалог приглашения на встречу**:

  1. TG ID участника → 2) ID вашего события → 3) детали/«Пропустить».
     Бот проверит занятость участника; если свободен — отправит приглашение с кнопками:
     **«✅ Подтвердить»** / **«❌ Отклонить»**. Статус встречи обновится и организатор получит уведомление.
* `/cancel` — отмена текущего диалога (FSM).

---

## Как это работает

1. Пользователь шлёт команду боту → [`bot.py`](./bot.py) маршрутизирует в хендлер (модули `tgapp/*`).
2. **События**:

   * Создание/чтение/редактирование/удаление выполняются через `db.py` (psycopg2) в общей БД.
   * Django читает те же записи через модель `Event (managed=False, db_table="events")`.
3. **Статистика**:

   * Метрики пишутся ботом через Django ORM в модель [`BotStatistics`](./webapp/calendarapp/models.py).
   * Просмотр в админке (раздел «Статистика бота»).
4. **Встречи**:

   * Бот вызывает утилиту [`create_pending_invite_for_event`](./webapp/calendarapp/utils.py), которая через ORM создаёт `Appointment` (статус `pending`) только если участник **свободен**.
   * Участник получает сообщение с инлайн-кнопками. Нажатие меняет статус на `confirmed` или `cancelled`/`declined` и уведомляет организатора.
5. **FSM**:

   * Лёгкая in-memory FSM (`tgapp/fsm.py`): `flow/step/data`. Диалоги `/create_event`, `/invite` и т.п. ведутся по шагам; `Отмена` очищает состояние.

---

## Типичные проблемы и решения

* **`ModuleNotFoundError: No module named 'calendarapp'` при runserver**
  Запускайте из корня:
  `python webapp/manage.py runserver`
  Убедитесь, что `INSTALLED_APPS` содержит `calendarapp`, и в пакетах есть `__init__.py`.

* **`No module named 'webapp.settings'` при запуске бота**
  Запускайте `python bot.py` из **корня**.
  В боте задан `DJANGO_SETTINGS_MODULE="webapp.settings"`; каталог `webapp/` должен быть на `sys.path`.

* **CSRF/логин в админку: `AttributeError: module 'secrets' has no attribute 'choice'`**
  Это конфликт **вашего** файла `secrets.py` с стандартным модулем `secrets`.
  Переименуйте свой файл в `bot_secrets.py` (как в этом проекте) и убедитесь, что `secrets.py` отсутствует в корне.

* **`psycopg2.errors.InsufficientPrivilege` при миграциях**
  Выдайте права пользователю БД: `GRANT ALL PRIVILEGES ON DATABASE ...`, а также на схему/таблицы при необходимости.

* **Приглашение не доставлено участнику**
  Участник мог не начать чат с ботом. В этом случае бот сообщит организатору и пометит встречу как отменённую (чтобы не «висела» в `pending`).

* **В админке пусто в «Событиях»**
  Проверьте, что модель `Event` настроена на существующую таблицу:
  `managed=False`, `db_table="events"`, поле `tg_user_id` → `db_column="user_id"`.

---