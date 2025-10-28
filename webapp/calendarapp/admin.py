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

from django.contrib import admin
from .models import Event, BotStatistics, Appointment


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
