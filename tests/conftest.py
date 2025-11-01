# tests/conftest.py
from __future__ import annotations

import os
import sys
import types
import pytest

# --- Путь к Django-проекту и настройка DJANGO_SETTINGS_MODULE ---
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # корень репо
WEBAPP_DIR = os.path.join(REPO_ROOT, "webapp")
if WEBAPP_DIR not in sys.path:
    sys.path.insert(0, WEBAPP_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webapp.settings")

import django  # noqa: E402
django.setup()  # noqa: E402

from django.db import connection  # noqa: E402
from calendarapp.models import Event  # noqa: E402


@pytest.fixture(autouse=True, scope="session")
def _setup_events_table(django_db_setup, django_db_blocker):
    """
    Создаём внешнюю таблицу `events` (Event.managed=False) один раз за сессию тестов.
    ВАЖНО: доступ к БД в session-фикстуре делаем внутри django_db_blocker.unblock().
    """
    sql = """
    CREATE TABLE IF NOT EXISTS events (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        name TEXT NOT NULL,
        date DATE NOT NULL,
        time TIME NOT NULL,
        details TEXT DEFAULT '',
        is_public BOOLEAN NOT NULL DEFAULT FALSE
    );
    """
    with django_db_blocker.unblock():
        with connection.cursor() as cur:
            cur.execute(sql)


@pytest.fixture
def make_event(db):
    """
    Фабрика событий в таблице events через ORM-модель Event (managed=False).
    """
    def _create(
        tg_user_id: int,
        name: str = "Test",
        date: str = "2025-12-12",
        time: str = "12:12",
        details: str = "",
        is_public: bool = False,
    ):
        return Event.objects.create(
            user_id=tg_user_id,
            name=name,
            date=date,
            time=time,
            details=details,
            is_public=is_public,
        )
    return _create


# --- Простейшие заглушки для handler-тестов (без реального Telegram) ---

class FakeMessage:
    def __init__(self, text: str, chat_id: int, user_id: int, username: str | None = None):
        self.text = text
        self.chat_id = chat_id
        self.from_user = types.SimpleNamespace(id=user_id, username=username)
        self.last_reply = None
        self.last_markup = None

    def reply_text(self, text: str, reply_markup=None):
        self.last_reply = text
        self.last_markup = reply_markup


class FakeUpdate:
    def __init__(self, text: str, user_id: int = 777, username: str | None = "user777"):
        self.effective_user = types.SimpleNamespace(id=user_id, username=username)
        self.message = FakeMessage(text=text, chat_id=user_id, user_id=user_id, username=username)


class FakeContext:
    def __init__(self):
        self.user_data = {}
        self.bot_data = {}
        self.args = []


@pytest.fixture
def fctx():
    return FakeContext()
