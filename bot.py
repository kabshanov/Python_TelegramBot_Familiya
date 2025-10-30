"""
bot.py
======

Главная точка входа Telegram-бота.

Функции:
- создаёт объект `Updater` (python-telegram-bot);
- регистрирует все хендлеры команд и сообщений;
- настраивает меню команд;
- связывает обработчики событий (tgapp.handlers_events)
  и встреч (tgapp.handlers_appointments);
- запускает polling-цикл (долгоживущий процесс получения обновлений).

Архитектура:
- FSM и бизнес-логика событий/встреч находятся в пакете `tgapp`;
- Django-часть (модели, ORM) подключается через webapp (настроено ранее);
- bot.py отвечает только за сборку и запуск Telegram-уровня.
"""

from __future__ import annotations

import logging
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters
)

import bot_secrets  # содержит API_TOKEN
from tgapp.core import setup_bot_commands, logger
from tgapp import handlers_events as ev
from tgapp import handlers_appointments as appt
from db import get_connection, ensure_is_public_column
from telegram.ext import CallbackQueryHandler


# ---------------------------------------------------------------------------
# Глобальный обработчик ошибок
# ---------------------------------------------------------------------------

def error_handler(update, context) -> None:
    """
    Универсальный логгер необработанных ошибок в хендлерах.

    :param update: объект Update (может быть None при системных ошибках)
    :param context: CallbackContext с полем .error
    """
    logging.exception("UNHANDLED ERROR: %s (update=%s)", context.error, update)


# ---------------------------------------------------------------------------
# Точка входа приложения
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Инициализация и запуск Telegram-бота.

    1) Проводит подготовку схемы БД для публичных событий (Task 5).
    2) Создаёт Updater и Dispatcher.
    3) Регистрирует все хендлеры команд, сообщений и callback-кнопок.
    4) Запускает polling-цикл до прерывания пользователем (Ctrl-C).
    """
    # 1) Гарантируем наличие колонки is_public в таблице events (вызов безопасен)
    conn = get_connection()
    ensure_is_public_column(conn)

    # 2) Инициализация Updater / Dispatcher
    updater = Updater(token=bot_secrets.API_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Меню /help
    setup_bot_commands(updater.bot)

    # --- Базовые команды ---
    dispatcher.add_handler(CommandHandler("start", ev.start))
    dispatcher.add_handler(CommandHandler("help", ev.help_command))
    dispatcher.add_handler(CommandHandler("register", ev.register_command))
    dispatcher.add_handler(CommandHandler("cancel", ev.cancel_command))

    # --- События (CRUD) ---
    dispatcher.add_handler(CommandHandler("display_events", ev.display_events_handler))
    dispatcher.add_handler(CommandHandler("read_event", ev.read_event_handler))
    dispatcher.add_handler(CommandHandler("create_event", ev.create_event_start))
    dispatcher.add_handler(CommandHandler("edit_event", ev.edit_event_start_or_inline))
    dispatcher.add_handler(CommandHandler("delete_event", ev.delete_event_start_or_inline))

    # --- Публичные события (Task 5) ---
    dispatcher.add_handler(CommandHandler("share_event", ev.share_event_start))
    dispatcher.add_handler(CommandHandler("my_public", ev.list_my_public_command))
    dispatcher.add_handler(CommandHandler("public_of", ev.public_of_start))  # FSM-версия
    dispatcher.add_handler(CallbackQueryHandler(ev.fsm_cancel_callback, pattern=r"^fsm:cancel$"))

    # --- Встречи и приглашения ---
    dispatcher.add_handler(CommandHandler("invite", appt.invite_start))
    dispatcher.add_handler(CallbackQueryHandler(appt.appointment_decision_handler, pattern=r"^appt:"))

    # --- Профиль и календарь ---
    dispatcher.add_handler(CommandHandler("login", ev.login_command))
    dispatcher.add_handler(CommandHandler("calendar", ev.calendar_command))

    # --- FSM-тексты (не команды) ---
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, ev.text_router))

    # --- Ошибки ---
    dispatcher.add_error_handler(error_handler)

    # --- Запуск ---
    updater.start_polling()
    logger.info("BOT запущен: FSM, встречи, статистика, публичные события, PostgreSQL, Django ORM активны.")
    updater.idle()


# ---------------------------------------------------------------------------
# CLI-точка входа
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
