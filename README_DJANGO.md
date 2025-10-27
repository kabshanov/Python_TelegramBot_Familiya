# README_DJANGO — веб-панель и ORM-слой

Документ описывает **только Django-часть** проекта: модели, админ-панель, настройки БД и запуск dev-сервера. Работа телеграм-бота — в `README_BOT.md`. Общий обзор — в `README.md`.

---

## Оглавление

* [Назначение и возможности](#назначение-и-возможности)
* [Стек технологий](#стек-технологий)
* [Инструменты и документация](#инструменты-и-документация)
* [Требования](#требования)
* [Установка и конфигурация](#установка-и-конфигурация)
* [Запуск](#запуск)
* [Модели данных](#модели-данных)
* [Админ-панель](#админ-панель)
* [Структура проекта](#структура-проекта)
* [Описание директорий и ключевых файлов](#описание-директорий-и-ключевых-файлов)
* [Интеграция с телеграм-ботом](#интеграция-с-телеграм-ботом)
* [Типичные проблемы и решения](#типичные-проблемы-и-решения)
* [Чек-лист перед PR](#чек-лист-перед-pr)

---

## Назначение и возможности

* Веб-слой на **Django** для просмотра и администрирования данных календаря.
* **Админ-панель** показывает:

  * реальные события пользователей из таблицы `events` (куда пишет бот);
  * суточную **статистику бота** (новые пользователи, созданные/редактированные/удалённые события).
* **ORM** используется для статистики; события маппятся на уже существующую таблицу.

---

## Стек технологий

* **Python 3.11–3.13**
* **Django 5.x**
* **Django Admin**
* **PostgreSQL 14–16**
* **psycopg2** (драйвер Postgres)

---

## Инструменты и документация

* Django: [https://docs.djangoproject.com/](https://docs.djangoproject.com/)
  • Admin: [https://docs.djangoproject.com/en/stable/ref/contrib/admin/](https://docs.djangoproject.com/en/stable/ref/contrib/admin/)
  • ORM: [https://docs.djangoproject.com/en/stable/topics/db/models/](https://docs.djangoproject.com/en/stable/topics/db/models/)
* PostgreSQL: [https://www.postgresql.org/docs/](https://www.postgresql.org/docs/)
* psycopg2: [https://www.psycopg.org/docs/](https://www.psycopg.org/docs/)
* Python: [https://docs.python.org/3/](https://docs.python.org/3/)

**MDN (базовые веб-понятия):**
HTTP — [https://developer.mozilla.org/en-US/docs/Web/HTTP](https://developer.mozilla.org/en-US/docs/Web/HTTP)
URL — [https://developer.mozilla.org/en-US/docs/Web/API/URL](https://developer.mozilla.org/en-US/docs/Web/API/URL)
JSON — [https://developer.mozilla.org/en-US/docs/Learn/JavaScript/Objects/JSON](https://developer.mozilla.org/en-US/docs/Learn/JavaScript/Objects/JSON)

---

## Требования

**Система**

* Python **3.11+**
* PostgreSQL **14+**
* Свободный порт **8000**

**Браузеры (доступ к /admin)**

* Chrome / Edge / Firefox — последние версии
* Safari **16+**

---

## Установка и конфигурация

1. Установите зависимости (из корня репозитория):

```bash
pip install -r requirements_part2.txt
```

2. Проверьте подключение к БД:

* Django: [`webapp/webapp/settings.py`](./webapp/webapp/settings.py) → `DATABASES`
* Бот (для общей БД): [`db.py`](./db.py)

Пример фрагмента `settings.py`:

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "calendar_db",
        "USER": "calendar_user",
        "PASSWORD": "strong_password",
        "HOST": "localhost",
        "PORT": "5432",
    }
}
```

3. Проверьте приложения:

* `INSTALLED_APPS` в [`webapp/webapp/settings.py`](./webapp/webapp/settings.py) должно содержать:

  ```python
  INSTALLED_APPS = [
      # ...
      "calendarapp",
      # ...
  ]
  ```
* В [`webapp/calendarapp/apps.py`](./webapp/calendarapp/apps.py) — `name = "calendarapp"`.
* В пакетах есть `__init__.py`:
  [`webapp/webapp/__init__.py`](./webapp/webapp/__init__.py), [`webapp/calendarapp/__init__.py`](./webapp/calendarapp/__init__.py).

4. Примените миграции и создайте суперпользователя:

```bash
python webapp/manage.py migrate
python webapp/manage.py createsuperuser
```

---

## Запуск

Из **корня** репозитория:

```bash
python webapp/manage.py runserver
```

* Главная: `http://127.0.0.1:8000/`
* Админ-панель: `http://127.0.0.1:8000/admin/` (логин: суперпользователь)

> Важно: запускать из корня (а не `cd webapp && python manage.py runserver`), чтобы корректно резолвились пути и импорты.

---

## Модели данных

Файл: [`webapp/calendarapp/models.py`](./webapp/calendarapp/models.py)

### `Event`

* Представляет записи в **существующей** таблице `events`, которую создаёт и заполняет телеграм-бот.
* Мэппинг:

  * `Meta.managed = False` — Django не создаёт/мигрирует таблицу;
  * `Meta.db_table = "events"` — используем готовую таблицу;
  * поле модели `tg_user_id` маппится на колонку `user_id` (`db_column="user_id"`).

Ключевые поля:

* `id: BigAutoField (PK)`
* `name: CharField(255)`
* `date: DateField`
* `time: TimeField`
* `details: TextField`
* `tg_user_id: BigIntegerField (db_column="user_id")`

### `BotStatistics`

* Таблица создаётся и управляется **через Django миграции** (`calendarapp_botstatistics`).
* Поля:

  * `date: DateField, unique`
  * `user_count: PositiveIntegerField`
  * `event_count: PositiveIntegerField`
  * `edited_events: PositiveIntegerField`
  * `cancelled_events: PositiveIntegerField`

> Телеграм-бот обновляет статистику через ORM, и записи видны в админке.

---

## Админ-панель

Регистрация моделей: [`webapp/calendarapp/admin.py`](./webapp/calendarapp/admin.py)

* **EventAdmin**

  * `list_display = ("id", "name", "date", "time", "tg_user_id")`
  * `list_filter = ("date",)`
  * `search_fields = ("name", "details", "tg_user_id")`

* **BotStatisticsAdmin**

  * `list_display = ("date", "user_count", "event_count", "edited_events", "cancelled_events")`
  * `list_filter = ("date",)`

---

## Структура проекта

```text
Python_TelegramBot_Kabshanov/
├─ webapp/
│  ├─ manage.py
│  ├─ webapp/
│  │  ├─ __init__.py
│  │  ├─ settings.py          # БД, INSTALLED_APPS, конфиг Django
│  │  ├─ urls.py
│  │  └─ wsgi.py
│  └─ calendarapp/
│     ├─ __init__.py
│     ├─ apps.py              # name="calendarapp"
│     ├─ admin.py             # регистрация Event и BotStatistics
│     ├─ models.py            # Event (db_table=events, managed=False), BotStatistics (ORM)
│     └─ migrations/
│        └─ 0001_initial.py   # таблица статистики
├─ bot.py                      # (бот — использует ORM для статистики)
├─ db.py                       # (SQL-операции для users/events)
├─ requirements_part2.txt
└─ README_DJANGO.md
```

### Описание директорий и ключевых файлов

* [`webapp/webapp/settings.py`](./webapp/webapp/settings.py) — настройки Django и БД.
* [`webapp/calendarapp/models.py`](./webapp/calendarapp/models.py) — модели `Event`, `BotStatistics`.
* [`webapp/calendarapp/admin.py`](./webapp/calendarapp/admin.py) — настройка админ-списков/фильтров.
* [`webapp/manage.py`](./webapp/manage.py) — утилиты (`runserver`, `migrate`, `createsuperuser`).

---

## Интеграция с телеграм-ботом

* Бот записывает события в **таблицу `events`** через чистый SQL (`psycopg2`) — см. [`db.py`](./db.py).
* Django-модель `Event` **маппится** на эту таблицу (`managed=False`, `db_table="events"`), поэтому админ-панель показывает **те же** данные.
* Сводная статистика (`BotStatistics`) создаётся и обновляется **ботом через ORM** и отображается в админке.

---

## Типичные проблемы и решения

* **`ModuleNotFoundError: No module named 'calendarapp'` при `runserver`**
  Запускайте из корня: `python webapp/manage.py runserver`.
  Проверьте `INSTALLED_APPS` и `apps.py (name="calendarapp")`, а также наличие `__init__.py`.

* **Админ-список “События” пустой**
  Убедитесь, что в `models.Event` стоит `managed=False`, `db_table="events"`,
  а поле `tg_user_id` имеет `db_column="user_id"` — тогда админка читает реальную таблицу бота.

* **Ошибки прав БД (например, при миграциях)**
  Выдайте необходимые привилегии пользователю PostgreSQL и убедитесь, что подключение единообразно в Django и у бота.

---

## Чек-лист перед PR

* [ ] `python webapp/manage.py runserver` поднимается без ошибок
* [ ] `/admin` доступен, вход по суперпользователю работает
* [ ] В разделе **События** видны записи из таблицы `events`
* [ ] В разделе **Статистика бота** видны/появляются записи за текущие дни
* [ ] `models.Event` = `managed=False`, `db_table="events"`, `tg_user_id -> user_id`
* [ ] `INSTALLED_APPS` содержит `calendarapp`, `apps.py.name = "calendarapp"`
* [ ] Файлы пакетов имеют `__init__.py`
* [ ] Конфиг БД единый для Django и бота (`settings.py` и `db.py`)


