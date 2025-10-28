"""
utils.py
========

Служебные функции для работы со встречами (`Appointment`).

Назначение:
- анализ занятости пользователей (по встречам со статусами pending/confirmed);
- проверка доступности участника на конкретную дату/время;
- создание новой встречи (Appointment) для события (`Event`) с безопасной
  транзакцией и проверкой занятости.

Эти функции используются ботом и Django-приложением для управления
встречами через ORM, без прямого SQL.
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import List, Tuple, Optional

from django.db import transaction
from django.db.models import Q

from .models import Appointment, Event, TgUser


# ---------------------------------------------------------------------------
# Занятость пользователей
# ---------------------------------------------------------------------------
def get_user_events_qs(tg_user_id: int):
    """
    Вернуть QuerySet событий конкретного пользователя по его Telegram ID.
    """
    return Event.objects.filter(user_id=tg_user_id).order_by("date", "time")


def get_user_busy_slots(
    tg_user_id: int,
    date_from: Optional[date_cls] = None,
    date_to: Optional[date_cls] = None,
) -> List[Tuple[date_cls, str, int, str]]:
    """
    Получить список занятых слотов пользователя.

    Возвращает список кортежей формата:
        [(date, time, appointment_id, status), ...]

    Занятыми считаются встречи со статусами `pending` и `confirmed`.

    :param tg_user_id: Telegram ID пользователя
    :param date_from: (опционально) нижняя граница даты
    :param date_to: (опционально) верхняя граница даты
    :return: список занятых интервалов
    """
    qs = Appointment.objects.filter(Appointment.user_busy_q(tg_user_id))
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)

    return list(qs.values_list("date", "time", "id", "status"))


def is_user_free(tg_user_id: int, meet_date, meet_time) -> bool:
    """
    Проверить, свободен ли пользователь в указанное время.

    :param tg_user_id: Telegram ID пользователя
    :param meet_date: дата предполагаемой встречи (datetime.date)
    :param meet_time: время предполагаемой встречи (datetime.time)
    :return: True, если пользователь свободен; False — если занят
    """
    return not Appointment.objects.filter(
        Appointment.user_busy_q(tg_user_id),
        date=meet_date,
        time=meet_time,
    ).exists()


# ---------------------------------------------------------------------------
# Создание встреч
# ---------------------------------------------------------------------------

@transaction.atomic
def create_pending_invite_for_event(
    organizer_tg_id: int,
    participant_tg_id: int,
    event: Event,
    details: str = "",
):
    """
    Создать встречу (Appointment) в статусе `PENDING` для указанного события.

    Перед созданием проверяется, свободен ли участник на эту дату/время.
    Если занят — возвращается (None, "busy").

    :param organizer_tg_id: Telegram ID организатора
    :param participant_tg_id: Telegram ID участника
    :param event: объект события Event (должен содержать date, time, details)
    :param details: дополнительные детали приглашения
    :return: (Appointment | None, error_code | None)
    """
    meet_date = event.date
    meet_time = event.time
    final_details = details or event.details or ""

    # Проверяем занятость участника
    if not is_user_free(participant_tg_id, meet_date, meet_time):
        return None, "busy"

    # Создаём новую встречу со статусом "ожидает подтверждения"
    appt = Appointment.objects.create(
        event_id=event.id,
        organizer_tg_id=organizer_tg_id,
        participant_tg_id=participant_tg_id,
        date=meet_date,
        time=meet_time,
        details=final_details,
        status=Appointment.Status.PENDING,
    )
    return appt, None
