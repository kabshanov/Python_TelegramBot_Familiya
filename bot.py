"""
bot.py

Телеграм-бот «календарь».

Функции:
- регистрация пользователя (/register);
- создание события (многошаговый FSM-диалог /create_event);
- просмотр событий (/display_events);
- чтение события по ID (/read_event <id>);
- редактирование (/edit_event ... или FSM);
- удаление (/delete_event ... или FSM);
- отмена текущей операции (/cancel);
- справка (/help, /start).

Часть 2 проекта:
- Поднимаем Django внутри бота и пишем статистику активности
  в модель BotStatistics (webapp/calendarapp/models.py), чтобы
  админ увидел метрики в панели Django (/admin):
    * user_count        — новые пользователи;
    * event_count       — созданные события;
    * edited_events     — редактированные события;
    * cancelled_events  — удалённые события.

Важно:
- FSM (user_states) хранится в памяти процесса.
- Подключение к PostgreSQL обёрнуто в db.py.
- Инициализация Django происходит вручную через django.setup().
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime

import django
from telegram import BotCommand, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

import secrets
from db import get_connection, Calendar, register_user, user_exists

# ---------------------------------------------------------------------------
# Подготовка путей так, чтобы Python видел calendarapp как пакет
# ---------------------------------------------------------------------------

# ABS_PATH_TO_PROJECT = корень проекта (где лежит bot.py)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# APP_DIR = путь до Django-приложений (папка webapp/)
DJANGO_APPS_DIR = os.path.join(PROJECT_ROOT, "webapp")

# Если ещё не в sys.path — добавим
if DJANGO_APPS_DIR not in sys.path:
    sys.path.insert(0, DJANGO_APPS_DIR)

# ---------------------------------------------------------------------------
# Django bootstrap
# ---------------------------------------------------------------------------

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webapp.settings")
django.setup()

from django.db import transaction
from calendarapp.models import BotStatistics



# ---------------------------------------------------------------------------
# Логирование
# ---------------------------------------------------------------------------

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Подключение к базе и инициализация бизнес-обёртки календаря
# ---------------------------------------------------------------------------

CONN = get_connection()
CALENDAR = Calendar(CONN)


# ---------------------------------------------------------------------------
# FSM (Finite State Machine) — состояние многошаговых диалогов
# user_states[user_id] = {"flow": ..., "step": ..., "data": {...}}
# ---------------------------------------------------------------------------

user_states: dict[int, dict] = {}


def set_state(user_id: int, flow: str | None, step: str | None, data: dict | None) -> None:
    """
    Установить текущее состояние пользователя в FSM.

    :param user_id: Telegram ID пользователя.
    :param flow: Название сценария ("CREATE", "EDIT", "DELETE", ...).
    :param step: Текущий шаг сценария.
    :param data: Временные данные сценария.
    """
    user_states[user_id] = {
        "flow": flow,
        "step": step,
        "data": data or {},
    }
    logger.info(
        "FSM set user_id=%s flow=%s step=%s data=%s",
        user_id,
        flow,
        step,
        user_states[user_id]["data"],
    )


def get_state(user_id: int) -> dict:
    """
    Получить текущее состояние FSM для пользователя.

    :param user_id: Telegram ID.
    :return: Словарь состояния или дефолт.
    """
    return user_states.get(
        user_id,
        {"flow": None, "step": None, "data": {}},
    )


def clear_state(user_id: int) -> None:
    """
    Сбросить состояние FSM для пользователя.
    """
    if user_id in user_states:
        logger.info("FSM clear user_id=%s (was %s)", user_id, user_states[user_id])
        del user_states[user_id]


# Клавиатура «Отмена» для диалогов
CANCEL_KB = ReplyKeyboardMarkup(
    [["Отмена"]],
    resize_keyboard=True,
    one_time_keyboard=True,
)


# ---------------------------------------------------------------------------
# Парсеры даты и времени
# ---------------------------------------------------------------------------

def parse_date(text: str) -> str | None:
    """
    Проверить, что text — дата формата ГГГГ-ММ-ДД.
    Вернуть ту же строку, если ок, иначе None.
    """
    try:
        datetime.strptime(text, "%Y-%m-%d")
        return text
    except ValueError:
        return None


def parse_time(text: str) -> str | None:
    """
    Проверить, что text — время формата ЧЧ:ММ.
    Вернуть ту же строку, если ок, иначе None.
    """
    try:
        datetime.strptime(text, "%H:%M")
        return text
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Статистика (BotStatistics) — учёт активности
# ---------------------------------------------------------------------------

def _get_today_stat_row() -> BotStatistics:
    """
    Получить или создать запись статистики за сегодняшний день.

    :return: Объект BotStatistics за сегодняшний день.
    """
    today = datetime.now().date()
    stat, _created = BotStatistics.objects.get_or_create(
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
    """
    Зафиксировать появление нового пользователя.

    :param tg_user_id: Telegram ID пользователя.
    :param is_new: True, если пользователь не существовал до /register.
    """
    if not is_new:
        return
    stat = _get_today_stat_row()
    stat.user_count += 1
    stat.save()
    logger.info("STAT: user_count +=1 tg_user_id=%s", tg_user_id)


@transaction.atomic
def track_event_created() -> None:
    """
    Зафиксировать факт создания события.
    """
    stat = _get_today_stat_row()
    stat.event_count += 1
    stat.save()
    logger.info("STAT: event_count +=1")


@transaction.atomic
def track_event_edited() -> None:
    """
    Зафиксировать факт редактирования события.
    """
    stat = _get_today_stat_row()
    stat.edited_events += 1
    stat.save()
    logger.info("STAT: edited_events +=1")


@transaction.atomic
def track_event_cancelled() -> None:
    """
    Зафиксировать факт удаления события.
    """
    stat = _get_today_stat_row()
    stat.cancelled_events += 1
    stat.save()
    logger.info("STAT: cancelled_events +=1")


# ---------------------------------------------------------------------------
# Вспомогательные функции бота
# ---------------------------------------------------------------------------

def ensure_registered(update, *, user_id: int, username: str, first_name: str) -> bool:
    """
    Проверить, зарегистрирован ли пользователь.
    Если нет — сказать ему про /register.

    :return: True, если пользователь зарегистрирован.
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


def setup_bot_commands(updater: Updater) -> None:
    """
    Установить команды бота, чтобы они были видны в меню Telegram.
    """
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
    ]
    updater.bot.set_my_commands(commands)
    logger.info("TG меню команд установлено (%d шт.)", len(commands))


# ---------------------------------------------------------------------------
# Команды бота
# ---------------------------------------------------------------------------

def start(update, context) -> None:
    """
    /start — краткая справка.
    """
    user = update.effective_user
    logger.info("/start user_id=%s @%s", user.id, user.username)

    text = (
        "Календарь-бот.\n\n"
        "Регистрация:\n"
        "• /register — создать учётную запись\n\n"
        "События:\n"
        "• /create_event — создать событие (диалог: имя → дата → время → описание)\n"
        "• /display_events — показать мои события\n"
        "• /read_event <id> — показать событие по ID\n"
        "• /edit_event — изменить описание (диалог) или /edit_event <id> <новое>\n"
        "• /delete_event — удалить (диалог) или /delete_event <id>\n"
        "• /cancel — отменить текущую операцию\n"
    )
    update.message.reply_text(text)


def help_command(update, context) -> None:
    """
    /help — то же самое, что /start.
    """
    start(update, context)


def register_command(update, context) -> None:
    """
    /register — зарегистрировать пользователя в таблице users.
    Если пользователь новый — увеличить user_count в статистике.
    """
    user = update.effective_user
    logger.info("/register user_id=%s @%s", user.id, user.username)

    already_exists = user_exists(CONN, user.id)

    try:
        register_user(
            CONN,
            user.id,
            user.username or "",
            user.first_name or "",
        )
        update.message.reply_text("Регистрация выполнена. Можно создавать события.")
    except Exception:
        update.message.reply_text(
            "Ошибка регистрации (проверьте права на таблицу users).",
        )
        return

    track_new_user(tg_user_id=user.id, is_new=not already_exists)


def cancel_command(update, context) -> None:
    """
    /cancel — отменить любой активный сценарий FSM.
    """
    user = update.effective_user
    logger.info("/cancel user_id=%s", user.id)

    clear_state(user.id)
    update.message.reply_text(
        "Операция отменена.",
        reply_markup=ReplyKeyboardRemove(),
    )


# ---------------------------------------------------------------------------
# FSM: создание события
# ---------------------------------------------------------------------------

def create_event_start(update, context) -> None:
    """
    /create_event — начать диалог создания события.
    """
    user = update.effective_user
    logger.info("/create_event start user_id=%s", user.id)

    if not ensure_registered(
        update,
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
    ):
        return

    set_state(user.id, flow="CREATE", step="WAIT_NAME", data={})
    update.message.reply_text(
        "Введите название события:",
        reply_markup=CANCEL_KB,
    )


def create_event_process(update, context, state: dict) -> None:
    """
    FSM-обработка шагов сценария создания события:
    WAIT_NAME -> WAIT_DATE -> WAIT_TIME -> WAIT_DETAILS -> INSERT.
    """
    user = update.effective_user
    msg = update.message.text.strip()
    logger.info("FSM CREATE user_id=%s step=%s msg=%s", user.id, state["step"], msg)

    # глобальная отмена
    if msg.lower() == "отмена":
        clear_state(user.id)
        update.message.reply_text(
            "Операция отменена.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    step = state["step"]
    data = state["data"]

    if step == "WAIT_NAME":
        data["name"] = msg
        set_state(user.id, flow="CREATE", step="WAIT_DATE", data=data)
        update.message.reply_text(
            "Введите дату в формате ГГГГ-ММ-ДД:",
            reply_markup=CANCEL_KB,
        )
        return

    if step == "WAIT_DATE":
        date_str = parse_date(msg)
        if not date_str:
            update.message.reply_text(
                "Неверный формат. Пример: 2025-11-03. Попробуйте ещё раз:",
                reply_markup=CANCEL_KB,
            )
            return
        data["date"] = date_str
        set_state(user.id, flow="CREATE", step="WAIT_TIME", data=data)
        update.message.reply_text(
            "Введите время в формате ЧЧ:ММ (например, 14:30):",
            reply_markup=CANCEL_KB,
        )
        return

    if step == "WAIT_TIME":
        time_str = parse_time(msg)
        if not time_str:
            update.message.reply_text(
                "Неверный формат. Пример: 09:05. Попробуйте ещё раз:",
                reply_markup=CANCEL_KB,
            )
            return
        data["time"] = time_str
        set_state(user.id, flow="CREATE", step="WAIT_DETAILS", data=data)
        update.message.reply_text(
            "Введите описание события:",
            reply_markup=CANCEL_KB,
        )
        return

    if step == "WAIT_DETAILS":
        data["details"] = msg

        try:
            event_id = CALENDAR.create_event(
                user_id=user.id,
                name=data["name"],
                date_str=data["date"],
                time_str=data["time"],
                details=data["details"],
            )
            update.message.reply_text(
                f"Событие создано. ID: {event_id}",
                reply_markup=ReplyKeyboardRemove(),
            )
            logger.info("FSM CREATE done user_id=%s id=%s", user.id, event_id)

            # статистика: +1 созданное событие
            track_event_created()

        except ValueError as err:
            update.message.reply_text(
                str(err),
                reply_markup=ReplyKeyboardRemove(),
            )
        except Exception:
            update.message.reply_text(
                "Не удалось создать событие.",
                reply_markup=ReplyKeyboardRemove(),
            )
        finally:
            clear_state(user.id)
        return


# ---------------------------------------------------------------------------
# Просмотр и чтение событий
# ---------------------------------------------------------------------------

def display_events_handler(update, context) -> None:
    """
    /display_events — вывести список своих событий.
    """
    user = update.effective_user
    logger.info("/display_events user_id=%s", user.id)

    if not ensure_registered(
        update,
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
    ):
        return

    try:
        update.message.reply_text(CALENDAR.display_events(user.id))
    except Exception:
        update.message.reply_text("Ошибка при получении списка событий.")


def read_event_handler(update, context) -> None:
    """
    /read_event <id> — показать одно событие по ID.
    """
    user = update.effective_user
    logger.info("/read_event user_id=%s", user.id)

    if not ensure_registered(
        update,
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
    ):
        return

    parts = update.message.text.split(maxsplit=1)
    if len(parts) < 2:
        update.message.reply_text("Формат: /read_event <id>")
        return

    try:
        event_id = int(parts[1])
    except ValueError:
        update.message.reply_text("ID должен быть числом.")
        return

    try:
        res = CALENDAR.read_event(user.id, event_id)
        update.message.reply_text(res or "Событие не найдено.")
    except Exception:
        update.message.reply_text("Ошибка при чтении события.")


# ---------------------------------------------------------------------------
# Редактирование события
# ---------------------------------------------------------------------------

def edit_event_start_or_inline(update, context) -> None:
    """
    /edit_event
    Либо сразу /edit_event <id> <новое описание>,
    либо запускаем FSM, если аргументов нет.
    """
    user = update.effective_user
    logger.info("/edit_event user_id=%s", user.id)

    if not ensure_registered(
        update,
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
    ):
        return

    parts = update.message.text.split(maxsplit=2)

    # Вариант «одной строкой»: /edit_event 15 Новый текст
    if len(parts) >= 3:
        try:
            event_id = int(parts[1])
        except ValueError:
            update.message.reply_text("ID должен быть числом.")
            return

        new_text = parts[2]
        try:
            ok = CALENDAR.edit_event(user.id, event_id, new_text)
            if ok:
                update.message.reply_text("Обновлено.")
                track_event_edited()
            else:
                update.message.reply_text("Событие не найдено.")
        except Exception:
            update.message.reply_text("Ошибка при изменении события.")
        return

    # FSM-режим
    set_state(user.id, flow="EDIT", step="WAIT_ID", data={})
    update.message.reply_text(
        "Введите ID события для изменения описания:",
        reply_markup=CANCEL_KB,
    )


def edit_event_process(update, context, state: dict) -> None:
    """
    FSM редактирования события:
    1) спрашиваем ID,
    2) спрашиваем новый текст,
    3) сохраняем.
    """
    user = update.effective_user
    msg = update.message.text.strip()
    logger.info("FSM EDIT user_id=%s step=%s msg=%s", user.id, state["step"], msg)

    if msg.lower() == "отмена":
        clear_state(user.id)
        update.message.reply_text(
            "Операция отменена.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    if state["step"] == "WAIT_ID":
        try:
            event_id = int(msg)
        except ValueError:
            update.message.reply_text(
                "ID должен быть числом. Введите ID:",
                reply_markup=CANCEL_KB,
            )
            return

        set_state(
            user.id,
            flow="EDIT",
            step="WAIT_NEW_DETAILS",
            data={"id": event_id},
        )
        update.message.reply_text(
            "Введите новое описание:",
            reply_markup=CANCEL_KB,
        )
        return

    if state["step"] == "WAIT_NEW_DETAILS":
        try:
            ok = CALENDAR.edit_event(
                user.id,
                state["data"]["id"],
                msg,
            )
            if ok:
                update.message.reply_text(
                    "Обновлено.",
                    reply_markup=ReplyKeyboardRemove(),
                )
                track_event_edited()
            else:
                update.message.reply_text(
                    "Событие не найдено.",
                    reply_markup=ReplyKeyboardRemove(),
                )
        except Exception:
            update.message.reply_text(
                "Ошибка при изменении события.",
                reply_markup=ReplyKeyboardRemove(),
            )
        finally:
            clear_state(user.id)
        return


# ---------------------------------------------------------------------------
# Удаление события
# ---------------------------------------------------------------------------

def delete_event_start_or_inline(update, context) -> None:
    """
    /delete_event
    Либо сразу /delete_event <id>,
    либо запускаем FSM.
    """
    user = update.effective_user
    logger.info("/delete_event user_id=%s", user.id)

    if not ensure_registered(
        update,
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
    ):
        return

    parts = update.message.text.split(maxsplit=1)

    # Вариант одной строкой
    if len(parts) == 2:
        try:
            event_id = int(parts[1])
        except ValueError:
            update.message.reply_text("ID должен быть числом.")
            return

        try:
            ok = CALENDAR.delete_event(user.id, event_id)
            if ok:
                update.message.reply_text("Удалено.")
                track_event_cancelled()
            else:
                update.message.reply_text("Событие не найдено.")
        except Exception:
            update.message.reply_text("Ошибка при удалении события.")
        return

    # FSM-режим
    set_state(user.id, flow="DELETE", step="WAIT_ID", data={})
    update.message.reply_text(
        "Введите ID события для удаления:",
        reply_markup=CANCEL_KB,
    )


def delete_event_process(update, context, state: dict) -> None:
    """
    FSM удаления события:
    1) спрашиваем ID,
    2) удаляем.
    """
    user = update.effective_user
    msg = update.message.text.strip()
    logger.info("FSM DELETE user_id=%s step=%s msg=%s", user.id, state["step"], msg)

    if msg.lower() == "отмена":
        clear_state(user.id)
        update.message.reply_text(
            "Операция отменена.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    if state["step"] == "WAIT_ID":
        try:
            event_id = int(msg)
        except ValueError:
            update.message.reply_text(
                "ID должен быть числом. Введите ID:",
                reply_markup=CANCEL_KB,
            )
            return

        try:
            ok = CALENDAR.delete_event(user.id, event_id)
            if ok:
                update.message.reply_text(
                    "Удалено.",
                    reply_markup=ReplyKeyboardRemove(),
                )
                track_event_cancelled()
            else:
                update.message.reply_text(
                    "Событие не найдено.",
                    reply_markup=ReplyKeyboardRemove(),
                )
        except Exception:
            update.message.reply_text(
                "Ошибка при удалении события.",
                reply_markup=ReplyKeyboardRemove(),
            )
        finally:
            clear_state(user.id)
        return


# ---------------------------------------------------------------------------
# Роутер текстовых сообщений (FSM диспетчер)
# ---------------------------------------------------------------------------

def text_router(update, context) -> None:
    """
    Общий обработчик любых текстовых сообщений.
    Если пользователь сейчас в FSM-сценарии — продолжаем его.
    Если нет — говорим про /help.
    """
    user = update.effective_user
    state = get_state(user.id)
    flow = state["flow"]

    logger.info(
        "TEXT user_id=%s flow=%s step=%s text=%s",
        user.id,
        flow,
        state["step"],
        update.message.text,
    )

    if flow == "CREATE":
        create_event_process(update, context, state)
        return

    if flow == "EDIT":
        edit_event_process(update, context, state)
        return

    if flow == "DELETE":
        delete_event_process(update, context, state)
        return

    update.message.reply_text("Команда не распознана. Используйте /help.")


# ---------------------------------------------------------------------------
# Глобальный обработчик ошибок
# ---------------------------------------------------------------------------

def error_handler(update, context) -> None:
    """
    Логировать непойманные ошибки общего уровня.
    """
    logger.exception("UNHANDLED ERROR: %s (update=%s)", context.error, update)


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Точка входа приложения:
    - создаём Updater;
    - регистрируем хендлеры;
    - запускаем polling.
    """
    updater = Updater(
        token=secrets.API_TOKEN,
        use_context=True,
    )
    dispatcher = updater.dispatcher

    setup_bot_commands(updater)

    # базовые команды
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("register", register_command))
    dispatcher.add_handler(CommandHandler("cancel", cancel_command))

    # операции с событиями
    dispatcher.add_handler(CommandHandler("display_events", display_events_handler))
    dispatcher.add_handler(CommandHandler("read_event", read_event_handler))
    dispatcher.add_handler(CommandHandler("create_event", create_event_start))
    dispatcher.add_handler(CommandHandler("edit_event", edit_event_start_or_inline))
    dispatcher.add_handler(CommandHandler("delete_event", delete_event_start_or_inline))

    # FSM-текст
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, text_router))

    # общий обработчик ошибок
    dispatcher.add_error_handler(error_handler)

    # запуск
    updater.start_polling()
    logger.info(
        "BOT запущен (FSM, статистика, PostgreSQL, Django ORM).",
    )
    updater.idle()


if __name__ == "__main__":
    main()
