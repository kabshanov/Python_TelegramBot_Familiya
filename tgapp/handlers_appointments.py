"""
tgapp.handlers_appointments
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
    CONN,
    ensure_registered,
    CANCEL_KB,
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
    Отправить приглашение в Telegram участнику с инлайн-кнопками.

    :param context: telegram context
    :param participant_tg_id: tg_id участника (куда шлём)
    :param organizer_tg_id: tg_id организатора
    :param ev: dict события из БД (id, name, date, time, details, user_id)
    :param appt_id: id Appointment
    :param extra_details: произвольный текст деталей
    :return: (успех, сообщение_ошибки_или_пусто)
    """
    text = (
        "Вас пригласили на встречу:\n\n"
        f"Дата/время: {ev['date']} {ev['time']}\n"
        f"Тема: {ev['name']}\n"
        f"Описание: {extra_details or (ev.get('details') or '')}\n\n"
        f"Организатор: {organizer_tg_id}"
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
        return True, ""
    except Exception as exc:
        # классическая причина — участник не начинал чат с ботом
        logger.warning("Invite delivery failed: %s", exc)
        return False, "Приглашение не доставлено (участник не активировал бота)."


# ------------------------------
# FSM: /invite
# ------------------------------

def invite_start(update: Any, context: Any) -> None:
    """
    Старт диалога приглашения.

    Проверяем, что инициатор зарегистрирован, и просим TG ID участника.
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
    update.message.reply_text(
        "Введите TG ID участника (число):",
        reply_markup=CANCEL_KB,
    )


def invite_process(update: Any, context: Any) -> None:
    """
    Обработчик текстовых сообщений для диалога приглашения.

    Шаги:
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
        update.message.reply_text("Операция отменена.", reply_markup=ReplyKeyboardRemove())
        return

    # Шаг 1: участник
    if step == "WAIT_PARTICIPANT_ID":
        participant_tg_id = _safe_int(msg)
        if participant_tg_id is None or participant_tg_id <= 0:
            update.message.reply_text("TG ID должен быть положительным числом. Повторите ввод:", reply_markup=CANCEL_KB)
            return
        if participant_tg_id == user.id:
            update.message.reply_text("Нельзя приглашать самого себя. Введите TG ID другого пользователя:", reply_markup=CANCEL_KB)
            return

        data["participant_tg_id"] = participant_tg_id
        set_state(user.id, flow="INVITE", step="WAIT_EVENT_ID", data=data)
        update.message.reply_text(
            "Введите ID события (из ваших событий):",
            reply_markup=CANCEL_KB,
        )
        return

    # Шаг 2: событие
    if step == "WAIT_EVENT_ID":
        event_id = _safe_int(msg)
        if event_id is None or event_id <= 0:
            update.message.reply_text("ID события должен быть положительным числом. Повторите ввод:", reply_markup=CANCEL_KB)
            return

        ev = get_event_by_id(CONN, event_id)
        if not ev:
            update.message.reply_text("Событие не найдено. Укажите корректный ID:", reply_markup=CANCEL_KB)
            return
        if ev["user_id"] != user.id:
            update.message.reply_text("Это событие вам не принадлежит. Укажите свой event_id:", reply_markup=CANCEL_KB)
            return

        data["event"] = ev
        set_state(user.id, flow="INVITE", step="WAIT_DETAILS", data=data)
        update.message.reply_text(
            "Добавьте детали (сообщение участнику). "
            "Если не нужно — напишите «Пропустить».",
            reply_markup=CANCEL_KB,
        )
        return

    # Шаг 3: детали → отправка
    if step == "WAIT_DETAILS":
        details = "" if msg.lower() == "пропустить" else msg
        ev = data["event"]

        # Лёгкая обёртка под Event для утилиты create_pending_invite_for_event
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
            update.message.reply_text("Участник занят в это время.", reply_markup=ReplyKeyboardRemove())
            return

        ok, err_msg = _send_invite_message(
            context=context,
            participant_tg_id=data["participant_tg_id"],
            organizer_tg_id=user.id,
            ev=ev,
            appt_id=appt.id,
            extra_details=details,
        )
        if not ok:
            # Если не доставили — пометим как отменённую (чтобы не висела PENDING)
            appt.status = Appointment.Status.CANCELLED
            appt.save(update_fields=["status"])
            clear_state(user.id)
            update.message.reply_text(err_msg, reply_markup=ReplyKeyboardRemove())
            return

        clear_state(user.id)
        update.message.reply_text("Приглашение отправлено. Статус: ожидание.", reply_markup=ReplyKeyboardRemove())
        return

    # Если почему-то шаг не распознан
    clear_state(user.id)
    update.message.reply_text("Состояние диалога потеряно. Начните заново: /invite", reply_markup=ReplyKeyboardRemove())


# ------------------------------
# Callback-кнопки подтверждения/отклонения
# ------------------------------

def appointment_decision_handler(update: Any, context: Any) -> None:
    """
    Обработка инлайн-кнопок «Подтвердить/Отклонить».

    Формат callback_data: 'appt:ok:<id>' или 'appt:no:<id>'.
    Меняем статус Appointment и уведомляем организатора.
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

    # Разрешаем подтверждать/отклонять только участнику
    user_id = query.from_user.id
    if user_id != appt.participant_tg_id:
        query.answer("Вы не участник этой встречи.")
        return

    # Если уже не PENDING — показываем текущее состояние и ничего не меняем
    if appt.status != Appointment.Status.PENDING:
        query.answer(f"Текущий статус: {appt.get_status_display()}.")
        return

    if action == "ok":
        appt.status = Appointment.Status.CONFIRMED
        result_text = "Встреча подтверждена ✅"
        notify = f"Участник {appt.participant_tg_id} подтвердил встречу #{appt.id} на {appt.date} {appt.time}."
    else:
        appt.status = Appointment.Status.CANCELLED
        result_text = "Встреча отклонена ❌"
        notify = f"Участник {appt.participant_tg_id} отклонил встречу #{appt.id}."

    appt.save(update_fields=["status"])
    query.edit_message_reply_markup(reply_markup=None)
    query.answer(result_text)

    # Уведомим организатора
    try:
        context.bot.send_message(chat_id=appt.organizer_tg_id, text=notify)
    except Exception as exc:
        logger.warning("Organizer notify failed: %s", exc)


__all__ = [
    "invite_start",
    "invite_process",
    "appointment_decision_handler",
]
