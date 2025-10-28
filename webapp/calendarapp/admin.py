"""
admin.py
========

Регистрация моделей приложения `calendarapp` в панели администратора Django.

Модели:
- Event — календарные события пользователей (создаются ботом);
- BotStatistics — статистика активности бота за день;
- Appointment — встречи между пользователями (организатор ↔ участник).

Для каждой модели определены классы ModelAdmin с настройками
отображения, фильтрации и поиска.

Цель:
Упростить работу администратора при просмотре и управлении событиями,
встречами и метриками бота.
"""
from __future__ import annotations

from django.contrib import admin
from .models import TgUser, Event, BotStatistics, Appointment


class EventInline(admin.TabularInline):
    """
    Read-only inline событий пользователя.
    Работает, потому что Event.user — FK на TgUser (без жёсткого ограничения в БД).
    """
    model = Event
    fields = ("id", "name", "date", "time", "details")
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None) -> bool:  # type: ignore[override]
        return False


@admin.register(TgUser)
class TgUserAdmin(admin.ModelAdmin):
    """
    «Личный кабинет» пользователя в админке:
    карточка пользователя + его события + суммарные счётчики.
    """
    list_display = (
        "tg_id", "username", "first_name", "last_name",
        "events_total", "events_created", "events_edited", "events_cancelled",
        "is_active", "created_at",
    )
    search_fields = ("tg_id", "username", "first_name", "last_name")
    list_filter = ("is_active",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [EventInline]

    @admin.display(description="Событий (всего)")
    def events_total(self, obj: TgUser) -> int:
        return obj.events.count()  # reverse related_name=events из Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    """
    Админ-интерфейс для модели Event.

    Отображает базовую информацию о событиях пользователей
    (название, дата, время, tg_id создателя).
    """
    list_display = ("id", "name", "date", "time", "tg_user_id")
    list_filter = ("date",)
    search_fields = ("name", "details", "tg_user_id")


@admin.register(BotStatistics)
class BotStatisticsAdmin(admin.ModelAdmin):
    """
    Админ-интерфейс для модели BotStatistics.

    Позволяет просматривать дневную статистику:
    количество пользователей, событий, отредактированных
    и отменённых записей.
    """
    list_display = (
        "date",
        "user_count",
        "event_count",
        "edited_events",
        "cancelled_events",
    )
    list_filter = ("date",)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    """
    Админ-интерфейс для модели Appointment (встречи).

    Отображает встречи между пользователями, с фильтрацией по дате и статусу,
    а также быстрым поиском по ID и деталям.
    """
    list_display = (
        "id",
        "date",
        "time",
        "status",
        "organizer_tg_id",
        "participant_tg_id",
        "event",
    )
    list_filter = ("status", "date")
    search_fields = ("details", "organizer_tg_id", "participant_tg_id")
