````md
# Проект: Telegram-бот с функцией календаря
**Автор:** Михаил Кабшанов  
**GitHub:** kabshanov  
**Telegram:** @kabmik

---

## Оглавление

- [Возможности](#возможности)
- [Стек технологий](#стек-технологий)
- [Инструменты и документация](#инструменты-и-документация)
- [Требования](#требования)
- [Установка и запуск](#установка-и-запуск)
- [Структура проекта](#структура-проекта)
- [Описание директорий и ключевых файлов](#описание-директорий-и-ключевых-файлов)
- [Команды бота](#команды-бота)
- [Как это работает](#как-это-работает)
- [Модели данных и права доступа](#модели-данных-и-права-доступа)
- [Типичные проблемы и решения](#типичные-проблемы-и-решения)
- [План развития](#план-развития)

---

## Возможности

- 📲 **Телеграм-бот**: создание/просмотр/редактирование/удаление событий через команды и диалоги FSM.
- 👥 **Личные кабинеты пользователей (TgUser)**:
  - Привязка Telegram-аккаунта к системе (`/login`);
  - Личный календарь из ORM (`/calendar`);
  - В админке Django — карточка пользователя с его событиями и счётчиками активности.
- 🤝 **Назначение встреч (Appointment)**:
  - Приглашение участника на своё событие (диалог `/invite`);
  - Проверка занятости участника; статусы `pending/confirmed/declined/cancelled`;
  - Нотификации организатору и участнику (инлайн-кнопки «✅/❌»).
- 🗄️ **Единая БД PostgreSQL** для бота и Django:
  - Таблица `events` — общая; Django-модель `Event` читает её (managed=False);
  - Системные модели Django: `BotStatistics`, `Appointment`, `TgUser`.
- 📈 **Статистика**:
  - Суточные метрики бота (`BotStatistics`): создано/отредактировано/отменено, новые пользователи;
  - Персональные счётчики в `TgUser`: сколько создал/исправил/отменил.
- 🧩 **Модульная архитектура**:
  - Пакет `tgapp/` (ядро, FSM, обработчики событий и приглашений);
  - Чистые аннотации типов и комментарии в стиле PEP 8.
- 🔐 **Права доступа**: пользователь управляет **только своими** событиями (проверка владельца на каждом действии).

---

## Стек технологий

- Python 3.11–3.13
- Django 5.x (админка, ORM, миграции)
- python-telegram-bot 13.x (Updater/Dispatcher API)
- PostgreSQL 14–16
- psycopg2 / psycopg2-binary
- Django REST Framework (заложено для будущих API)
- logging (базовая телеметрия)

---

## Инструменты и документация

**Core:**
- Python — https://docs.python.org/3/
- Django — https://docs.djangoproject.com/
- python-telegram-bot v13 — https://docs.python-telegram-bot.org/en/v13.15/
- PostgreSQL — https://www.postgresql.org/docs/
- psycopg2 — https://www.psycopg.org/docs/

**Базовые веб-понятия (MDN):**
- HTTP — https://developer.mozilla.org/en-US/docs/Web/HTTP
- URL — https://developer.mozilla.org/en-US/docs/Web/API/URL
- JSON — https://developer.mozilla.org/en-US/docs/Learn/JavaScript/Objects/JSON

---

## Требования

**Система**
- Python **3.11+**
- PostgreSQL **14+**
- Доступ в интернет (Telegram Bot API)
- Порт **8000** свободен (Django dev server)

**Браузеры (админ-панель)**
- Chrome/Edge/Firefox — последние версии
- Safari — 16+

---

## Установка и запуск

### 1) Клонирование и виртуальное окружение

```bash
git clone git@github.com:kabshanov/Python_TelegramBot_Kabshanov.git
cd Python_TelegramBot_Kabshanov
python -m venv .venv
# Windows PowerShell
. .venv/Scripts/Activate.ps1
# macOS/Linux
# source .venv/bin/activate
````

### 2) Зависимости

```bash
pip install -r requirements_part2.txt
# при необходимости:
# pip install "django==5.*" "python-telegram-bot==13.13" "psycopg2-binary==2.*" "djangorestframework==3.*"
```

### 3) Секреты и настройки БД

1. Создайте `bot_secrets.py` (в `.gitignore`) по образцу:

   * [`secrets_example.py`](./secrets_example.py) → скопируйте и задайте `API_TOKEN`.

2. Поднимите PostgreSQL и права:

```sql
CREATE DATABASE calendar_db;
CREATE USER calendar_user WITH PASSWORD 'strong_password';
GRANT ALL PRIVILEGES ON DATABASE calendar_db TO calendar_user;
```

3. Проверьте, что в обоих местах одна и та же БД:

   * Django: [`webapp/webapp/settings.py`](./webapp/webapp/settings.py) → `DATABASES`
   * Бот: [`db.py`](./db.py) → `get_connection()`

### 4) Миграции и суперпользователь

```bash
python webapp/manage.py migrate
python webapp/manage.py createsuperuser
```

### 5) Запуск (два процесса)

**A — Django:**

```bash
python webapp/manage.py runserver
# http://127.0.0.1:8000/  и  http://127.0.0.1:8000/admin/
```

**B — Бот:**

```bash
python bot.py
```

---

## Структура проекта

```text
Python_TelegramBot_Kabshanov/
├─ bot.py                      # точка входа бота, регистрация команд и FSM-роутера
├─ db.py                       # psycopg2-CRUD для users/events (общая БД с Django)
├─ secrets_example.py          # шаблон секретов
├─ bot_secrets.py              # реальный токен (в .gitignore)
├─ requirements_part2.txt      # зависимости
├─ tgapp/                      # логика бота (модульно)
│  ├─ __init__.py              # краткое описание пакета
│  ├─ core.py                  # логгер, меню команд, регистрация, трекинг метрик и счётчиков
│  ├─ fsm.py                   # простая in-memory FSM (flow/step/data) + парсеры даты/времени
│  ├─ handlers_events.py       # CRUD событий, /login, /calendar, текстовый роутер (включая INVITE)
│  └─ handlers_appointments.py # FSM приглашений и callback-логика подтверждений
├─ webapp/
│  ├─ manage.py                # CLI Django
│  ├─ webapp/
│  │  ├─ __init__.py
│  │  ├─ settings.py           # INSTALLED_APPS, БД, локаль/таймзона, статика
│  │  ├─ urls.py               # корневые маршруты (/admin, /)
│  │  └─ wsgi.py
│  └─ calendarapp/
│     ├─ __init__.py
│     ├─ apps.py               # AppConfig (verbose_name, name="calendarapp")
│     ├─ admin.py              # админка: Event, TgUser, Appointment, BotStatistics
│     ├─ models.py             # Event(managed=False), TgUser, Appointment, BotStatistics
│     ├─ utils.py              # занятость/слоты и создание встреч
│     ├─ urls.py               # healthcheck
│     ├─ views.py              # healthcheck / точка расширения (API)
│     └─ migrations/           # миграции приложений (кроме таблицы events)
└─ .gitignore                  # исключения (включая .venv, *.sqlite3, bot_secrets.py, *.md рабочие)
```

---

## Описание директорий и ключевых файлов

* [`bot.py`](./bot.py) — инициализация Django-окружения, запуск `Updater/Dispatcher`, регистрация команд и роутера.
* [`db.py`](./db.py) — подключение к PostgreSQL и CRUD `users/events` (используется ботом напрямую).
* [`tgapp/core.py`](./tgapp/core.py) — общие утилиты: логгер, меню команд, регистрация пользователя, трекинг метрик/счётчиков, доступ к `CALENDAR`.
* [`tgapp/fsm.py`](./tgapp/fsm.py) — in-memory FSM: `set_state/get_state/clear_state`, `parse_date/parse_time`.
* [`tgapp/handlers_events.py`](./tgapp/handlers_events.py) — команды: `/start /help /register /login /calendar /create_event /display_events /read_event /edit_event /delete_event /cancel` + роутер текстов (ветка `INVITE`).
* [`tgapp/handlers_appointments.py`](./tgapp/handlers_appointments.py) — диалог `/invite` и callback-обработка статусов встреч.
* [`webapp/calendarapp/models.py`](./webapp/calendarapp/models.py) — `Event` (читает общую таблицу `events`), `TgUser`, `Appointment`, `BotStatistics`.
* [`webapp/calendarapp/admin.py`](./webapp/calendarapp/admin.py) — удобные админ-интерфейсы: инлайн-события у пользователя, счётчики, фильтры, поиск.
* [`webapp/calendarapp/utils.py`](./webapp/calendarapp/utils.py) — слоты занятости, проверка доступности, создание приглашений.
* [`webapp/webapp/settings.py`](./webapp/webapp/settings.py) — настройки Django и подключения к БД.

---

## Команды бота

* `/start`, `/help` — краткая справка.
* `/register` — регистрация в базе (таблица `users`) и синхронизация карточки `TgUser`.
* `/login` — привязка текущего Telegram-аккаунта к `TgUser` (создание/обновление профиля).
* `/calendar` — показать личный календарь (данные из ORM по `tg_user_id`).
* `/create_event` — диалог: **название → дата YYYY-MM-DD → время HH:MM → описание**.
* `/display_events` — список моих событий (через `db.py`).
* `/read_event <id>` — показать моё событие по ID.
* `/edit_event [<id> <новый текст>]` — inline или диалог изменения описания.
* `/delete_event [<id>]` — inline или диалог удаления.
* `/invite` — диалог приглашения на встречу:

  1. TG ID участника → 2) ID вашего события → 3) детали/«Пропустить».
     Бот проверит занятость и, если свободен, создаст `pending` встречу и отправит участнику инлайн-кнопки.
* `/cancel` — отмена текущего диалога (FSM).

> Все операции **строго по владельцу**: редактировать/удалять можно только собственные события.

---

## Как это работает

1. **Единая БД**
   Бот пишет/читает `events` через `db.py` (psycopg2). Django читает те же строки через модель `Event (managed=False, db_table="events")`.

2. **Личные кабинеты (TgUser)**
   `/login` создаёт/обновляет `TgUser`.
   В админке видны: TG ID/username/имя/фамилия, флаг активности, счётчики и **инлайн-список событий** пользователя.

3. **Права доступа**
   На каждой операции с событием проверяется, что `tg_user_id` события совпадает с автором запроса.

4. **Встречи (Appointment)**
   `/invite` запускает FSM: бот проверяет, не занят ли участник в дату/время исходного события (через ORM и `utils.is_user_free`).
   Если свободен — создаётся `Appointment (pending)`, участнику летит уведомление с «✅/❌».
   Нажатие меняет статус на `confirmed/declined/cancelled` и уведомляет организатора.

5. **Статистика**

   * Глобальная (`BotStatistics`) — апдейты на создании/редактировании/удалении.
   * Персональная (`TgUser`) — счётчики `created_total/edited_total/cancelled_total`.

6. **FSM**
   Лёгкое in-memory состояние: `flow/step/data` с утилитами `set_state/get_state/clear_state`.
   Поддерживаются диалоги `CREATE`, `EDIT`, `DELETE`, `INVITE`. Универсальная «Отмена».

---

## Модели данных и права доступа

* **Event** (`managed=False`, `db_table="events"`):

  * `id`, `name`, `date`, `time`, `details`, `tg_user_id (db_column="user_id")`.
  * Владение событием — по `tg_user_id`. Только владелец может читать/менять/удалять.

* **TgUser**:

  * `tg_id`, `username`, `first_name`, `last_name`, `is_active`;
  * персональные счётчики: `created_total`, `edited_total`, `cancelled_total`;
  * related-inline со списком событий в админке.

* **Appointment**:

  * `event` (FK без DB-constraint к `Event`), `organizer_tg_id`, `participant_tg_id`,
  * `date`, `time`, `details`,
  * `status`: `pending | confirmed | declined | cancelled`.

* **BotStatistics**:

  * `date (unique)`, `user_count`, `event_count`, `edited_events`, `cancelled_events`.

---

## Типичные проблемы и решения

* **Запуск бота: `No module named 'webapp.settings'`**
  Запускайте `python bot.py` из корня репозитория. Бот сам настраивает `DJANGO_SETTINGS_MODULE="webapp.settings"`.

* **Запуск админки: `ModuleNotFoundError: 'calendarapp'`**
  Запускайте: `python webapp/manage.py runserver` из **корня**. Проверьте, что `calendarapp` в `INSTALLED_APPS`, и есть `__init__.py`.

* **CSRF / `module 'secrets' has no attribute 'choice'`**
  В корне не должно быть вашего `secrets.py` (конфликт с стандартным модулем). Используйте `bot_secrets.py`.

* **Миграции: `psycopg2.errors.InsufficientPrivilege`**
  Выдайте права пользователю БД и/или на схему: `GRANT ALL ON DATABASE/SCHEMA/TABLES`.

* **Событие «не найдено», хотя ID существует**
  Вы проверяете чужое событие. Бот не позволит читать/менять/удалять не своё.
  Используйте `/display_events` или `/calendar`, чтобы увидеть **свои** ID.

* **Приглашение не доходит**
  Участник не начинал чат с ботом. На стороне Telegram нельзя отправить личное сообщение, пока пользователь сам не нажмёт «Start». Сообщите участнику об этом.

---

## План развития

* Пользовательская веб-страница «Мой календарь» (вне админки) — через DRF + мини-frontend.
* Умные напоминания о встречах (APS/cron).
* Экспорт/импорт iCal/ICS.
* Теги/категории для событий.
* Покрытие unit-тестами ключевых модулей (`tgapp/*`, `calendarapp/utils.py`).

---