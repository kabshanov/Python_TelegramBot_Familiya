"""
models.py
=========

ORM-модели приложения `calendarapp`.

Содержит три ключевые сущности:

1. **Event** — событие календаря, созданное пользователем телеграм-бота.  
   - Таблица `events` создаётся и заполняется ботом напрямую через psycopg2.  
   - Django использует модель только для чтения и отображения данных.  

2. **BotStatistics** — суточная статистика активности бота.  
   - Создаётся и мигрируется Django.  
   - Содержит агрегированные показатели за день.  

3. **Appointment** — встреча между пользователями (организатор ↔ участник).  
   - Ссылается на `Event`, но без внешнего ключа в БД (db_constraint=False).  
   - Управляется Django ORM.  

Назначение модуля — связать данные телеграм-бота и Django-админку в единую систему.
"""
from __future__ import annotations

from django.db import models
from django.db.models import Q


# ---------------------------------------------------------------------------
# Event — события календаря
# ---------------------------------------------------------------------------

class TgUser(models.Model):
    """
    Пользователь Телеграм в системе.
    Используем tg_id как первичный ключ, чтобы быстро искать и связывать события.
    Здесь же считаем личные счётчики активности (создано/редактировано/удалено).
    """
    tg_id = models.BigIntegerField(primary_key=True, verbose_name="Telegram ID")
    username = models.CharField("Username", max_length=255, blank=True, default="")
    first_name = models.CharField("Имя", max_length=255, blank=True, default="")
    last_name = models.CharField("Фамилия", max_length=255, blank=True, default="")
    is_active = models.BooleanField("Активен", default=True)

    # личные счётчики активности
    events_created = models.PositiveIntegerField("Создано событий (всего)", default=0)
    events_edited = models.PositiveIntegerField("Отредактировано событий (всего)", default=0)
    events_cancelled = models.PositiveIntegerField("Отменено событий (всего)", default=0)

    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        db_table = "tg_users"
        verbose_name = "Пользователь TG"
        verbose_name_plural = "Пользователи TG"

    def __str__(self) -> str:
        base = self.username or f"{self.first_name} {self.last_name}".strip() or "без имени"
        return f"{base} ({self.tg_id})"


class Event(models.Model):
    """
    Событие календаря, созданное пользователем бота.

    ВНИМАНИЕ: это уже существующая таблица 'events', которую пишет бот через psycopg2.
    Django её НЕ мигрирует (managed=False). Мы лишь описываем схему для чтения/админки.

    Добавили FK на TgUser по колонке user_id (db_constraint=False — чтобы не требовать FK в БД).
    """
    id = models.BigAutoField(primary_key=True, db_column="id", verbose_name="ID события")

    user = models.ForeignKey(
        "calendarapp.TgUser",
        to_field="tg_id",
        db_column="user_id",
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="events",
        verbose_name="Пользователь (TG)",
    )

    is_public = models.BooleanField(
        "Публичное",
        default=False,
        db_column="is_public",
        help_text="Если включено — событие видно всем по TG ID владельца.",
    )

    name = models.CharField("Название события", max_length=255, db_column="name")
    date = models.DateField("Дата", db_column="date")
    time = models.TimeField("Время", db_column="time")
    details = models.TextField("Описание", blank=True, default="", db_column="details")

    class Meta:
        managed = False
        db_table = "events"
        verbose_name = "Событие"
        verbose_name_plural = "События"

    def __str__(self) -> str:
        return f"{self.name} @ {self.date} {self.time}"

    @property
    def tg_user_id(self) -> int:
        """Сырой TG ID владельца (значение в колонке user_id)."""
        return self.user_id


# ---------------------------------------------------------------------------
# BotStatistics — суточная активность бота
# ---------------------------------------------------------------------------

class BotStatistics(models.Model):
    """
    Суточная статистика активности бота.

    В эту таблицу Django ORM пишет ежедневные агрегаты:
    - user_count        — новых пользователей за день;
    - event_count       — созданных событий;
    - edited_events     — отредактированных событий;
    - cancelled_events  — удалённых событий.
    """

    date = models.DateField(
        "Дата",
        unique=True,
        help_text="Статистика за этот день",
    )
    user_count = models.PositiveIntegerField(
        "Пользователей всего (новых за день)",
        default=0,
    )
    event_count = models.PositiveIntegerField(
        "Создано событий",
        default=0,
    )
    edited_events = models.PositiveIntegerField(
        "Отредактировано событий",
        default=0,
    )
    cancelled_events = models.PositiveIntegerField(
        "Отменено событий",
        default=0,
    )

    class Meta:
        verbose_name = "Статистика бота"
        verbose_name_plural = "Статистика бота"

    def __str__(self) -> str:
        return f"Статистика {self.date}"


# ---------------------------------------------------------------------------
# Appointment — встречи между пользователями
# ---------------------------------------------------------------------------

class Appointment(models.Model):
    """
    Встреча между организатором и участником.

    Ссылается на таблицу `events` (через модель Event), но без ограничения
    внешнего ключа в БД, чтобы не ломать связь с ботом. Проверки целостности
    выполняются прикладным кодом.
    """

    class Status(models.TextChoices):
        """Возможные статусы встречи."""
        PENDING = "pending", "Ожидает подтверждения"
        CONFIRMED = "confirmed", "Подтверждено"
        CANCELLED = "cancelled", "Отменено"
        DECLINED = "declined", "Отклонено"

    event = models.ForeignKey(
        "calendarapp.Event",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        db_constraint=False,
        db_column="event_id",
        verbose_name="Событие",
    )
    organizer_tg_id = models.BigIntegerField("Организатор (TG ID)", db_index=True)
    participant_tg_id = models.BigIntegerField("Участник (TG ID)", db_index=True)

    date = models.DateField("Дата")
    time = models.TimeField("Время")
    details = models.TextField("Детали", blank=True, default="")

    status = models.CharField(
        "Статус",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Встреча"
        verbose_name_plural = "Встречи"
        ordering = ["-date", "-time", "-id"]

    def __str__(self) -> str:
        return (
            f"{self.date} {self.time} "
            f"[{self.get_status_display()}] "
            f"{self.organizer_tg_id} → {self.participant_tg_id}"
        )

    @staticmethod
    def user_busy_q(tg_user_id: int) -> Q:
        """
        Q-условие для выборки встреч, которые занимают время пользователя.

        Занятыми считаются встречи со статусами `pending` и `confirmed`.

        :param tg_user_id: Telegram-ID пользователя
        :return: объект django.db.models.Q для фильтрации QuerySet
        """
        return (
            Q(organizer_tg_id=tg_user_id) | Q(participant_tg_id=tg_user_id)
        ) & Q(status__in=[Appointment.Status.PENDING, Appointment.Status.CONFIRMED])
