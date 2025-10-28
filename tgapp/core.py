"""
tgapp.core
Базовая инфраструктура бота:
- bootstrap Django
- логирование
- подключение к БД и Calendar
- общие утилиты (меню, ensure_registered)
- учёт статистики (BotStatistics)
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime

import django

# --- Сделаем видимым webapp/ для импорта calendarapp ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DJANGO_APPS_DIR = os.path.join(PROJECT_ROOT, "webapp")
if DJANGO_APPS_DIR not in sys.path:
    sys.path.insert(0, DJANGO_APPS_DIR)

# --- Django bootstrap ---
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webapp.settings")
django.setup()

# Теперь можно импортировать Django-модели
from django.db import transaction  # noqa: E402
from calendarapp.models import BotStatistics  # noqa: E402

from telegram import BotCommand, ReplyKeyboardMarkup, ReplyKeyboardRemove  # noqa: E402

# БД-обёртки проекта
from db import (  # noqa: E402
    get_connection,
    Calendar,
    register_user,
    user_exists,
)

# --- Логирование ---
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --- Подключение к БД (общая для бота) ---
CONN = get_connection()
CALENDAR = Calendar(CONN)

# --- Общая клавиатура «Отмена» для диалогов ---
CANCEL_KB = ReplyKeyboardMarkup([["Отмена"]], resize_keyboard=True, one_time_keyboard=True)


# ========== Статистика (BotStatistics) ==========

def _get_today_stat_row() -> BotStatistics:
    """Получить/создать строку статистики за сегодня."""
    today = datetime.now().date()
    stat, _ = BotStatistics.objects.get_or_create(
        date=today,
        defaults={
            "user_count": 0,
            "event_count": 0,
            "edited_events": 0,
            "cancelled_events": 0,
        },
    )
    return stat


@transaction.atomic
def track_new_user(tg_user_id: int, is_new: bool) -> None:
    """Инкрементировать user_count, если пользователь действительно новый."""
    if not is_new:
        return
    stat = _get_today_stat_row()
    stat.user_count += 1
    stat.save()
    logger.info("STAT: user_count +=1 tg_user_id=%s", tg_user_id)


@transaction.atomic
def track_event_created() -> None:
    stat = _get_today_stat_row()
    stat.event_count += 1
    stat.save()
    logger.info("STAT: event_count +=1")


@transaction.atomic
def track_event_edited() -> None:
    stat = _get_today_stat_row()
    stat.edited_events += 1
    stat.save()
    logger.info("STAT: edited_events +=1")


@transaction.atomic
def track_event_cancelled() -> None:
    stat = _get_today_stat_row()
    stat.cancelled_events += 1
    stat.save()
    logger.info("STAT: cancelled_events +=1")


# ========== Общие утилиты ==========

def setup_bot_commands(bot) -> None:
    """Показать меню команд в клиенте Telegram."""
    commands = [
        BotCommand("start", "Справка и команды"),
        BotCommand("help", "Справка"),
        BotCommand("register", "Регистрация"),
        BotCommand("create_event", "Создать событие (диалог)"),
        BotCommand("display_events", "Показать мои события"),
        BotCommand("read_event", "Показать событие по ID"),
        BotCommand("edit_event", "Изменить описание события"),
        BotCommand("delete_event", "Удалить событие"),
        BotCommand("cancel", "Отменить текущую операцию"),
        BotCommand("invite", "Пригласить на встречу (/invite <tg_id> <event_id> [текст])"),
    ]
    bot.set_my_commands(commands)
    logger.info("TG меню команд установлено (%d шт.)", len(commands))


def ensure_registered(update, *, user_id: int, username: str, first_name: str) -> bool:
    """
    Проверить регистрацию пользователя, при необходимости — подсказать /register.
    Возвращает True, если пользователь зарегистрирован.
    """
    try:
        exists = user_exists(CONN, user_id)
    except Exception:
        update.message.reply_text("Ошибка доступа к базе при проверке регистрации.")
        return False

    if exists:
        return True

    update.message.reply_text("Сначала выполните регистрацию: /register")
    return False


def register_in_db_and_track(update, *, user_id: int, username: str, first_name: str) -> None:
    """Регистрация пользователя + учёт статистики «новый пользователь»."""
    already_exists = user_exists(CONN, user_id)
    register_user(CONN, user_id, username or "", first_name or "")
    update.message.reply_text("Регистрация выполнена. Можно создавать события.")
    track_new_user(tg_user_id=user_id, is_new=not already_exists)


# Удобный алиас, чтобы из хендлеров импортировать одним местом
__all__ = [
    "logger",
    "CONN",
    "CALENDAR",
    "CANCEL_KB",
    "setup_bot_commands",
    "ensure_registered",
    "register_in_db_and_track",
    "track_event_created",
    "track_event_edited",
    "track_event_cancelled",
]
