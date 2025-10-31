"""
utils.py
========

Служебные функции для календарного приложения.

Содержит две логические группы:

1) Встречи (Appointment):
   - анализ занятости пользователя (по встречам со статусами pending/confirmed);
   - проверка свободного слота;
   - создание приглашения на встречу со статусом PENDING.

2) Экспорт событий (Event):
   - выпуск/проверка подписанного токена для безопасной выгрузки;
   - подготовка полезной нагрузки (JSON/CSV) по событиям пользователя.

Эти утилиты используются как в Django-вьюхах (export endpoint),
так и на уровне Telegram-бота (генерация ссылок, проверка занятости и т.д.).
"""

from __future__ import annotations

from datetime import date as date_cls, time as time_cls
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.db.models import QuerySet

from .models import Appointment, Event


# ---------------------------------------------------------------------------
# ВСТРЕЧИ: занятость, проверка и создание приглашения
# ---------------------------------------------------------------------------

def get_user_events_qs(tg_user_id: int) -> QuerySet[Event]:
    """
    Вернуть QuerySet событий конкретного пользователя по его Telegram ID.

    ВАЖНО:
    Поле в модели `Event` — это foreign key в виде колонки `user_id` (целочисленное
    значение tg_user_id), поэтому фильтрация идёт по `user_id`, а не по `tg_user_id`.

    :param tg_user_id: Telegram ID пользователя
    :return: QuerySet(Event), отсортированный по дате/времени/ID
    """
    return (
        Event.objects
        .filter(user_id=tg_user_id)
        .order_by("date", "time", "id")
    )


def get_user_busy_slots(
    tg_user_id: int,
    date_from: Optional[date_cls] = None,
    date_to: Optional[date_cls] = None,
) -> List[Tuple[date_cls, time_cls, int, str]]:
    """
    Получить список занятых слотов пользователя по встречам.

    Занятыми считаются встречи со статусами `pending` и `confirmed`.

    :param tg_user_id: Telegram ID пользователя
    :param date_from: нижняя граница даты (включительно), если задана
    :param date_to:   верхняя граница даты (включительно), если задана
    :return: список кортежей (date, time, appointment_id, status)
    """
    qs = Appointment.objects.filter(Appointment.user_busy_q(tg_user_id))
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)

    # values_list удобен для формирования «лёгких» ответов без ORM-объектов
    return list(qs.values_list("date", "time", "id", "status"))


def is_user_free(tg_user_id: int, meet_date: date_cls, meet_time: time_cls) -> bool:
    """
    Проверить, свободен ли пользователь в указанную дату/время.

    :param tg_user_id: Telegram ID пользователя
    :param meet_date:  дата предполагаемой встречи
    :param meet_time:  время предполагаемой встречи
    :return: True — свободен, False — занят
    """
    return not Appointment.objects.filter(
        Appointment.user_busy_q(tg_user_id),
        date=meet_date,
        time=meet_time,
    ).exists()


@transaction.atomic
def create_pending_invite_for_event(
    organizer_tg_id: int,
    participant_tg_id: int,
    event: Event,
    details: str = "",
) -> Tuple[Optional[Appointment], Optional[str]]:
    """
    Создать приглашение на встречу (Appointment) в статусе PENDING для указанного события.

    Перед созданием проверяем, свободен ли участник на дату/время события.
    Если участник занят — возвращаем (None, "busy").

    :param organizer_tg_id: Telegram ID организатора
    :param participant_tg_id: Telegram ID участника
    :param event: объект Event (должен иметь date, time, details)
    :param details: дополнительные детали приглашения (опционально)
    :return: кортеж (Appointment | None, error_code | None)
    """
    meet_date = event.date
    meet_time = event.time
    final_details = details or (event.details or "")

    if not is_user_free(participant_tg_id, meet_date, meet_time):
        return None, "busy"

    appt = Appointment.objects.create(
        event_id=event.id,                  # FK на Event без БД-constraint (по модели)
        organizer_tg_id=organizer_tg_id,
        participant_tg_id=participant_tg_id,
        date=meet_date,
        time=meet_time,
        details=final_details,
        status=Appointment.Status.PENDING,
    )
    return appt, None


# ---------------------------------------------------------------------------
# ЭКСПОРТ: токены и полезная нагрузка (JSON/CSV)
# ---------------------------------------------------------------------------

def make_export_token(tg_user_id: int) -> str:
    """
    Выпустить подписанный токен для безопасной выгрузки календаря пользователя.

    Токен — это подпись `TimestampSigner` от строки tg_user_id.
    Проверка выполняется с ограничением срока жизни (settings.EXPORT_TOKEN_MAX_AGE).

    Формат:
        token = TimestampSigner(salt="calendar-export-v1").sign("<tg_id>")

    :param tg_user_id: Telegram ID пользователя, для которого будет выгрузка
    :return: строка-токен
    """
    signer = signing.TimestampSigner(salt="calendar-export-v1")
    return signer.sign(str(tg_user_id))


def verify_export_token(token: str) -> int:
    """
    Проверить валидность токена и извлечь из него tg_user_id.

    При неверной подписи/просрочке `TimestampSigner` выбросит исключение.
    Это ожидаемое поведение — вьюха должна ловить его и отдавать 403.

    :param token: полученный от клиента (бота) токен
    :return: tg_user_id (int), если токен валиден
    """
    signer = signing.TimestampSigner(salt="calendar-export-v1")
    raw = signer.unsign(token, max_age=settings.EXPORT_TOKEN_MAX_AGE)
    return int(raw)


def get_user_events_payload(tg_user_id: int) -> List[Dict]:
    """
    Подготовить список событий пользователя к сериализации (JSON/CSV).

    Здесь мы возвращаем список словарей с предсказуемыми ключами.
    Обрати внимание: для совместимости ключ назван `tg_user_id`, хотя фактически
    берётся из `Event.user_id`.

    :param tg_user_id: Telegram ID пользователя
    :return: список словарей: [{id, name, date, time, details, tg_user_id}, ...]
    """
    qs = get_user_events_qs(tg_user_id)
    return [
        {
            "id": ev.id,
            "name": ev.name,
            "date": ev.date.isoformat(),
            "time": ev.time.strftime("%H:%M:%S"),
            "details": ev.details or "",
            "tg_user_id": ev.user_id,  # совместимость с фронтом/ботом
        }
        for ev in qs
    ]


__all__ = [
    # Встречи
    "get_user_events_qs",
    "get_user_busy_slots",
    "is_user_free",
    "create_pending_invite_for_event",
    # Экспорт
    "make_export_token",
    "verify_export_token",
    "get_user_events_payload",
]
