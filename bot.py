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
- Django-часть (модели, ORM) подключается автоматически при импорте;
- bot.py отвечает только за сборку и запуск Telegram-уровня.
"""

from __future__ import annotations

import logging
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
)

import bot_secrets  # содержит API_TOKEN
from tgapp.core import setup_bot_commands, logger
from tgapp import handlers_events as ev
from tgapp import handlers_appointments as appt


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

    1. Создаёт Updater и Dispatcher.
    2. Регистрирует все хендлеры команд, сообщений и callback-кнопок.
    3. Запускает polling-цикл до прерывания пользователем (Ctrl-C).

    Использует токен из файла `bot_secrets.py`.
    """
    # Инициализация Updater / Dispatcher
    updater = Updater(token=bot_secrets.API_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Настройка меню /help
    setup_bot_commands(updater.bot)

    # --- Базовые команды ---
    dispatcher.add_handler(CommandHandler("start", ev.start))
    dispatcher.add_handler(CommandHandler("help", ev.help_command))
    dispatcher.add_handler(CommandHandler("register", ev.register_command))
    dispatcher.add_handler(CommandHandler("cancel", ev.cancel_command))

    # --- События ---
    dispatcher.add_handler(CommandHandler("display_events", ev.display_events_handler))
    dispatcher.add_handler(CommandHandler("read_event", ev.read_event_handler))
    dispatcher.add_handler(CommandHandler("create_event", ev.create_event_start))
    dispatcher.add_handler(CommandHandler("edit_event", ev.edit_event_start_or_inline))
    dispatcher.add_handler(CommandHandler("delete_event", ev.delete_event_start_or_inline))

    # --- Встречи и приглашения ---
    dispatcher.add_handler(CommandHandler("invite", appt.invite_start))
    dispatcher.add_handler(CallbackQueryHandler(appt.appointment_decision_handler, pattern=r"^appt:"))

    # --- FSM-тексты (не команды) ---
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, ev.text_router))

    # --- Ошибки ---
    dispatcher.add_error_handler(error_handler)

    # --- Профиль и календарь ---
    dispatcher.add_handler(CommandHandler("login", ev.login_command))
    dispatcher.add_handler(CommandHandler("calendar", ev.calendar_command))

    # --- Запуск ---
    updater.start_polling()
    logger.info("BOT запущен: FSM, статистика, PostgreSQL, Django ORM активны.")
    updater.idle()


# ---------------------------------------------------------------------------
# CLI-точка входа
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
