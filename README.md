---

# Проект: Telegram-бот календаря + Django (админка, API, экспорт)

**Автор:** Михаил Кабшанов
**GitHub:** kabshanov
**Telegram:** @kabmik

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
* [API (DRF)](#api-drf)
* [Экспорт событий (CSV/JSON)](#экспорт-событий-csvjson)
* [Автоматические тесты](#автоматические-тесты)
* [Модели данных](#модели-данных)
* [Админ-панель](#админ-панель)
* [Типичные проблемы и решения](#типичные-проблемы-и-решения)
* [План развития](#план-развития)
* [Лицензия](#лицензия)

---

## Возможности

* 📲 **Телеграм-бот**: создание / просмотр / редактирование / удаление событий через диалоги (FSM) и простые команды.
* 👤 **Пользователи (TgUser)**: учёт Telegram-профилей, базовые счётчики активности.
* 🤝 **Встречи (Appointment)**: приглашения между пользователями и статусы (`pending/confirmed/cancelled/declined`).
* 🌐 **Публичность**: событие можно “опубликовать” и делиться ссылкой.
* ⬇️ **Экспорт CSV/JSON**: безопасная выгрузка событий через Django-эндпоинты с защитным токеном.
* ⚙️ **REST API (DRF)**: интеграция с внешними системами (списки/детали/создание/обновление объектов).
* 🧪 **Автотесты**: `pytest` + `pytest-django` закрывают критические узлы (модели, экспорт, команды бота).
* 📈 **Статистика**: агрегаты по активности за сутки.

---

## Стек технологий

* **Python 3.11–3.13**
* **Django 5.x**
* **Django REST Framework 3.x**
* **python-telegram-bot 13.x**
* **PostgreSQL 14–16**, `psycopg2`
* **pytest**, `pytest-django`, `pytest-sugar`, `pytest-rich`

---

## Инструменты и документация

* Django: [https://docs.djangoproject.com/](https://docs.djangoproject.com/)
* DRF: [https://www.django-rest-framework.org/](https://www.django-rest-framework.org/)
* python-telegram-bot (v13): [https://docs.python-telegram-bot.org/en/v13.15/](https://docs.python-telegram-bot.org/en/v13.15/)
* PostgreSQL: [https://www.postgresql.org/docs/](https://www.postgresql.org/docs/)

---

## Требования

* Python 3.11+
* PostgreSQL (локально или в контейнере)
* Созданная БД и пользователь с правами на создание тестовой БД (см. ниже)

---

## Установка и запуск

1. **Клонирование и окружение**

```bash
git clone <repo-url>
cd Python_TelegramBot_Familiya
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

2. **Переменные и секреты**

* Телеграм-токен: либо создать `bot_secrets.py` в корне:

  ```python
  API_TOKEN = "<YOUR_TELEGRAM_BOT_TOKEN>"
  ```

  либо в окружении:

  ```bash
  set TELEGRAM_BOT_TOKEN=<YOUR_TELEGRAM_BOT_TOKEN>
  ```

3. **PostgreSQL**

Создайте БД и пользователя (пример):

```sql
-- psql -U postgres
CREATE USER calendar_user WITH PASSWORD 'calendar_password';
ALTER USER calendar_user CREATEDB;               -- нужно для автосоздания тестовой БД
CREATE DATABASE calendar_db OWNER calendar_user;
GRANT ALL PRIVILEGES ON DATABASE calendar_db TO calendar_user;
```

Параметры подключения берутся из Django `webapp/settings.py` (DATABASES).

4. **Миграции и запуск Django**

```bash
cd webapp
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Django доступен на `http://127.0.0.1:8000/`
Админка: `http://127.0.0.1:8000/admin/`

5. **Запуск бота**

```bash
cd ..
python bot.py
```

---

## Структура проекта

```text
Python_TelegramBot_Familiya/
├─ bot.py                       # точка входа Telegram-бота
├─ bot_secrets.py               # (локально) TELEGRAM API_TOKEN
├─ db.py                        # низкоуровневые операции (psycopg2), Calendar и т.п.
├─ tgapp/
│  ├─ core.py                   # общие хелперы для tg-уровня
│  ├─ fsm.py                    # состояния диалогов
│  ├─ handlers_events.py        # команды бота (события, публичность, экспорт, справка)
│  └─ handlers_appointments.py  # команды бота по встречам
├─ webapp/
│  ├─ manage.py
│  ├─ webapp/
│  │  ├─ settings.py            # Django-настройки (DRF в INSTALLED_APPS)
│  │  ├─ urls.py                # корневые URL, подключение calendarapp.urls
│  │  └─ __init__.py
│  └─ calendarapp/
│     ├─ admin.py
│     ├─ apps.py
│     ├─ models.py              # TgUser (ORM), Event (managed=False), Appointment, BotStatistics
│     ├─ utils.py               # экспорт, токены, выборки
│     ├─ views.py               # /export/json, /export/csv
│     ├─ serializers.py         # DRF-сериализаторы
│     ├─ api_views.py           # DRF ViewSet-ы/Generic Views
│     ├─ urls.py                # /export/* и /api/* маршруты
│     └─ __init__.py
├─ tests/
│  ├─ conftest.py               # фикстуры: тестовая таблица events, фабрика make_event и т.д.
│  ├─ test_export_views.py      # проверки /export/json и /export/csv
│  ├─ test_handlers_events.py   # базовые команды бота (/start, /help)
│  └─ test_models.py            # модели: TgUser, Appointment, BotStatistics
├─ README.md
├─ README_BOT.md
├─ README_DJANGO.md
└─ pytest.ini                   # конфигурация pytest/pytest-django
```

---

## Описание директорий и ключевых файлов

* **bot.py** — инициализация Django-контекста для бота, регистрация хендлеров, запуск `Updater/Dispatcher`.
* **tgapp/*** — уровень Telegram: FSM, команды, тексты, логика кнопок/ссылок (в т.ч. `/export`).
* **db.py** — соединение с PostgreSQL, класс `Calendar` (создание/чтение/обновление событий), прочие утилиты.
* **webapp/calendarapp/models.py**

  * `TgUser` — пользователи TG (ORM) с `tg_id` (PK).
  * `Event` — события (таблица создаётся ботом через psycopg2, `managed=False`).
  * `Appointment`, `BotStatistics` — обычные ORM-модели.
* **webapp/calendarapp/views.py** — экспорт JSON/CSV c проверкой подписи токена.
* **webapp/calendarapp/serializers.py**, **api_views.py**, **urls.py** — DRF API.
* **tests/** — минимальный набор тестов, закрывающий критические узлы проекта.

---

## Команды бота

* `/start`, `/help` — справка и меню.
* `/register` — регистрация/привязка TG-профиля.
* `/create_event`, `/display_events`, `/read_event <id>`, `/edit_event [<id> <текст>]`, `/delete_event [<id>]` — операции с событиями.
* `/share_event` — отметить событие публичным.
* `/my_public` — список публичных событий пользователя.
* `/public_of` — публичные события другого пользователя.
* `/invite` — создать приглашение на встречу.
* `/login` — привязка аккаунта.
* `/calendar` — показать личный календарь.
* `/export` — получить кнопки со ссылками для выгрузки CSV/JSON.

---

## Как это работает

* Бот пишет события напрямую в БД (через `db.py` / `psycopg2`).
* Django читает те же таблицы (модель `Event` описана как `managed=False`) и отдаёт админку/экспорт/API.
* Экспорт защищён одноразовым токеном (подпись + TTL).
* DRF даёт стандартный REST-доступ для внешней интеграции.

---

## API (DRF)

**Подключение:** `webapp/calendarapp/urls.py` включает DRF-маршруты под `/api/`.

**Основные точки:**

|  Метод | URL                   | Описание                           |
| -----: | --------------------- | ---------------------------------- |
|    GET | `/api/events/`        | список событий (пагинация/фильтры) |
|   POST | `/api/events/`        | создать событие                    |
|    GET | `/api/events/{id}/`   | получить событие                   |
|  PATCH | `/api/events/{id}/`   | частичное обновление               |
| DELETE | `/api/events/{id}/`   | удалить событие                    |
|    GET | `/api/users/`         | список пользователей TG            |
|    GET | `/api/users/{tg_id}/` | карточка пользователя              |
|    GET | `/api/appointments/`  | список встреч                      |
|   POST | `/api/appointments/`  | создать встречу                    |

> Для учебных целей API открыт. В проде — добавить аутентификацию (Session/JWT), права и фильтры.

**Примеры запросов (curl):**

```bash
# Список событий
curl -s http://127.0.0.1:8000/api/events/

# Создать событие
curl -s -X POST http://127.0.0.1:8000/api/events/ \
  -H "Content-Type: application/json" \
  -d '{"user_id": 667400736, "name": "Встреча", "date": "2025-12-12", "time": "12:12:00", "details": "обсуждение"}'
```

**Browsable API:**
`http://127.0.0.1:8000/api/` — удобная веб-форма DRF для ручной проверки.

---

## Экспорт событий (CSV/JSON)

**Эндпоинты:**

* `GET /export/json/?token=<подпись>` — JSON
* `GET /export/csv/?token=<подпись>` — CSV (Windows-friendly, `cp1251`, BOM, `sep=;`)

**Как получить ссылку:** в боте команда `/export` выдаёт две кнопки со ссылками на эти эндпоинты.
**Токен:** генерируется на стороне сервера из `tg_user_id` + тайм-штампа + подписи, имеет ограниченный срок жизни.

**CSV-особенности для Excel (Windows):**

* Кодировка **cp1251** + BOM;
* Первая строка `sep=;` — чтобы Excel сразу выбрал `;` как разделитель;
* Заголовки: `id;name;date;time;details;tg_user_id`.

---

## Автоматические тесты

**Файлы:** `tests/`

* `conftest.py` — фикстуры (в т.ч. создание внешней таблицы `events` один раз).
* `test_export_views.py` — проверка JSON/CSV-экспорта.
* `test_handlers_events.py` — базовые сценарии `/start` и `/help`.
* `test_models.py` — `TgUser`, `Appointment`, `BotStatistics`.

**Запуск:**

```bash
pytest --reuse-db -q
```

**Пример успешного прогона:**

```
6 passed
```

**pytest.ini:**

```ini
[pytest]
addopts = -q --reuse-db -ra
DJANGO_SETTINGS_MODULE = webapp.settings
filterwarnings =
    ignore::DeprecationWarning
    ignore:python-telegram-bot is using upstream urllib3:UserWarning
    ignore:pkg_resources is deprecated:UserWarning
```

> При первом запуске тестов Django создаёт тестовую БД. У Postgres-пользователя должны быть права `CREATEDB`.

---

## Модели данных

* **TgUser**

  * `tg_id` (PK, BIGINT), `username`, `first_name`, `last_name`, `is_active`
  * счётчики: `events_created`, `events_edited`, `events_cancelled`
  * тайм-метки: `created_at`, `updated_at`
  * таблица: `tg_users`

* **Event** (`managed=False`, таблица создаётся ботом)

  * `id`, `user_id` (FK-like на `TgUser.tg_id`, `db_constraint=False`)
  * `is_public`, `name`, `date`, `time`, `details`
  * таблица: `events`

* **Appointment**

  * связи по TG-ID: `organizer_tg_id`, `participant_tg_id`
  * `event` (FK-like на `Event`, `db_constraint=False`)
  * `date`, `time`, `details`, `status`
  * таблица: `calendarapp_appointment`

* **BotStatistics**

  * `date` (unique), `user_count`, `event_count`, `edited_events`, `cancelled_events`

---

## Админ-панель

* `http://127.0.0.1:8000/admin/`
* Доступны: `TgUser`, `Appointment`, `BotStatistics`, просмотр `Event` (read-only).

---

## Типичные проблемы и решения

* **`ModuleNotFoundError: No module named 'webapp.settings'`**

  * Запускайте бота из корня проекта (`python bot.py`), не из подпапок.
  * Убедитесь, что `webapp/webapp/__init__.py` существует (пакет Django).

* **При тестах:**

  * `RuntimeError: Database access not allowed…` — добавьте `@pytest.mark.django_db`.
  * `ProgrammingError: нет прав для создания базы данных` — у пользователя Postgres должен быть `CREATEDB`.

* **CSV открывается «кракозябрами» в Excel**

  * Используемый формат уже адаптирован: BOM + `cp1251` + `sep=;`. Скачайте файл и откройте в Excel, а не в браузере.

* **Конфликт getUpdates**

  * Запущена вторая копия бота. Остановите дублирующий процесс.

---