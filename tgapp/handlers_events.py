"""
tgapp.handlers_events
=====================

Блок обработчиков базовых команд и CRUD по событиям:

Команды:
- /start, /help, /register, /cancel
- /create_event  (FSM-диалог)
- /display_events
- /read_event <id>
- /edit_event    (FSM-диалог) или /edit_event <id> <новое описание>
- /delete_event  (FSM-диалог) или /delete_event <id>

FSM-потоки:
- CREATE: по шагам собираем (name -> date -> time -> details).
- EDIT:   по шагам (id -> new_details), если не указанно inline.
- DELETE: по шагам (id), если не указанно inline.
- INVITE: управляется в tgapp.handlers_appointments; здесь только ветка
  в text_router для передачи обработки.

Примечание:
- Все операции завязаны на регистрацию пользователя (/register).
- Для отмены любого диалога пользователь может отправить "Отмена".
"""

from __future__ import annotations

from typing import Any, Dict

from telegram import ReplyKeyboardRemove

from tgapp.core import (
    logger,
    CALENDAR,
    CANCEL_KB,
    ensure_registered,
    register_in_db_and_track,
    track_event_created,
    track_event_edited,
    track_event_cancelled,
)
from tgapp.fsm import (
    get_state,
    set_state,
    clear_state,
    parse_date,
    parse_time,
)

# Чтобы роутер мог передать сообщения в FSM приглашений:
from tgapp import handlers_appointments as appt


# Тип подсказка для состояния FSM
StateDict = Dict[str, Any]


# ---------------------------------------------------------------------------
# Базовые команды
# ---------------------------------------------------------------------------

def start(update: Any, context: Any) -> None:
    """
    Показать краткую справку по доступным командам.

    :param update: объект апдейта Telegram
    :param context: контекст выполнения хендлера
    """
    user = update.effective_user
    logger.info("/start user_id=%s @%s", user.id, user.username)
    update.message.reply_text(
        "Календарь-бот.\n\n"
        "Регистрация:\n"
        "• /register — создать учётную запись\n\n"
        "События:\n"
        "• /create_event — создать событие (диалог)\n"
        "• /display_events — показать мои события\n"
        "• /read_event <id> — показать событие по ID\n"
        "• /edit_event — изменить описание (диалог) или /edit_event <id> <новое>\n"
        "• /delete_event — удалить (диалог) или /delete_event <id>\n"
        "• /invite — диалог приглашения на встречу\n"
        "• /cancel — отменить текущую операцию\n"
    )


def help_command(update: Any, context: Any) -> None:
    """
    Синоним /start — выводит те же подсказки.
    """
    start(update, context)


def register_command(update: Any, context: Any) -> None:
    """
    Зарегистрировать пользователя в БД (users).
    Повторный вызов — безопасен (идемпотентен).

    :param update: объект апдейта Telegram
    :param context: контекст выполнения хендлера
    """
    user = update.effective_user
    logger.info("/register user_id=%s @%s", user.id, user.username)
    try:
        register_in_db_and_track(
            update,
            user_id=user.id,
            username=user.username or "",
            first_name=user.first_name or "",
        )
    except Exception:
        update.message.reply_text(
            "Ошибка регистрации (проверьте права на таблицу users)."
        )


def cancel_command(update: Any, context: Any) -> None:
    """
    Отменить текущий FSM-процесс и сбросить состояние пользователя.

    :param update: объект апдейта Telegram
    :param context: контекст выполнения хендлера
    """
    user = update.effective_user
    logger.info("/cancel user_id=%s", user.id)
    clear_state(user.id)
    update.message.reply_text(
        "Операция отменена.",
        reply_markup=ReplyKeyboardRemove(),
    )


# ---------------------------------------------------------------------------
# Создание события (FSM)
# ---------------------------------------------------------------------------

def create_event_start(update: Any, context: Any) -> None:
    """
    Запустить FSM-диалог создания события.
    Сначала проверяем регистрацию, затем спрашиваем название события.

    :param update: объект апдейта Telegram
    :param context: контекст выполнения хендлера
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
    update.message.reply_text("Введите название события:", reply_markup=CANCEL_KB)


def create_event_process(update: Any, context: Any, state: StateDict) -> None:
    """
    Обработчик шагов FSM для создания события.

    Последовательно собираем:
    WAIT_NAME -> WAIT_DATE -> WAIT_TIME -> WAIT_DETAILS.

    :param update: объект апдейта Telegram
    :param context: контекст выполнения хендлера
    :param state: текущее состояние FSM пользователя
    """
    user = update.effective_user
    msg = update.message.text.strip()
    step = state["step"]
    data = state["data"]

    # Универсальная отмена диалога
    if msg.lower() == "отмена":
        clear_state(user.id)
        update.message.reply_text(
            "Операция отменена.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    # Шаг 1: название события
    if step == "WAIT_NAME":
        data["name"] = msg
        set_state(user.id, flow="CREATE", step="WAIT_DATE", data=data)
        update.message.reply_text(
            "Введите дату в формате ГГГГ-ММ-ДД:",
            reply_markup=CANCEL_KB,
        )
        return

    # Шаг 2: дата
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

    # Шаг 3: время
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

    # Шаг 4: детали -> создание
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
            track_event_created()
        except ValueError as err:
            update.message.reply_text(str(err), reply_markup=ReplyKeyboardRemove())
        except Exception:
            update.message.reply_text(
                "Не удалось создать событие.",
                reply_markup=ReplyKeyboardRemove(),
            )
        finally:
            clear_state(user.id)


# ---------------------------------------------------------------------------
# Просмотр и чтение событий
# ---------------------------------------------------------------------------

def display_events_handler(update: Any, context: Any) -> None:
    """
    Показать список событий пользователя в текстовом виде.

    :param update: объект апдейта Telegram
    :param context: контекст выполнения хендлера
    """
    user = update.effective_user
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


def read_event_handler(update: Any, context: Any) -> None:
    """
    Показать одно событие по ID: /read_event <id>.

    :param update: объект апдейта Telegram
    :param context: контекст выполнения хендлера
    """
    user = update.effective_user
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

def edit_event_start_or_inline(update: Any, context: Any) -> None:
    """
    Редактирование описания:
    - inline-режим: /edit_event <id> <новое описание>
    - FSM-режим: если параметры не переданы, запускаем диалог.

    :param update: объект апдейта Telegram
    :param context: контекст выполнения хендлера
    """
    user = update.effective_user
    if not ensure_registered(
        update,
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
    ):
        return

    parts = update.message.text.split(maxsplit=2)
    if len(parts) >= 3:
        # Одной строкой: /edit_event 15 Новый текст
        try:
            event_id = int(parts[1])
        except ValueError:
            update.message.reply_text("ID должен быть числом.")
            return

        new_text = parts[2]
        try:
            ok = CALENDAR.edit_event(user.id, event_id, new_text)
            update.message.reply_text("Обновлено." if ok else "Событие не найдено.")
            if ok:
                track_event_edited()
        except Exception:
            update.message.reply_text("Ошибка при изменении события.")
        return

    # FSM-режим
    set_state(user.id, flow="EDIT", step="WAIT_ID", data={})
    update.message.reply_text(
        "Введите ID события для изменения описания:",
        reply_markup=CANCEL_KB,
    )


def edit_event_process(update: Any, context: Any, state: StateDict) -> None:
    """
    FSM-обработчик редактирования:
    WAIT_ID -> WAIT_NEW_DETAILS.

    :param update: объект апдейта Telegram
    :param context: контекст выполнения хендлера
    :param state: текущее состояние FSM пользователя
    """
    user = update.effective_user
    msg = update.message.text.strip()

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
        update.message.reply_text("Введите новое описание:", reply_markup=CANCEL_KB)
        return

    if state["step"] == "WAIT_NEW_DETAILS":
        try:
            ok = CALENDAR.edit_event(user.id, state["data"]["id"], msg)
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


# ---------------------------------------------------------------------------
# Удаление события
# ---------------------------------------------------------------------------

def delete_event_start_or_inline(update: Any, context: Any) -> None:
    """
    Удаление события:
    - inline-режим: /delete_event <id>
    - FSM-режим: если параметр не указан, запускаем диалог.

    :param update: объект апдейта Telegram
    :param context: контекст выполнения хендлера
    """
    user = update.effective_user
    if not ensure_registered(
        update,
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
    ):
        return

    parts = update.message.text.split(maxsplit=1)
    if len(parts) == 2:
        # Одной строкой: /delete_event 15
        try:
            event_id = int(parts[1])
        except ValueError:
            update.message.reply_text("ID должен быть числом.")
            return

        try:
            ok = CALENDAR.delete_event(user.id, event_id)
            update.message.reply_text("Удалено." if ok else "Событие не найдено.")
            if ok:
                track_event_cancelled()
        except Exception:
            update.message.reply_text("Ошибка при удалении события.")
        return

    # FSM-режим
    set_state(user.id, flow="DELETE", step="WAIT_ID", data={})
    update.message.reply_text(
        "Введите ID события для удаления:",
        reply_markup=CANCEL_KB,
    )


def delete_event_process(update: Any, context: Any, state: StateDict) -> None:
    """
    FSM-обработчик удаления: единственный шаг — запрос ID.

    :param update: объект апдейта Telegram
    :param context: контекст выполнения хендлера
    :param state: текущее состояние FSM пользователя
    """
    user = update.effective_user
    msg = update.message.text.strip()

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


# ---------------------------------------------------------------------------
# Роутер текстовых сообщений (FSM)
# ---------------------------------------------------------------------------

def text_router(update: Any, context: Any) -> None:
    """
    Роутер FSM: направляет текст пользователя в нужный обработчик
    в зависимости от активного потока (CREATE/EDIT/DELETE/INVITE).

    :param update: объект апдейта Telegram
    :param context: контекст выполнения хендлера
    """
    user = update.effective_user
    state = get_state(user.id)
    flow = state["flow"]

    if flow == "CREATE":
        create_event_process(update, context, state)
        return

    if flow == "EDIT":
        edit_event_process(update, context, state)
        return

    if flow == "DELETE":
        delete_event_process(update, context, state)
        return

    # новая ветка — передаём обработку FSM-приглашения в другой модуль
    if flow == "INVITE":
        appt.invite_process(update, context)
        return

    # Если пользователь не в FSM — подскажем команды
    update.message.reply_text("Команда не распознана. Используйте /help.")
