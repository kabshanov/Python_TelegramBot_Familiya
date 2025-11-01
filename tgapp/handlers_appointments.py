"""
tgapp/handlers_appointments.py
===========================

FSM-приглашения на встречу:

1) /invite — старт диалога.
2) Шаг 1: запрос TG ID участника.
3) Шаг 2: запрос ID события организатора.
4) Шаг 3: запрос деталей (необязательно, можно "Пропустить").
5) Отправка приглашения участнику с инлайн-кнопками:
   - ✅ Подтвердить
   - ❌ Отклонить

Обработка нажатий кнопок меняет статус Appointment и уведомляет организатора.
"""

from __future__ import annotations

from typing import Any, Optional, Tuple

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove

from tgapp.core import (
    logger,
    ensure_registered,
    CANCEL_KB,
    get_connection,  # <-- Изменилось: импортируем функцию, а не CONN
)
from tgapp.fsm import get_state, set_state, clear_state
from calendarapp.models import Appointment
from calendarapp.utils import create_pending_invite_for_event
from db import get_event_by_id


# ------------------------------
# Вспомогательные функции
# ------------------------------

def _safe_int(text: str) -> Optional[int]:
    """
    Аккуратно преобразовать строку в int.

    :param text: входная строка
    :return: целое число или None, если не число/пусто
    """
    try:
        return int(text.strip())
    except Exception:
        return None


def _send_invite_message(
    context: Any,
    participant_tg_id: int,
    organizer_tg_id: int,
    ev: dict,
    appt_id: int,
    extra_details: str,
) -> Tuple[bool, str]:
    """
    Отправить приглашение участнику с инлайн-кнопками.

    Возвращает (успех, сообщение_ошибки_или_пусто).
    """
    text = (
        "Вас пригласили на встречу:\n\n"
        f"• Дата/время: {ev['date']} {ev['time']}\n"
        f"• Тема: {ev['name']}\n"
        f"• Комментарий: {extra_details or (ev.get('details') or '—')}\n\n"
        "Вы можете подтвердить или отклонить приглашение:"
    )
    buttons = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"appt:ok:{appt_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"appt:no:{appt_id}"),
        ]]
    )
    try:
        context.bot.send_message(
            chat_id=participant_tg_id,
            text=text,
            reply_markup=buttons,
        )
        logger.info(
            "INVITE sent appt_id=%s organizer=%s -> participant=%s",
            appt_id, organizer_tg_id, participant_tg_id
        )
        return True, ""
    except Exception as exc:
        # классическая причина — участник не начинал чат с ботом
        logger.warning(
            "Invite delivery failed appt_id=%s to %s: %s",
            appt_id, participant_tg_id, exc
        )
        return False, "Не удалось доставить приглашение: участник ещё не начал чат с ботом."

# ------------------------------
# FSM: /invite
# ------------------------------

def invite_start(update: Any, context: Any) -> None:
    """
    Старт диалога приглашения.
    """
    user = update.effective_user
    if not ensure_registered(
        update,
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
    ):
        return

    set_state(user.id, flow="INVITE", step="WAIT_PARTICIPANT_ID", data={})
    logger.info("INVITE flow started by %s", user.id)
    update.message.reply_text(
        "Кого пригласить? Отправьте TG ID участника (число).",
        reply_markup=CANCEL_KB,
    )


def invite_process(update: Any, context: Any) -> None:
    """
    Обработчик текстов в потоке INVITE:
    - WAIT_PARTICIPANT_ID → запрос event_id
    - WAIT_EVENT_ID       → запрос деталей
    - WAIT_DETAILS        → отправка приглашения
    """
    user = update.effective_user
    msg = (update.message.text or "").strip()
    state = get_state(user.id)
    step = state.get("step")
    data = state.get("data", {})

    # Универсальная отмена
    if msg.lower() == "отмена":
        clear_state(user.id)
        logger.info("INVITE cancelled by %s at step=%s", user.id, step)
        update.message.reply_text("Ок, отменил.", reply_markup=ReplyKeyboardRemove())
        return

    # Шаг 1: TG ID участника
    if step == "WAIT_PARTICIPANT_ID":
        participant_tg_id = _safe_int(msg)
        if participant_tg_id is None or participant_tg_id <= 0:
            update.message.reply_text("TG ID — это положительное число. Попробуйте ещё раз:", reply_markup=CANCEL_KB)
            return
        if participant_tg_id == user.id:
            update.message.reply_text("Нельзя приглашать самого себя. Укажите ID другого пользователя:", reply_markup=CANCEL_KB)
            return

        data["participant_tg_id"] = participant_tg_id
        set_state(user.id, flow="INVITE", step="WAIT_EVENT_ID", data=data)
        logger.info("INVITE step1 ok by %s -> participant=%s", user.id, participant_tg_id)
        update.message.reply_text("Теперь отправьте ID вашего события (из списка ваших событий):", reply_markup=CANCEL_KB)
        return

    # Шаг 2: ID события
    if step == "WAIT_EVENT_ID":
        event_id = _safe_int(msg)
        if event_id is None or event_id <= 0:
            update.message.reply_text("ID события — это положительное число. Попробуйте ещё раз:", reply_markup=CANCEL_KB)
            return

        # ---
        # Изменение: получаем "ленивое" подключение
        # ---
        conn = None
        try:
            conn = get_connection()
            ev = get_event_by_id(conn, event_id)
        except Exception as e:
            logger.exception("Ошибка получения события %s", event_id)
            update.message.reply_text(f"Ошибка при поиске события: {e}", reply_markup=CANCEL_KB)
            return
        finally:
            if conn:
                conn.close()
        # --- Конец изменения ---

        if not ev:
            update.message.reply_text("Не нашёл такое событие. Укажите корректный ID:", reply_markup=CANCEL_KB)
            return
        if ev["user_id"] != user.id:
            update.message.reply_text("Это не ваше событие. Укажите ID события, созданного вами:", reply_markup=CANCEL_KB)
            return

        data["event"] = ev
        set_state(user.id, flow="INVITE", step="WAIT_DETAILS", data=data)
        logger.info("INVITE step2 ok by %s event_id=%s", user.id, event_id)
        update.message.reply_text(
            "Добавьте короткий комментарий для участника.\n"
            "Если комментарий не нужен — напишите «Пропустить».",
            reply_markup=CANCEL_KB,
        )
        return

    # Шаг 3: детали → отправка
    if step == "WAIT_DETAILS":
        details = "" if msg.lower() == "пропустить" else msg
        ev = data["event"]

        class _E:
            id = ev["id"]
            date = ev["date"]
            time = ev["time"]
            details = ev.get("details") or ""

        appt, err = create_pending_invite_for_event(
            organizer_tg_id=user.id,
            participant_tg_id=data["participant_tg_id"],
            event=_E,
            details=details,
        )
        if err == "busy":
            clear_state(user.id)
            logger.info("INVITE blocked (busy) %s -> %s at %s %s",
                        user.id, data["participant_tg_id"], ev["date"], ev["time"])
            update.message.reply_text("У участника на это время уже есть встреча.", reply_markup=ReplyKeyboardRemove())
            return

        ok, err_msg = _send_invite_message(
            context=context,
            participant_tg_id=data["participant_tg_id"],
            organizer_tg_id=user.id,
            ev=ev,
            appt_id=appt.id,
            extra_details=details,
        )
        clear_state(user.id)

        if not ok:
            appt.status = Appointment.Status.CANCELLED
            appt.save(update_fields=["status"])
            logger.info("INVITE delivery failed -> appt %s cancelled", appt.id)
            update.message.reply_text(err_msg, reply_markup=ReplyKeyboardRemove())
            return

        logger.info("INVITE done appt_id=%s", appt.id)
        update.message.reply_text("Приглашение отправил. Ждём ответа участника.", reply_markup=ReplyKeyboardRemove())
        return

    # Если шаг потерялся
    clear_state(user.id)
    logger.warning("INVITE state desync for user=%s", user.id)
    update.message.reply_text("Потеряли шаг диалога. Начните заново: /invite", reply_markup=ReplyKeyboardRemove())

# ------------------------------
# Callback-кнопки подтверждения/отклонения
# ------------------------------

def appointment_decision_handler(update: Any, context: Any) -> None:
    """
    Обработка инлайн-кнопок «Подтвердить/Отклонить».
    """
    query = update.callback_query
    if not query or not query.data:
        return

    parts = query.data.split(":")
    if len(parts) != 3 or parts[0] != "appt":
        query.answer("Некорректные данные.")
        return

    action, appt_id_s = parts[1], parts[2]
    appt_id = _safe_int(appt_id_s)
    if not appt_id:
        query.answer("Некорректный номер встречи.")
        return

    try:
        appt = Appointment.objects.get(pk=appt_id)
    except Appointment.DoesNotExist:
        query.answer("Встреча не найдена.")
        return

    user_id = query.from_user.id
    if user_id != appt.participant_tg_id:
        query.answer("Подтверждать или отклонять может только участник этой встречи.")
        return

    if appt.status != Appointment.Status.PENDING:
        query.answer(f"Текущий статус: {appt.get_status_display()}.")
        return

    if action == "ok":
        appt.status = Appointment.Status.CONFIRMED
        human_text = "Встреча подтверждена ✅"
        notify = f"Участник {appt.participant_tg_id} подтвердил встречу #{appt.id} на {appt.date} {appt.time}."
    else:
        appt.status = Appointment.Status.CANCELLED
        human_text = "Встреча отклонена ❌"
        notify = f"Участник {appt.participant_tg_id} отклонил встречу #{appt.id}."

    appt.save(update_fields=["status"])
    logger.info("APPT %s -> %s by %s", appt.id, appt.status, user_id)

    query.edit_message_reply_markup(reply_markup=None)
    query.answer(human_text)

    try:
        context.bot.send_message(chat_id=appt.organizer_tg_id, text=notify)
    except Exception as exc:
        logger.warning("Notify organizer failed: %s", exc)


__all__ = [
    "invite_start",
    "invite_process",
    "appointment_decision_handler",
]