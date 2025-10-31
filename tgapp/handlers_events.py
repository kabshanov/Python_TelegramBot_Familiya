"""
tgapp.handlers_events
=====================

Обработчики команд бота и FSM по событиям (CRUD), логин/календарь,
публикация событий (Task 5) и экспорт (Task 6).

Команды:
- /start, /help, /register, /cancel
- /create_event                — создать событие (FSM)
- /display_events              — показать мои события (через CALENDAR)
- /read_event <id>             — показать одно событие
- /edit_event [id msg]         — изменить описание (inline или FSM)
- /delete_event [id]           — удалить событие (inline или FSM)
- /login                       — привязать TG-аккаунт к Django-модели TgUser
- /calendar                    — показать личный календарь (ORM)
- /share_event                 — сделать событие публичным (FSM по ID)
- /my_public                   — список моих публичных событий
- /public_of                   — список публичных событий другого TG-пользователя (FSM)
- /export                      — кнопки-ссылки CSV/JSON на Django-эндпоинт экспорта

FSM-потоки:
- CREATE:    WAIT_NAME -> WAIT_DATE -> WAIT_TIME -> WAIT_DETAILS
- EDIT:      WAIT_ID   -> WAIT_NEW_DETAILS
- DELETE:    WAIT_ID
- INVITE:    (в tgapp.handlers_appointments)
- SHARE_PUBLIC: WAIT_EVENT_ID
- PUBLIC_OF:    WAIT_TG_ID
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List
from urllib.parse import quote_plus

from django.conf import settings
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, Filters


from calendarapp.models import Event
from calendarapp.utils import make_export_token

from tgapp import handlers_appointments as appt
from tgapp.fsm import clear_state, get_state, parse_date, parse_time, set_state
from tgapp.core import (
    logger,                 # общий логгер приложения
    CALENDAR,               # слой работы с БД (psycopg2)
    CANCEL_KB,              # ReplyKeyboard с «Отмена»
    ensure_registered,      # проверка/регистрация в users (psycopg2)
    register_in_db_and_track,
    track_event_created,    # суточная статистика бота
    track_event_edited,
    track_event_cancelled,
    ensure_tg_user,         # Django-профиль TgUser
    ensure_profile_from_update,
    track_user_event_created,
    track_user_event_edited,
    track_user_event_cancelled,
)

StateDict = Dict[str, Any]
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Вспомогалки (форматирование, inline-отмена)
# ---------------------------------------------------------------------------

def _format_events_for_message(rows: Iterable[Event]) -> str:
    """
    Сформировать удобный список событий для пользователя.
    Формат: "[ID 1] 2025-12-12 12:30 — Название\nОписание"
    """
    lines: List[str] = []
    for ev in rows:
        details = (ev.details or "").strip()
        base = f"[ID {ev.id}] {ev.date} {ev.time} — {ev.name}"
        lines.append(base if not details else f"{base}\n{details}")
    return "\n\n".join(lines)


def _inline_cancel_kb() -> InlineKeyboardMarkup:
    """Единая inline-кнопка «Отмена» для FSM."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Отмена", callback_data="fsm:cancel")]]
    )


def _send_with_inline_cancel(update: Update, text: str) -> None:
    """Отправить сообщение с inline-кнопкой «Отмена»."""
    update.message.reply_text(text, reply_markup=_inline_cancel_kb())


def fsm_cancel_callback(update: Update, context: CallbackContext) -> None:
    """
    Обработчик inline-«Отмена» (callback_data='fsm:cancel').
    Сбрасывает состояние и аккуратно подтверждает в чате.
    """
    q = update.callback_query
    try:
        if q:
            user_id = q.from_user.id
            clear_state(user_id)
            q.answer("Отменено")
            q.edit_message_text("Операция отменена.")
            log.info("FSM cancel via inline: user_id=%s", user_id)
        else:
            user = update.effective_user
            clear_state(user.id)
            update.effective_message.reply_text(
                "Операция отменена.", reply_markup=ReplyKeyboardRemove()
            )
            log.info("FSM cancel via message: user_id=%s", user.id)
    except Exception:
        log.exception("fsm_cancel_callback error")


# ---------------------------------------------------------------------------
# БАЗОВЫЕ КОМАНДЫ
# ---------------------------------------------------------------------------

def start(update: Update, context: CallbackContext) -> None:
    """Краткая справка по командам."""
    user = update.effective_user
    log.info("/start user_id=%s @%s", user.id, user.username)
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
        "Публикация и экспорт:\n"
        "• /share_event — сделать событие публичным (по ID)\n"
        "• /my_public — мои публичные события\n"
        "• /public_of — публичные события другого пользователя\n"
        "• /export — выгрузка CSV/JSON\n\n"
        "Встречи:\n"
        "• /invite — приглашение на встречу (диалог)\n\n"
        "Профиль и календарь:\n"
        "• /login — привязать Telegram-аккаунт к системе\n"
        "• /calendar — показать мой личный календарь\n\n"
        "• /cancel — отменить текущую операцию"
    )


def help_command(update: Update, context: CallbackContext) -> None:
    """Синоним /start — выводит те же подсказки."""
    start(update, context)


def register_command(update: Update, context: CallbackContext) -> None:
    """
    Зарегистрировать пользователя в БД (users, psycopg2) и
    синхронизировать Django-модель TgUser.
    Повторный вызов — безопасен.
    """
    ensure_profile_from_update(update)
    user = update.effective_user
    log.info("/register user_id=%s @%s", user.id, user.username)

    ok_db = True
    try:
        register_in_db_and_track(
            update,
            user_id=user.id,
            username=user.username or "",
            first_name=user.first_name or "",
        )
        log.info("users-table ensured/updated for user_id=%s", user.id)
    except Exception:
        ok_db = False
        log.exception("register_in_db_and_track failed for user_id=%s", user.id)

    try:
        ensure_tg_user(
            tg_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )
        log.info("TgUser ensured for user_id=%s", user.id)
    except Exception:
        log.exception("ensure_tg_user failed for user_id=%s", user.id)

    if ok_db:
        update.message.reply_text("Регистрация выполнена. Можно работать со своим календарём.")
    else:
        update.message.reply_text(
            "Профиль создан. Таблица пользователей недоступна — это не мешает личному календарю и админке."
        )


def cancel_command(update: Update, context: CallbackContext) -> None:
    """Отменить текущий FSM-процесс и сбросить состояние пользователя."""
    user = update.effective_user
    clear_state(user.id)
    log.info("/cancel user_id=%s", user.id)
    update.message.reply_text("Операция отменена.", reply_markup=ReplyKeyboardRemove())


# ---------------------------------------------------------------------------
# СОЗДАНИЕ СОБЫТИЯ (FSM)
# ---------------------------------------------------------------------------

def create_event_start(update: Update, context: CallbackContext) -> None:
    """Запуск FSM-диалога создания события."""
    ensure_profile_from_update(update)
    user = update.effective_user
    log.info("/create_event start user_id=%s", user.id)

    if not ensure_registered(
        update,
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
    ):
        log.warning("create_event denied: user not registered user_id=%s", user.id)
        return

    set_state(user.id, flow="CREATE", step="WAIT_NAME", data={})
    update.message.reply_text("Введите название события:", reply_markup=CANCEL_KB)


def create_event_process(update: Update, context: CallbackContext, state: StateDict) -> None:
    """Шаги FSM: WAIT_NAME -> WAIT_DATE -> WAIT_TIME -> WAIT_DETAILS."""
    user = update.effective_user
    msg = (update.message.text or "").strip()
    step = state["step"]
    data = state["data"]
    log.debug("CREATE step=%s user_id=%s msg=%r", step, user.id, msg)

    if msg.lower() == "отмена":
        clear_state(user.id)
        update.message.reply_text("Операция отменена.", reply_markup=ReplyKeyboardRemove())
        log.info("CREATE cancelled user_id=%s", user.id)
        return

    if step == "WAIT_NAME":
        data["name"] = msg
        set_state(user.id, flow="CREATE", step="WAIT_DATE", data=data)
        update.message.reply_text("Введите дату в формате ГГГГ-ММ-ДД:", reply_markup=CANCEL_KB)
        return

    if step == "WAIT_DATE":
        date_str = parse_date(msg)
        if not date_str:
            update.message.reply_text(
                "Неверный формат даты. Пример: 2025-12-03. Попробуйте ещё раз:",
                reply_markup=CANCEL_KB,
            )
            return
        data["date"] = date_str
        set_state(user.id, flow="CREATE", step="WAIT_TIME", data=data)
        update.message.reply_text("Введите время в формате ЧЧ:ММ (например, 14:30):", reply_markup=CANCEL_KB)
        return

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
            track_event_created()
            track_user_event_created(user.id)
            update.message.reply_text(
                f"Событие создано. ID: {event_id}",
                reply_markup=ReplyKeyboardRemove(),
            )
            log.info("CREATE done user_id=%s event_id=%s", user.id, event_id)
        except ValueError as err:
            update.message.reply_text(str(err), reply_markup=ReplyKeyboardRemove())
            log.warning("CREATE validation error user_id=%s err=%s", user.id, err)
        except Exception:
            update.message.reply_text("Не удалось создать событие.", reply_markup=ReplyKeyboardRemove())
            log.exception("CREATE failed user_id=%s", user.id)
        finally:
            clear_state(user.id)


# ---------------------------------------------------------------------------
# ПРОСМОТР И ЧТЕНИЕ СОБЫТИЙ
# ---------------------------------------------------------------------------

def display_events_handler(update: Update, context: CallbackContext) -> None:
    """Показать список событий пользователя (через CALENDAR)."""
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
        res = CALENDAR.display_events(user.id)
        update.message.reply_text(res)
        log.info("DISPLAY_EVENTS ok user_id=%s", user.id)
    except Exception:
        update.message.reply_text("Ошибка при получении списка событий.")
        log.exception("DISPLAY_EVENTS failed user_id=%s", user.id)


def read_event_handler(update: Update, context: CallbackContext) -> None:
    """Показать одно событие по ID. Доступ только к своим событиям."""
    ensure_profile_from_update(update)
    user = update.effective_user

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
        log.info("READ_EVENT ok user_id=%s event_id=%s", user.id, event_id)
    except Exception:
        update.message.reply_text("Ошибка при чтении события.")
        log.exception("READ_EVENT failed user_id=%s event_id=%s", user.id, event_id)


# ---------------------------------------------------------------------------
# РЕДАКТИРОВАНИЕ СОБЫТИЯ
# ---------------------------------------------------------------------------

def edit_event_start_or_inline(update: Update, context: CallbackContext) -> None:
    """
    Редактирование описания:
    - inline: /edit_event <id> <новое описание>
    - FSM: если параметры не переданы, WAIT_ID -> WAIT_NEW_DETAILS.
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
                update.message.reply_text("Описание обновлено.")
                log.info("EDIT inline ok user_id=%s event_id=%s", user.id, event_id)
            else:
                update.message.reply_text("Событие не найдено.")
                log.info("EDIT inline not_found user_id=%s event_id=%s", user.id, event_id)
        except Exception:
            update.message.reply_text("Ошибка при изменении события.")
            log.exception("EDIT inline failed user_id=%s event_id=%s", user.id, event_id)
        return

    set_state(user.id, flow="EDIT", step="WAIT_ID", data={})
    update.message.reply_text("Введите ID события для изменения описания:", reply_markup=CANCEL_KB)


def edit_event_process(update: Update, context: CallbackContext, state: StateDict) -> None:
    """FSM: WAIT_ID -> WAIT_NEW_DETAILS."""
    ensure_profile_from_update(update)
    user = update.effective_user
    msg = (update.message.text or "").strip()
    log.debug("EDIT step=%s user_id=%s msg=%r", state["step"], user.id, msg)

    if msg.lower() == "отмена":
        clear_state(user.id)
        update.message.reply_text("Операция отменена.", reply_markup=ReplyKeyboardRemove())
        log.info("EDIT cancelled user_id=%s", user.id)
        return

    if state["step"] == "WAIT_ID":
        try:
            event_id = int(msg)
        except ValueError:
            update.message.reply_text("ID должен быть числом. Введите ID:", reply_markup=CANCEL_KB)
            return

        preview = CALENDAR.read_event(user.id, event_id)
        if not preview:
            update.message.reply_text(
                "Это событие вам не принадлежит или не существует. Укажите свой event_id:",
                reply_markup=CANCEL_KB,
            )
            log.info("EDIT wrong_owner/not_found user_id=%s event_id=%s", user.id, event_id)
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
                update.message.reply_text("Описание обновлено.", reply_markup=ReplyKeyboardRemove())
                log.info("EDIT done user_id=%s event_id=%s", user.id, state["data"]["id"])
            else:
                update.message.reply_text("Событие не найдено.", reply_markup=ReplyKeyboardRemove())
                log.info("EDIT not_found user_id=%s event_id=%s", user.id, state["data"]["id"])
        except Exception:
            update.message.reply_text("Ошибка при изменении события.", reply_markup=ReplyKeyboardRemove())
            log.exception("EDIT failed user_id=%s event_id=%s", user.id, state["data"]["id"])
        finally:
            clear_state(user.id)


# ---------------------------------------------------------------------------
# УДАЛЕНИЕ СОБЫТИЯ
# ---------------------------------------------------------------------------

def delete_event_start_or_inline(update: Update, context: CallbackContext) -> None:
    """
    Удаление события:
    - inline: /delete_event <id>
    - FSM: если параметр не указан, WAIT_ID.
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
                update.message.reply_text("Событие удалено.")
                log.info("DELETE inline ok user_id=%s event_id=%s", user.id, event_id)
            else:
                update.message.reply_text("Событие не найдено.")
                log.info("DELETE inline not_found user_id=%s event_id=%s", user.id, event_id)
        except Exception:
            update.message.reply_text("Ошибка при удалении события.")
            log.exception("DELETE inline failed user_id=%s event_id=%s", user.id, event_id)
        return

    set_state(user.id, flow="DELETE", step="WAIT_ID", data={})
    update.message.reply_text("Введите ID события для удаления:", reply_markup=CANCEL_KB)


def delete_event_process(update: Update, context: CallbackContext, state: StateDict) -> None:
    """FSM: единственный шаг — запрос ID."""
    ensure_profile_from_update(update)
    user = update.effective_user
    msg = (update.message.text or "").strip()
    log.debug("DELETE step=%s user_id=%s msg=%r", state["step"], user.id, msg)

    if msg.lower() == "отмена":
        clear_state(user.id)
        update.message.reply_text("Операция отменена.", reply_markup=ReplyKeyboardRemove())
        log.info("DELETE cancelled user_id=%s", user.id)
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
                update.message.reply_text("Событие удалено.", reply_markup=ReplyKeyboardRemove())
                log.info("DELETE done user_id=%s event_id=%s", user.id, event_id)
            else:
                update.message.reply_text("Событие не найдено.", reply_markup=ReplyKeyboardRemove())
                log.info("DELETE not_found user_id=%s event_id=%s", user.id, event_id)
        except Exception:
            update.message.reply_text("Ошибка при удалении события.", reply_markup=ReplyKeyboardRemove())
            log.exception("DELETE failed user_id=%s event_id=%s", user.id, event_id)
        finally:
            clear_state(user.id)


# ---------------------------------------------------------------------------
# ЛОГИН И ЛИЧНЫЙ КАЛЕНДАРЬ
# ---------------------------------------------------------------------------

def login_command(update: Update, context: CallbackContext) -> None:
    """
    /login [tg_id?] — привязка Telegram-аккаунта к Django-модели TgUser.
    Если tg_id не указан, используется ID отправителя.
    """
    ensure_profile_from_update(update)
    u = update.effective_user

    if context.args:
        try:
            arg_id = int(context.args[0])
            if arg_id != u.id:
                update.message.reply_text(
                    "Можно привязать только свой аккаунт. Использую ваш текущий Telegram ID."
                )
        except ValueError:
            update.message.reply_text(
                "ID должен быть числом. Игнорирую аргумент и использую ваш Telegram ID."
            )

    try:
        ensure_tg_user(u.id, u.username, u.first_name, u.last_name)
        update.message.reply_text(
            "Готово — ваш Telegram-аккаунт привязан. В админке доступен личный кабинет."
        )
        log.info("LOGIN ok user_id=%s", u.id)
    except Exception:
        update.message.reply_text("Не удалось привязать аккаунт.")
        log.exception("LOGIN failed user_id=%s", u.id)


def calendar_command(update: Update, context: CallbackContext) -> None:
    """/calendar — показать личный календарь (ORM Event), фильтр по user_id."""
    ensure_profile_from_update(update)
    u = update.effective_user
    ensure_tg_user(u.id, u.username, u.first_name, u.last_name)

    try:
        qs = Event.objects.filter(user_id=u.id).order_by("date", "time", "id")
        if not qs.exists():
            update.message.reply_text("Ваш календарь пуст.")
            log.info("CALENDAR empty user_id=%s", u.id)
            return

        msg = "Ваши события:\n\n" + _format_events_for_message(qs)
        update.message.reply_text(msg)
        log.info("CALENDAR ok user_id=%s count=%s", u.id, qs.count())
    except Exception:
        update.message.reply_text("Ошибка при получении календаря.")
        log.exception("CALENDAR failed user_id=%s", u.id)


# ---------------------------------------------------------------------------
# ПУБЛИКАЦИЯ (Task 5)
# ---------------------------------------------------------------------------

def share_event_start(update: Update, context: CallbackContext) -> None:
    """/share_event — FSM: спросить ID события и сделать его публичным."""
    ensure_profile_from_update(update)
    u = update.effective_user

    if not ensure_registered(update, user_id=u.id, username=u.username or "", first_name=u.first_name or ""):
        return

    set_state(u.id, flow="SHARE_PUBLIC", step="WAIT_EVENT_ID", data={})
    _send_with_inline_cancel(update, "Введите ID события, которое хотите сделать публичным.")
    log.info("SHARE start user_id=%s", u.id)


def share_public_process(update: Update, context: CallbackContext, state: StateDict) -> None:
    """FSM: получить ID, проверить владение, поставить is_public=True (ORM)."""
    u = update.effective_user
    msg = (update.message.text or "").strip()
    log.debug("SHARE step=%s user_id=%s msg=%r", state["step"], u.id, msg)

    if msg.lower() == "отмена":
        clear_state(u.id)
        update.message.reply_text("Операция отменена.", reply_markup=ReplyKeyboardRemove())
        log.info("SHARE cancelled user_id=%s", u.id)
        return

    if state["step"] == "WAIT_EVENT_ID":
        try:
            event_id = int(msg)
        except ValueError:
            update.message.reply_text("ID должен быть числом. Введите ID:", reply_markup=_inline_cancel_kb())
            return

        try:
            updated = Event.objects.filter(id=event_id, user_id=u.id).update(is_public=True)
            if updated:
                update.message.reply_text(
                    "Готово: событие теперь видно другим. "
                    "Посмотреть список своих публичных событий — /my_public."
                )
                log.info("SHARE ok user_id=%s event_id=%s", u.id, event_id)
            else:
                update.message.reply_text("Событие не найдено или не принадлежит вам.")
                log.info("SHARE not_found/forbidden user_id=%s event_id=%s", u.id, event_id)
        except Exception:
            update.message.reply_text("Не удалось изменить видимость события.")
            log.exception("SHARE failed user_id=%s event_id=%s", u.id, event_id)
        finally:
            clear_state(u.id)


def list_my_public_command(update: Update, context: CallbackContext) -> None:
    """/my_public — вывести список публичных событий текущего пользователя."""
    ensure_profile_from_update(update)
    u = update.effective_user
    ensure_tg_user(u.id, u.username, u.first_name, u.last_name)

    try:
        qs = Event.objects.filter(user_id=u.id, is_public=True).order_by("date", "time", "id")
        if not qs.exists():
            update.message.reply_text("У вас нет публичных событий.")
            log.info("MY_PUBLIC empty user_id=%s", u.id)
            return
        update.message.reply_text("Ваши публичные события:\n\n" + _format_events_for_message(qs))
        log.info("MY_PUBLIC ok user_id=%s count=%s", u.id, qs.count())
    except Exception:
        update.message.reply_text("Ошибка при получении публичных событий.")
        log.exception("MY_PUBLIC failed user_id=%s", u.id)


def public_of_start(update: Update, context: CallbackContext) -> None:
    """/public_of — FSM: спросить tg_id пользователя для просмотра его публичных событий."""
    ensure_profile_from_update(update)
    u = update.effective_user
    ensure_tg_user(u.id, u.username, u.first_name, u.last_name)

    set_state(u.id, flow="PUBLIC_OF", step="WAIT_TG_ID", data={})
    _send_with_inline_cancel(update, "Введите Telegram ID пользователя, чьи публичные события хотите посмотреть.")
    log.info("PUBLIC_OF start user_id=%s", u.id)


def public_of_process(update: Update, context: CallbackContext, state: StateDict) -> None:
    """FSM: получить tg_id и вывести публичные события."""
    u = update.effective_user
    msg = (update.message.text or "").strip()
    log.debug("PUBLIC_OF step=%s user_id=%s msg=%r", state["step"], u.id, msg)

    if msg.lower() == "отмена":
        clear_state(u.id)
        update.message.reply_text("Операция отменена.", reply_markup=ReplyKeyboardRemove())
        log.info("PUBLIC_OF cancelled user_id=%s", u.id)
        return

    if state["step"] == "WAIT_TG_ID":
        try:
            target_id = int(msg)
        except ValueError:
            update.message.reply_text("ID должен быть числом. Введите Telegram ID:", reply_markup=_inline_cancel_kb())
            return

        try:
            qs = Event.objects.filter(user_id=target_id, is_public=True).order_by("date", "time", "id")
            if not qs.exists():
                update.message.reply_text("У пользователя нет публичных событий.")
                log.info("PUBLIC_OF empty user_id=%s target_id=%s", u.id, target_id)
            else:
                update.message.reply_text("Публичные события пользователя:\n\n" + _format_events_for_message(qs))
                log.info("PUBLIC_OF ok user_id=%s target_id=%s count=%s", u.id, target_id, qs.count())
        except Exception:
            update.message.reply_text("Ошибка при получении публичных событий.")
            log.exception("PUBLIC_OF failed user_id=%s target_id=%s", u.id, target_id)
        finally:
            clear_state(u.id)


# ---------------------------------------------------------------------------
# ЭКСПОРТ (Task 6)
# ---------------------------------------------------------------------------

def export_command(update: Update, context: CallbackContext) -> None:
    """
    /export — выдаёт пользователю две ссылки-кнопки для скачивания:
      — CSV
      — JSON
    Ссылки включают подписанный токен и действуют ограниченное время (настройка).
    """
    ensure_profile_from_update(update)
    u = update.effective_user
    ensure_tg_user(u.id, u.username, u.first_name, u.last_name)

    try:
        token = make_export_token(u.id)
        q = quote_plus(token)
        base = getattr(settings, "SITE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
        url_csv = f"{base}/export/csv/?token={q}"
        url_json = f"{base}/export/json/?token={q}"

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬇️ CSV", url=url_csv)],
            [InlineKeyboardButton("⬇️ JSON", url=url_json)],
        ])
        update.message.reply_text(
            "Экспорт календаря:\n"
            f"• ссылка активна ~{getattr(settings, 'EXPORT_TOKEN_MAX_AGE', 900)} сек.\n"
            "• выгрузка откроется в браузере.",
            reply_markup=kb,
        )
        log.info("EXPORT links sent user_id=%s", u.id)
    except Exception:
        update.message.reply_text("Не удалось сформировать ссылки на выгрузку.")
        log.exception("EXPORT failed user_id=%s", u.id)


# ---------------------------------------------------------------------------
# РОУТЕР ТЕКСТОВ (FSM)
# ---------------------------------------------------------------------------

def text_router(update: Update, context: CallbackContext) -> None:
    """
    Роутер FSM: направляет текст пользователя в нужный обработчик
    в зависимости от активного потока (CREATE/EDIT/DELETE/INVITE/SHARE_PUBLIC/PUBLIC_OF).
    Если пользователь вне FSM — напоминаем про /help.
    """
    user = update.effective_user
    state = get_state(user.id)
    flow = state["flow"]
    log.debug("text_router user_id=%s flow=%s step=%s", user.id, flow, state["step"])

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
        appt.invite_process(update, context)
        return
    if flow == "SHARE_PUBLIC":
        share_public_process(update, context, state)
        return
    if flow == "PUBLIC_OF":
        public_of_process(update, context, state)
        return

    update.message.reply_text("Команда не распознана. Используйте /help.")


# ---------------------------------------------------------------------------
# Регистрация (если нужно регать тут)
# ---------------------------------------------------------------------------

def register(dp) -> None:
    """Опциональная регистрация обработчиков на Dispatcher."""
    # Базовые
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("register", register_command))
    dp.add_handler(CommandHandler("cancel", cancel_command))

    # CRUD
    dp.add_handler(CommandHandler("create_event", create_event_start))
    dp.add_handler(CommandHandler("display_events", display_events_handler))
    dp.add_handler(CommandHandler("read_event", read_event_handler))
    dp.add_handler(CommandHandler("edit_event", edit_event_start_or_inline))
    dp.add_handler(CommandHandler("delete_event", delete_event_start_or_inline))

    # Профиль/календарь
    dp.add_handler(CommandHandler("login", login_command))
    dp.add_handler(CommandHandler("calendar", calendar_command))

    # Публикация и экспорт
    dp.add_handler(CommandHandler("share_event", share_event_start))
    dp.add_handler(CommandHandler("my_public", list_my_public_command))
    dp.add_handler(CommandHandler("public_of", public_of_start))
    dp.add_handler(CommandHandler("export", export_command))

    # FSM-роутер
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, text_router))
