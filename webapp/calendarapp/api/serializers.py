"""
serializers.py
==============

DRF-сериализаторы для моделей календаря.
"""

from __future__ import annotations

from rest_framework import serializers

from calendarapp.models import Event, Appointment, TgUser, BotStatistics


class EventSerializer(serializers.ModelSerializer):
    """
    Сериализатор событий.

    Важно:
    - tg_user_id read-only: берётся из токена/контекста вьюхи (безопасность).
    """

    class Meta:
        model = Event
        fields = ["id", "name", "date", "time", "details", "tg_user_id", "is_public"]
        read_only_fields = ["id", "tg_user_id"]


class AppointmentSerializer(serializers.ModelSerializer):
    """
    Сериализатор встреч.
    """

    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "event",
            "organizer_tg_id",
            "participant_tg_id",
            "date",
            "time",
            "details",
            "status",
            "status_display",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class TgUserSerializer(serializers.ModelSerializer):
    """
    Сериализатор связанных TG-пользователей.
    """

    class Meta:
        model = TgUser
        fields = ["id", "tg_user_id", "full_name", "created_at"]
        read_only_fields = ["id", "created_at"]


class BotStatisticsSerializer(serializers.ModelSerializer):
    """
    Read-only сериализатор суточной статистики.
    """

    class Meta:
        model = BotStatistics
        fields = ["date", "user_count", "event_count", "edited_events", "cancelled_events"]
        read_only_fields = fields
