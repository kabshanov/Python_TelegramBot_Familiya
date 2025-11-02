"""
bot.py
======

Главная точка входа Telegram-бота.

Что делает:
- корректно поднимает Django (DJANGO_SETTINGS_MODULE + django.setup);
- гарантирует колонку is_public у таблицы events;
- создаёт Updater/Dispatcher (python-telegram-bot v13.x);
- регистрирует все команды/хендлеры (события, встречи, публичность, экспорт);
- настраивает меню команд;
- запускает polling-цикл.

Архитектура:
- Telegram-слой (FSM/бизнес-логика) — пакет `tgapp`;
- Django-ORM и веб — пакет `webapp` (settings: webapp.settings).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Django bootstrap: делаем так, чтобы `webapp.settings` гарантированно импортировался
# ---------------------------------------------------------------------------
from pathlib import Path
import os
import sys
import importlib

PROJECT_ROOT = Path(__file__).resolve().parent
OUTER_WEBAPP = PROJECT_ROOT / "webapp"          # здесь лежит manage.py
INNER_WEBAPP = OUTER_WEBAPP / "webapp"          # здесь лежат settings.py / urls.py

def _patch_sys_path() -> None:
    """
    Гарантируем корректный порядок путей:
    1) <корень>/webapp  — чтобы импортировался пакет `webapp` (внутренний)
    2) <корень>         — остальное
    + удаляем дубликаты
    """
    new_path: list[str] = []
    seen: set[str] = set()

    preferred = [str(OUTER_WEBAPP), str(PROJECT_ROOT)]
    for p in preferred + sys.path:
        if p not in seen:
            new_path.append(p)
            seen.add(p)
    sys.path[:] = new_path

def _preflight_checks() -> None:
    """
    Базовые проверки структуры проекта, чтобы импорт не срывался молча.
    """
    # 1) Внутренний пакет должен существовать
    init_file = INNER_WEBAPP / "__init__.py"
    if not init_file.exists():
        raise RuntimeError(
            "Не найден пакет Django: ожидался файл "
            f"'{init_file}'. Проверь структуру: webapp/manage.py и webapp/webapp/__init__.py"
        )

    # 2) Коллизия имён: файл webapp.py в корне перекрывает пакет `webapp`
    shadow = PROJECT_ROOT / "webapp.py"
    if shadow.exists():
        raise RuntimeError(
            f"Обнаружен файл '{shadow}'. Он перекрывает пакет `webapp` и ломает импорт. "
            "Переименуйте/удалите этот файл."
        )

# Применяем патч и проверки
_patch_sys_path()
_preflight_checks()

# Сообщаем Django, где искать настройки
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webapp.settings")

# Пробуем импортировать настройки, чтобы рано упасть с понятной диагностикой
try:
    importlib.import_module("webapp.settings")  # noqa: F401
except ModuleNotFoundError as e:
    # Показываем диагностический контекст и падаем
    ctx = (
        "\nИмпорт 'webapp.settings' не удался.\n"
        f"sys.path[0:4]: {sys.path[:4]}\n"
        f"Ожидался модуль по пути: {INNER_WEBAPP / 'settings.py'}\n"
        "Проверьте, что запускаете из корня проекта: `python bot.py`.\n"
    )
    raise ModuleNotFoundError(ctx) from e

# Теперь можно поднимать Django
import django  # noqa: E402
django.setup()  # noqa: E402

# ---------------------------------------------------------------------------
# Дальше — обычные импорты бота
# ---------------------------------------------------------------------------
import logging  # noqa: E402
from typing import NoReturn  # noqa: E402

from telegram import Update  # noqa: E402
from telegram.ext import (  # noqa: E402
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
    CallbackContext,
)

import bot_secrets  # содержит API_TOKEN  # noqa: E402
from db import get_connection, ensure_is_public_column  # noqa: E402
from tgapp.core import setup_bot_commands, logger as app_logger  # noqa: E402
from tgapp import handlers_events as ev  # noqa: E402
from tgapp import handlers_appointments as appt  # noqa: E402


# ---------------------------------------------------------------------------
# Логирование
# ---------------------------------------------------------------------------

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("calendar_bot")


# ---------------------------------------------------------------------------
# Глобальный обработчик ошибок
# ---------------------------------------------------------------------------

def error_handler(update: object, context: CallbackContext) -> None:
    """
    Универсальный логгер необработанных ошибок в хендлерах.

    :param update: объект Update (может быть None при системных ошибках)
    :param context: CallbackContext c полем .error
    """
    log.exception("UNHANDLED ERROR: %s (update=%r)", context.error, update)


# ---------------------------------------------------------------------------
# Регистрация хендлеров
# ---------------------------------------------------------------------------

def _register_handlers(updater: Updater) -> None:
    """
    Регистрирует все хендлеры команд/сообщений и callback-кнопок
    на едином Dispatcher.
    """
    dp = updater.dispatcher

    # --- Базовые команды ---
    dp.add_handler(CommandHandler("start", ev.start))
    dp.add_handler(CommandHandler("help", ev.help_command))
    dp.add_handler(CommandHandler("register", ev.register_command))
    dp.add_handler(CommandHandler("cancel", ev.cancel_command))

    # --- События (CRUD) ---
    dp.add_handler(CommandHandler("display_events", ev.display_events_handler))
    dp.add_handler(CommandHandler("read_event", ev.read_event_handler))
    dp.add_handler(CommandHandler("create_event", ev.create_event_start))
    dp.add_handler(CommandHandler("edit_event", ev.edit_event_start_or_inline))
    dp.add_handler(CommandHandler("delete_event", ev.delete_event_start_or_inline))

    # --- Публичные события (Task 5) ---
    dp.add_handler(CommandHandler("share_event", ev.share_event_start))
    dp.add_handler(CommandHandler("my_public", ev.list_my_public_command))
    dp.add_handler(CommandHandler("public_of", ev.public_of_start))
    dp.add_handler(CallbackQueryHandler(ev.fsm_cancel_callback, pattern=r"^fsm:cancel$"))

    # --- Встречи и приглашения ---
    dp.add_handler(CommandHandler("invite", appt.invite_start))
    dp.add_handler(CallbackQueryHandler(appt.appointment_decision_handler, pattern=r"^appt:"))

    # --- Профиль и календарь ---
    dp.add_handler(CommandHandler("login", ev.login_command))
    dp.add_handler(CommandHandler("calendar", ev.calendar_command))
    dp.add_handler(CommandHandler("export", ev.export_command))  # Task 6: CSV/JSON

    # --- FSM-тексты (не команды) ---
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, ev.text_router))

    # --- Ошибки ---
    dp.add_error_handler(error_handler)

    log.info("Handlers registered: commands + callbacks готовы.")


# ---------------------------------------------------------------------------
# Точка входа приложения
# ---------------------------------------------------------------------------

def main() -> NoReturn:
    """
    Инициализация и запуск Telegram-бота.

    Шаги:
    1) Проверка схемы БД (is_public для events);
    2) Создание Updater/Dispatcher, меню команд;
    3) Регистрация хендлеров;
    4) Запуск polling.
    """
    # 1) База данных: колонка для публичности событий
    conn = get_connection()
    ensure_is_public_column(conn)

    # 2) Updater / Dispatcher
    if not getattr(bot_secrets, "API_TOKEN", None):
        raise RuntimeError("bot_secrets.API_TOKEN не задан")

    updater = Updater(token=bot_secrets.API_TOKEN, use_context=True)

    # Меню /help
    setup_bot_commands(updater.bot)

    # 3) Handlers
    _register_handlers(updater)

    # 4) Запуск polling
    updater.start_polling()
    app_logger.info(
        "BOT запущен: FSM, встречи, публикации, экспорт, PostgreSQL/Django активны."
    )
    updater.idle()


# ---------------------------------------------------------------------------
# CLI-точка входа
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        log.exception("Fatal error on bot startup")
        raise
