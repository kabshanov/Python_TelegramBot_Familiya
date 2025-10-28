"""
tgapp.handlers_events
=====================

Обработчики команд бота и FSM по событиям (CRUD), плюс логин и вывод личного
календаря.

Команды:
- /start, /help, /register, /cancel
- /create_event              — создать событие (FSM-диалог)
- /display_events            — показать мои события (быстрый текстовый вывод)
- /read_event <id>           — показать одно событие
- /edit_event [id msg]       — изменить описание (inline или FSM)
- /delete_event [id]         — удалить событие (inline или FSM)
- /login                     — привязать Telegram-аккаунт к Django-модели TgUser
- /calendar                  — показать личный календарь (через ORM)

FSM-потоки:
- CREATE: WAIT_NAME -> WAIT_DATE -> WAIT_TIME -> WAIT_DETAILS
- EDIT:   WAIT_ID   -> WAIT_NEW_DETAILS
- DELETE: WAIT_ID
- INVITE: FSM-приглашений живёт в tgapp.handlers_appointments (роутим сюда)

Поведение:
- Все пользовательские действия вызывают ensure_profile_from_update(...) —
  профиль TgUser всегда существует (иначе инкременты некуда писать).
- Создание/редактирование/удаление — только для владельца события.
- В любой момент "Отмена" — сброс FSM и клавиатуры.

Зависимости:
- CALENDAR (низкоуровневый слой работы с таблицей events, psycopg2)
- TgUser/счётчики и BotStatistics — через функции из tgapp.core
"""

from __future__ import annotations

from typing import Any, Dict

from telegram import ReplyKeyboardRemove, Update
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, Filters

from calendarapp.utils import get_user_events_qs
from tgapp import handlers_appointments as appt
from tgapp.fsm import clear_state, get_state, parse_date, parse_time, set_state
from tgapp.core import (
    # логгер и инфраструктура
    logger,
    CALENDAR,
    CANCEL_KB,
    # регистрация в слое БД и базовые проверки
    ensure_registered,
    register_in_db_and_track,
    # суточная статистика бота (BotStatistics)
    track_event_created,
    track_event_edited,
    track_event_cancelled,
    # Django-профиль пользователя (TgUser) и личные счётчики
    ensure_tg_user,
    ensure_profile_from_update,
    track_user_event_created,
    track_user_event_edited,
    track_user_event_cancelled,
)

# Тип подсказка для FSM-состояния
StateDict = Dict[str, Any]


# ---------------------------------------------------------------------------
# БАЗОВЫЕ КОМАНДЫ
# ---------------------------------------------------------------------------

def start(update: Update, context: CallbackContext) -> None:
    """
    Показать краткую справку по доступным командам.
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
        "• /delete_event — удалить (диалог) или /delete_event <id>\n\n"
        "Встречи:\n"
        "• /invite — начать приглашение на встречу (диалог)\n\n"
        "Профиль и календарь:\n"
        "• /login — привязать Telegram-аккаунт к системе\n"
        "• /calendar — показать мой личный календарь\n\n"
        "• /cancel — отменить текущую операцию"
    )


def help_command(update: Update, context: CallbackContext) -> None:
    """
    Синоним /start — выводит те же подсказки.
    """
    start(update, context)


def register_command(update: Update, context: CallbackContext) -> None:
    """
    Зарегистрировать пользователя в БД (таблица users, psycopg2) и
    синхронизировать Django-модель TgUser (личный кабинет в админке).

    Повторный вызов — безопасен (идемпотентен).
    """
    ensure_profile_from_update(update)
    user = update.effective_user
    logger.info("/register user_id=%s @%s", user.id, user.username)

    ok_db = True
    try:
        register_in_db_and_track(
            update,
            user_id=user.id,
            username=user.username or "",
            first_name=user.first_name or "",
        )
    except Exception:
        ok_db = False

    # В любом случае держим профиль TgUser в актуальном состоянии
    ensure_tg_user(
        tg_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    if ok_db:
        update.message.reply_text("Регистрация выполнена. Можно работать со своим календарём.")
    else:
        update.message.reply_text(
            "Ваш профиль привязан к системе, но регистрация в таблице users недоступна "
            "(нет прав/нет таблицы). Это не мешает личному календарю и админке."
        )


def cancel_command(update: Update, context: CallbackContext) -> None:
    """
    Отменить текущий FSM-процесс и сбросить состояние пользователя.
    """
    user = update.effective_user
    logger.info("/cancel user_id=%s", user.id)
    clear_state(user.id)
    update.message.reply_text("Операция отменена.", reply_markup=ReplyKeyboardRemove())


# ---------------------------------------------------------------------------
# СОЗДАНИЕ СОБЫТИЯ (FSM)
# ---------------------------------------------------------------------------

def create_event_start(update: Update, context: CallbackContext) -> None:
    """
    Запустить FSM-диалог создания события.
    Порядок: WAIT_NAME -> WAIT_DATE -> WAIT_TIME -> WAIT_DETAILS.
    """
    ensure_profile_from_update(update)
    user = update.effective_user
    logger.info("/create_event start user_id=%s", user.id)

    # Требуем регистрацию (создаёт запись users и профиль TgUser при необходимости)
    if not ensure_registered(
        update,
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
    ):
        return

    set_state(user.id, flow="CREATE", step="WAIT_NAME", data={})
    update.message.reply_text("Введите название события:", reply_markup=CANCEL_KB)


def create_event_process(update: Update, context: CallbackContext, state: StateDict) -> None:
    """
    Обработчик шагов FSM для создания события.
    Последовательно: WAIT_NAME -> WAIT_DATE -> WAIT_TIME -> WAIT_DETAILS.
    """
    user = update.effective_user
    msg = (update.message.text or "").strip()
    step = state["step"]
    data = state["data"]

    # Универсальная отмена
    if msg.lower() == "отмена":
        clear_state(user.id)
        update.message.reply_text("Операция отменена.", reply_markup=ReplyKeyboardRemove())
        return

    # Шаг 1: название
    if step == "WAIT_NAME":
        data["name"] = msg
        set_state(user.id, flow="CREATE", step="WAIT_DATE", data=data)
        update.message.reply_text("Введите дату в формате ГГГГ-ММ-ДД:", reply_markup=CANCEL_KB)
        return

    # Шаг 2: дата
    if step == "WAIT_DATE":
        date_str = parse_date(msg)
        if not date_str:
            update.message.reply_text(
                "Неверный формат даты. Пример: 2025-11-03. Попробуйте ещё раз:",
                reply_markup=CANCEL_KB,
            )
            return
        data["date"] = date_str
        set_state(user.id, flow="CREATE", step="WAIT_TIME", data=data)
        update.message.reply_text("Введите время в формате ЧЧ:ММ (например, 14:30):", reply_markup=CANCEL_KB)
        return

    # Шаг 3: время
    if step == "WAIT_TIME":
        time_str = parse_time(msg)
        if not time_str:
            update.message.reply_text(
                "Неверный формат времени. Пример: 09:05. Попробуйте ещё раз:",
                reply_markup=CANCEL_KB,
            )
            return
        data["time"] = time_str
        set_state(user.id, flow="CREATE", step="WAIT_DETAILS", data=data)
        update.message.reply_text("Введите описание события:", reply_markup=CANCEL_KB)
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
            # Глобальная статистика + личный счётчик
            track_event_created()
            track_user_event_created(user.id)

            update.message.reply_text(
                f"Событие создано. ID: {event_id}",
                reply_markup=ReplyKeyboardRemove(),
            )
        except ValueError as err:
            update.message.reply_text(str(err), reply_markup=ReplyKeyboardRemove())
        except Exception:
            update.message.reply_text("Не удалось создать событие.", reply_markup=ReplyKeyboardRemove())
        finally:
            clear_state(user.id)


# ---------------------------------------------------------------------------
# ПРОСМОТР И ЧТЕНИЕ СОБЫТИЙ
# ---------------------------------------------------------------------------

def display_events_handler(update: Update, context: CallbackContext) -> None:
    """
    Показать список событий пользователя в текстовом виде (через CALENDAR).
    """
    ensure_profile_from_update(update)
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


def read_event_handler(update: Update, context: CallbackContext) -> None:
    """
    Показать одно событие по ID: /read_event <id>.
    Доступ только к собственным событиям пользователя.
    """
    ensure_profile_from_update(update)
    user = update.effective_user
    if not ensure_registered(
        update,
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
    ):
        return

    parts = (update.message.text or "").split(maxsplit=1)
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
# РЕДАКТИРОВАНИЕ СОБЫТИЯ
# ---------------------------------------------------------------------------

def edit_event_start_or_inline(update: Update, context: CallbackContext) -> None:
    """
    Редактирование описания:
    - inline: /edit_event <id> <новое описание>
    - FSM: если параметры не переданы, запускаем диалог (WAIT_ID -> WAIT_NEW_DETAILS).
    """
    ensure_profile_from_update(update)
    user = update.effective_user
    if not ensure_registered(
        update,
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
    ):
        return

    parts = (update.message.text or "").split(maxsplit=2)
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
            if ok:
                track_event_edited()
                track_user_event_edited(user.id)
                update.message.reply_text("Обновлено.")
            else:
                update.message.reply_text("Событие не найдено.")
        except Exception:
            update.message.reply_text("Ошибка при изменении события.")
        return

    # FSM-режим
    set_state(user.id, flow="EDIT", step="WAIT_ID", data={})
    update.message.reply_text("Введите ID события для изменения описания:", reply_markup=CANCEL_KB)


def edit_event_process(update: Update, context: CallbackContext, state: StateDict) -> None:
    """
    FSM-обработчик редактирования: WAIT_ID -> WAIT_NEW_DETAILS.
    С ранней проверкой владения сразу после ввода ID.
    """
    ensure_profile_from_update(update)
    user = update.effective_user
    msg = (update.message.text or "").strip()

    if msg.lower() == "отмена":
        clear_state(user.id)
        update.message.reply_text("Операция отменена.", reply_markup=ReplyKeyboardRemove())
        return

    if state["step"] == "WAIT_ID":
        try:
            event_id = int(msg)
        except ValueError:
            update.message.reply_text("ID должен быть числом. Введите ID:", reply_markup=CANCEL_KB)
            return

        # Ранняя валидация владения: попробуем прочитать событие как своё.
        preview = CALENDAR.read_event(user.id, event_id)
        if not preview:
            update.message.reply_text(
                "Это событие вам не принадлежит или не существует. Укажите свой event_id:",
                reply_markup=CANCEL_KB,
            )
            return

        set_state(user.id, flow="EDIT", step="WAIT_NEW_DETAILS", data={"id": event_id})
        update.message.reply_text("Введите новое описание:", reply_markup=CANCEL_KB)
        return

    if state["step"] == "WAIT_NEW_DETAILS":
        try:
            ok = CALENDAR.edit_event(user.id, state["data"]["id"], msg)
            if ok:
                track_event_edited()
                track_user_event_edited(user.id)
                update.message.reply_text("Обновлено.", reply_markup=ReplyKeyboardRemove())
            else:
                update.message.reply_text("Событие не найдено.", reply_markup=ReplyKeyboardRemove())
        except Exception:
            update.message.reply_text("Ошибка при изменении события.", reply_markup=ReplyKeyboardRemove())
        finally:
            clear_state(user.id)


# ---------------------------------------------------------------------------
# УДАЛЕНИЕ СОБЫТИЯ
# ---------------------------------------------------------------------------

def delete_event_start_or_inline(update: Update, context: CallbackContext) -> None:
    """
    Удаление события:
    - inline: /delete_event <id>
    - FSM: если параметр не указан, запускаем диалог (WAIT_ID).
    """
    ensure_profile_from_update(update)
    user = update.effective_user
    if not ensure_registered(
        update,
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
    ):
        return

    parts = (update.message.text or "").split(maxsplit=1)
    if len(parts) == 2:
        # Одной строкой: /delete_event 15
        try:
            event_id = int(parts[1])
        except ValueError:
            update.message.reply_text("ID должен быть числом.")
            return

        try:
            ok = CALENDAR.delete_event(user.id, event_id)
            if ok:
                track_event_cancelled()
                track_user_event_cancelled(user.id)
                update.message.reply_text("Удалено.")
            else:
                update.message.reply_text("Событие не найдено.")
        except Exception:
            update.message.reply_text("Ошибка при удалении события.")
        return

    # FSM-режим
    set_state(user.id, flow="DELETE", step="WAIT_ID", data={})
    update.message.reply_text("Введите ID события для удаления:", reply_markup=CANCEL_KB)


def delete_event_process(update: Update, context: CallbackContext, state: StateDict) -> None:
    """
    FSM-обработчик удаления: единственный шаг — запрос ID.
    """
    ensure_profile_from_update(update)
    user = update.effective_user
    msg = (update.message.text or "").strip()

    if msg.lower() == "отмена":
        clear_state(user.id)
        update.message.reply_text("Операция отменена.", reply_markup=ReplyKeyboardRemove())
        return

    if state["step"] == "WAIT_ID":
        try:
            event_id = int(msg)
        except ValueError:
            update.message.reply_text("ID должен быть числом. Введите ID:", reply_markup=CANCEL_KB)
            return

        try:
            ok = CALENDAR.delete_event(user.id, event_id)
            if ok:
                track_event_cancelled()
                track_user_event_cancelled(user.id)
                update.message.reply_text("Удалено.", reply_markup=ReplyKeyboardRemove())
            else:
                update.message.reply_text("Событие не найдено.", reply_markup=ReplyKeyboardRemove())
        except Exception:
            update.message.reply_text("Ошибка при удалении события.", reply_markup=ReplyKeyboardRemove())
        finally:
            clear_state(user.id)


# ---------------------------------------------------------------------------
# ЛОГИН И ЛИЧНЫЙ КАЛЕНДАРЬ
# ---------------------------------------------------------------------------

def login_command(update: Update, context: CallbackContext) -> None:
    """
    /login [tg_id?]
    Привязывает пользователя Telegram к Django-модели TgUser.
    Если tg_id не указан, используем ID отправителя.
    """
    ensure_profile_from_update(update)
    u = update.effective_user
    tg_id = u.id

    # Опциональный аргумент игнорируем, если он не совпадает с фактическим ID
    if context.args:
        try:
            arg_id = int(context.args[0])
            if arg_id != tg_id:
                update.message.reply_text(
                    "Можно привязать только свой аккаунт. Использую ваш текущий Telegram ID."
                )
        except ValueError:
            update.message.reply_text(
                "ID должен быть числом. Игнорирую аргумент и использую ваш текущий Telegram ID."
            )

    ensure_tg_user(tg_id, u.username, u.first_name, u.last_name)
    update.message.reply_text(
        "Ваш Telegram-аккаунт привязан к системе. В админке доступен личный кабинет."
    )


def calendar_command(update: Update, context: CallbackContext) -> None:
    """
    /calendar — отправляет пользователю его календарь (события по дате/времени).
    Источник — ORM (calendarapp.Event), отфильтровано по tg_user_id.
    """
    ensure_profile_from_update(update)
    u = update.effective_user
    ensure_tg_user(u.id, u.username, u.first_name, u.last_name)

    try:
        qs = get_user_events_qs(u.id)
        if not qs.exists():
            update.message.reply_text("Ваш календарь пуст.")
            return

        lines = [
            f"[ID {ev.id}] {ev.date} {ev.time} — {ev.name}\n{(ev.details or '').strip()}"
            for ev in qs
        ]
        msg = "Ваши события:\n\n" + "\n\n".join(lines)
        update.message.reply_text(msg)
    except Exception:
        update.message.reply_text("Ошибка при получении календаря.")


# ---------------------------------------------------------------------------
# РОУТЕР ТЕКСТОВ (FSM)
# ---------------------------------------------------------------------------

def text_router(update: Update, context: CallbackContext) -> None:
    """
    Роутер FSM: направляет текст пользователя в нужный обработчик
    в зависимости от активного потока (CREATE/EDIT/DELETE/INVITE).
    Если пользователь вне FSM — напоминаем про /help.
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

    if flow == "INVITE":
        # Передаём управление FSM приглашений в соседний модуль
        appt.invite_process(update, context)
        return

    update.message.reply_text("Команда не распознана. Используйте /help.")


# ---------------------------------------------------------------------------
# РЕГИСТРАЦИЯ ХЕНДЛЕРОВ
# ---------------------------------------------------------------------------

def register(dp) -> None:
    """
    Зарегистрировать все обработчики текущего модуля в Dispatcher.
    Порядок важен: сначала команды, затем общий роутер текстов.
    """
    # Базовые команды
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("register", register_command))
    dp.add_handler(CommandHandler("cancel", cancel_command))

    # CRUD событий
    dp.add_handler(CommandHandler("create_event", create_event_start))
    dp.add_handler(CommandHandler("display_events", display_events_handler))
    dp.add_handler(CommandHandler("read_event", read_event_handler))
    dp.add_handler(CommandHandler("edit_event", edit_event_start_or_inline))
    dp.add_handler(CommandHandler("delete_event", delete_event_start_or_inline))

    # Профиль и календарь
    dp.add_handler(CommandHandler("login", login_command))
    dp.add_handler(CommandHandler("calendar", calendar_command))

    # Роутер текстов для FSM-потоков (последним, чтобы не "съедал" команды)
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, text_router))
