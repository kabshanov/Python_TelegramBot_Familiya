````md
# Проект: Telegram-бот с функцией календаря (бот + Django)

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
  - [Единая БД](#единая-бд)
  - [Личные кабинеты (TgUser)](#личные-кабинеты-tguser)
  - [Доступ и права](#доступ-и-права)
  - [Встречи (Appointment)](#встречи-appointment)
  - [Публичные события](#публичные-события)
  - [Экспорт CSV/JSON](#экспорт-csvjson)
  - [FSM (диалоги)](#fsm-диалоги)
- [Модели данных](#модели-данных)
- [Админ-панель](#админ-панель)
- [Типичные проблемы и решения](#типичные-проблемы-и-решения)
- [План развития](#план-развития)
- [Лицензия](#лицензия)

---

## Возможности

- 📲 **Телеграм-бот**: создание, просмотр, редактирование и удаление событий. Диалоговые сценарии через FSM.
- 👤 **Личные кабинеты**: привязка Telegram-аккаунта к Django-профилю (`/login`), просмотр личного календаря (`/calendar`).
- 🤝 **Встречи (Appointment)**: приглашение в один клик, статусы `pending / confirmed / declined / cancelled`, уведомления с инлайн-кнопками.
- 🌐 **Публичные события**: владелец может пометить событие как публичное и делиться ссылкой; другие пользователи видят список через бот.
- ⬇️ **Экспорт**: выгрузка своих событий в **CSV** и **JSON** по безопасной ссылке (подпись+TTL), кнопки появляются внутри `/calendar`.
- 📈 **Статистика**: суточные метрики (`BotStatistics`) и персональные счётчики действий в карточке `TgUser`.
- 🧩 **Модульная архитектура**: логика бота отдельно (`tgapp/`), Django-часть с ORM и эндпоинтами отдельно (`webapp/`).

---

## Стек технологий

- **Python** 3.11–3.13
- **Django** 5.x (админка, ORM, миграции)
- **python-telegram-bot** 13.x (Updater/Dispatcher API)
- **PostgreSQL** 14–16
- **psycopg2 / psycopg2-binary**
- **Django REST Framework** (заложено под API)
- **logging** (единый стиль логов)

---

## Инструменты и документация

- Python — https://docs.python.org/3/
- Django — https://docs.djangoproject.com/
- python-telegram-bot v13 — https://docs.python-telegram-bot.org/en/v13.15/
- PostgreSQL — https://www.postgresql.org/docs/
- psycopg2 — https://www.psycopg.org/docs/

MDN (базовые веб-понятия):
- HTTP — https://developer.mozilla.org/en-US/docs/Web/HTTP
- URL — https://developer.mozilla.org/en-US/docs/Web/API/URL
- JSON — https://developer.mozilla.org/en-US/docs/Learn/JavaScript/Objects/JSON

---

## Требования

**Система**
- Python **3.11+**
- PostgreSQL **14+**
- Свободный порт **8000** (Django dev server)
- Доступ в интернет (Telegram Bot API)

**Браузеры для админки**
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
# на всякий:
# pip install "django==5.*" "python-telegram-bot==13.13" "psycopg2-binary==2.*" "djangorestframework==3.*"
```

### 3) Секреты и БД

1. Скопируйте `secrets_example.py` → `bot_secrets.py` и задайте `API_TOKEN`.
2. Поднимите PostgreSQL и создайте пользователя/БД:

   ```sql
   CREATE DATABASE calendar_db;
   CREATE USER calendar_user WITH PASSWORD 'strong_password';
   GRANT ALL PRIVILEGES ON DATABASE calendar_db TO calendar_user;
   ```
3. Проверьте единые настройки подключения:

   * Django: [`webapp/webapp/settings.py`](webapp/webapp/settings.py) → `DATABASES`
   * Бот: [`db.py`](db.py) → `get_connection()`

### 4) Миграции и суперпользователь

```bash
python webapp/manage.py migrate
python webapp/manage.py createsuperuser
```

### 5) Настройки экспорта (рекомендуется)

В `webapp/webapp/settings.py`:

```python
EXPORT_TOKEN_MAX_AGE = 900  # 15 минут
```

### 6) Запуск (две консоли)

**A — Django:**

```bash
python webapp/manage.py runserver
# http://127.0.0.1:8000/  и  http://127.0.0.1:8000/admin/
```

**B — Бот:**

```bash
python bot.py
```

> При старте бот проверит и при необходимости добавит колонку `events.is_public` (безопасно для повторных запусков).

---

## Структура проекта

```text
Python_TelegramBot_Kabshanov/
├─ bot.py                      # точка входа бота: меню, хендлеры, FSM-роутер, запуск
├─ db.py                       # psycopg2-CRUD для users/events, ensure_is_public_column()
├─ secrets_example.py          # пример секретов
├─ bot_secrets.py              # реальные секреты (в .gitignore)
├─ requirements_part2.txt      # зависимости
├─ tgapp/
│  ├─ __init__.py              # краткое описание пакета (для IDE и читателя)
│  ├─ core.py                  # логгер, меню команд, регистрация, счётчики
│  ├─ fsm.py                   # простая in-memory FSM (flow/step/data), парсеры даты/времени
│  ├─ handlers_events.py       # CRUD событий, /login, /calendar, шёринг, экспорт (кнопки), роутер
│  └─ handlers_appointments.py # приглашения на встречи, инлайн-кнопки, статусы
├─ webapp/
│  ├─ manage.py                # CLI Django
│  ├─ webapp/
│  │  ├─ __init__.py
│  │  ├─ settings.py           # INSTALLED_APPS, БД, локаль/таймзона, EXPORT_TOKEN_MAX_AGE
│  │  ├─ urls.py               # корневые маршруты (/admin, /)
│  │  └─ wsgi.py
│  └─ calendarapp/
│     ├─ __init__.py
│     ├─ apps.py               # AppConfig, verbose_name
│     ├─ admin.py              # удобная админка: инлайны, фильтры, счётчики
│     ├─ models.py             # Event(managed=False), TgUser, Appointment, BotStatistics
│     ├─ utils.py              # занятость, слоты, создание инвайта, токены экспорта
│     ├─ urls.py               # healthcheck, export/<fmt> (csv|json)
│     ├─ views.py              # экспорт CSV/JSON по токену, healthcheck
│     └─ migrations/
└─ .gitignore
```

---

## Описание директорий и ключевых файлов

* `bot.py` — собирает и запускает Telegram-бот: регистрирует команды, FSM-обработчики, кнопки экспорта; инициализирует Django-окружение.
* `db.py` — низкоуровневый доступ к `users`/`events` (psycopg2), без ORM. Содержит `ensure_is_public_column()` для Task 5.
* `tgapp/core.py` — общее: логирование, меню команд, регистрация/привязка пользователя, обновление счётчиков в `TgUser`/`BotStatistics`.
* `tgapp/fsm.py` — in-memory FSM: `set_state/get_state/clear_state`, парсеры `parse_date/parse_time`, клавиатуры отмены.
* `tgapp/handlers_events.py` — команды `/start /help /register /login /calendar /create_event /display_events /read_event /edit_event /delete_event /share_event /my_public /public_of /export /cancel`, inline и диалоговые ветки, кнопки экспорта.
* `tgapp/handlers_appointments.py` — диалог `/invite`, инлайн-кнопки подтверждения/отклонения, уведомления, статусы.
* `webapp/calendarapp/models.py` — `Event (managed=False, db_table="events")`, `TgUser`, `Appointment`, `BotStatistics`.
* `webapp/calendarapp/utils.py` — слоты занятости, проверка свободности, создание инвайта, подпись/проверка экспортного токена, сбор данных для экспорта.
* `webapp/calendarapp/urls.py` — `"" → healthcheck`, `"export/<str:fmt>/" → export_events`.
* `webapp/calendarapp/views.py` — `export_events` (CSV/JSON): проверяет подпись/TTL токена, отдаёт файл; `healthcheck`.

---

## Команды бота

**Справка/профиль**

* `/start`, `/help` — краткая справка.
* `/register` — регистрация в `users` и синхронизация с `TgUser`.
* `/login` — привязать текущий Telegram-аккаунт к `TgUser`.
* `/calendar` — показать личный календарь и **кнопки экспорта** (CSV/JSON).

**События**

* `/create_event` — диалог: *название → дата (YYYY-MM-DD) → время (HH:MM) → описание*.
* `/display_events` — список моих событий (через `db.py`).
* `/read_event <id>` — показать моё событие.
* `/edit_event [<id> <новое описание>]` — либо диалог, либо сразу.
* `/delete_event [<id>]` — диалог или сразу.

**Публичные события**

* `/share_event` — сделать своё событие публичным (диалог, с проверкой владельца).
* `/my_public` — мои публичные события.
* `/public_of` — публичные события другого пользователя.

**Встречи**

* `/invite` — пригласить участника на своё событие (проверка занятости, инлайн-подтверждение).

**Служебное**

* `/cancel` — отменить текущий диалог.

> Любые операции со **своими** событиями: чужие редактировать/удалять нельзя.

---

## Как это работает

### Единая БД

* Бот пишет/читает таблицу `events` напрямую через `db.py` (psycopg2).
* Django читает те же строки моделью `Event` (`managed=False`, `db_table="events"`).
* Так достигается совместимость и отсутствие двойной миграции этой таблицы.

### Личные кабинеты (TgUser)

* `/login` создаёт/обновляет профиль `TgUser` (tg_id, username, имя/фамилия, активность).
* В админке у пользователя виден **инлайн-список событий** и персональные счётчики действий.

### Доступ и права

* Владелец события — `tg_user_id` (столбец `user_id` в `events`).
* Проверка владельца встроена в команды чтения/редактирования/удаления.

### Встречи (Appointment)

* `/invite` запускает FSM: TG ID участника → ID события (вашего) → комментарий.
* Проверяется занятость участника на дату/время события; если свободен — создаётся `pending` встреча и отправляется приглашение.
* Нажатие кнопок меняет статус, организатор уведомляется.

### Публичные события

* Команда `/share_event` помечает выбранное событие флагом `is_public=True`.
* `/my_public` — список только ваших публичных событий.
* `/public_of` — список публичных событий по TG ID другого пользователя.
* Внутри интерфейс адаптирован под пользователя (без «is_public=True» в тексте).

### Экспорт CSV/JSON

* В `/calendar` бот формирует **кнопки с URL** на эндпоинт Django:

  * `/export/csv/?token=...`
  * `/export/json/?token=...`
* Токен содержит `tg_user_id`, подписан `django.core.signing` и ограничен по времени (`EXPORT_TOKEN_MAX_AGE`, по умолчанию 900 с).
* Доступ по токену позволяет скачать **только свои** события.
* **CSV**: заголовки `id,name,date,time,details,tg_user_id`.
* **JSON**: читаемый (UTF-8, `ensure_ascii=False`, `indent=2`).

### FSM (диалоги)

* Простая in-memory FSM с шагами `flow/step/data` и универсальной отменой.
* Диалоги: `CREATE`, `EDIT`, `DELETE`, `INVITE`, (ветка публикации внутри событий).
* Логи помогают отлавливать десинхронизацию шагов.

---

## Модели данных

**Event** (`managed=False`, `db_table="events"`)

* `id`, `name`, `date`, `time`, `details`, `tg_user_id` (db_column=`user_id`), `is_public` (bool).
* Владение — по `tg_user_id`. Только владелец управляет.

**TgUser**

* `tg_id`, `username`, `first_name`, `last_name`, `is_active`
* Счётчики: `created_total`, `edited_total`, `cancelled_total`
* Инлайн-события в админке (для быстрого обзора).

**Appointment**

* `event` (FK без DB-constraint к `Event`), `organizer_tg_id`, `participant_tg_id`
* `date`, `time`, `details`, `status` (`pending|confirmed|declined|cancelled`)
* Валидация занятости вынесена в утилиты.

**BotStatistics**

* `date (unique)`, `user_count`, `event_count`, `edited_events`, `cancelled_events`
* Актуализируется при действиях в боте.

---

## Админ-панель

* Разделы: **Пользователи TG (TgUser)**, **События (Event)**, **Встречи (Appointment)**, **Статистика бота (BotStatistics)**.
* Удобные списки, фильтры и поиск.
* В карточке пользователя — инлайн-события и счётчики.
* История изменений доступна в стандартных местах админки.

---

## Типичные проблемы и решения

* **`ModuleNotFoundError: 'webapp.settings'` при запуске бота**
  Запускайте `python bot.py` из корня репозитория (он сам выставляет `DJANGO_SETTINGS_MODULE`).

* **`ModuleNotFoundError: 'calendarapp'` при запуске сервера**
  `python webapp/manage.py runserver` — тоже из корня. Проверьте `INSTALLED_APPS` и наличие `__init__.py` в пакетах.

* **CSRF/`module 'secrets' has no attribute 'choice'`**
  В корне не должно быть файла `secrets.py` (конфликт с стандартной библиотекой). Используйте `bot_secrets.py`.

* **Недостаточно прав на схему/таблицы**
  Выдайте права пользователю БД на базу/схему/таблицы. Для общей таблицы `events` у Django `managed=False`, миграций не будет.

* **Приглашение не доставляется**
  Участник ещё не писал боту — Telegram не даст отправить личное сообщение. Попросите участника нажать **Start** в боте.

---

## План развития

* Пользовательский веб-интерфейс «Мой календарь» (вне админки) на DRF + минимальный фронт.
* Напоминания за N минут до события (APS/cron).
* iCal/ICS экспорт/импорт.
* Метки/категории событий.
* Unit-тесты на ключевые сценарии.

---

## Лицензия

MIT (по умолчанию). При необходимости можно добавить кастомные условия в `LICENSE`.

```