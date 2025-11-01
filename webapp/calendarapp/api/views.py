"""
views.py (API)
==============

DRF-представления:
- PublicEventsListView: публичные события пользователя (без токена)
- MyEventsViewSet: CRUD по «моим» событиям (требует токен)
- MyAppointmentsViewSet: CRUD по «моим» встречам (требует токен)
- BotStatsViewSet: read-only статистика (для админов через SessionAuth)
"""

from __future__ import annotations

import logging
from typing import Any

from django.db.models import QuerySet
from rest_framework import mixins, viewsets, permissions, generics, filters
from rest_framework.request import Request
from rest_framework.response import Response

from calendarapp.models import Event, Appointment, BotStatistics
from .serializers import (
    EventSerializer,
    AppointmentSerializer,
    BotStatisticsSerializer,
)
from .permissions import HasValidExportToken

logger = logging.getLogger(__name__)


# -------- Публичные события другого пользователя --------

class PublicEventsListView(generics.ListAPIView):
    """
    Список публичных событий владельца (owner=TG_ID).
    Доступен без токена (это «публичные» события).
    Пример: GET /api/public/events/?owner=123456789
    """

    serializer_class = EventSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.OrderingFilter]
    ordering = ["date", "time", "id"]

    def get_queryset(self) -> QuerySet[Event]:
        owner = self.request.query_params.get("owner")
        if not owner or not owner.isdigit():
            return Event.objects.none()
        return Event.objects.filter(
            tg_user_id=int(owner),
            is_public=True,
        ).order_by("date", "time", "id")


# -------- Мои события (по токену) --------

class MyEventsViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    /api/my/events/ — мои события (CRUD).
    Требуется токен (?token=... или Authorization: Bearer ...).
    """

    serializer_class = EventSerializer
    permission_classes = [HasValidExportToken]
    filter_backends = [filters.OrderingFilter]
    ordering = ["date", "time", "id"]

    def get_queryset(self) -> QuerySet[Event]:
        tg_user_id = getattr(self.request, "authenticated_tg_user_id", None)
        if tg_user_id is None:
            return Event.objects.none()
        return Event.objects.filter(tg_user_id=tg_user_id).order_by("date", "time", "id")

    def perform_create(self, serializer: EventSerializer) -> None:
        tg_user_id = getattr(self.request, "authenticated_tg_user_id", None)
        serializer.save(tg_user_id=tg_user_id)

    def perform_update(self, serializer: EventSerializer) -> None:
        """
        Защищаемся: нельзя «переписать» чужое событие или сменить владельца.
        """
        tg_user_id = getattr(self.request, "authenticated_tg_user_id", None)
        instance: Event = self.get_object()
        if instance.tg_user_id != tg_user_id:
            raise PermissionError("Not owner of this event")
        serializer.save(tg_user_id=tg_user_id)


# -------- Мои встречи (по токену) --------

class MyAppointmentsViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """
    /api/my/appointments/ — мои встречи (CRUD).
    Тут считаем «моими» те встречи, где я организатор или участник.
    """

    serializer_class = AppointmentSerializer
    permission_classes = [HasValidExportToken]
    filter_backends = [filters.OrderingFilter]
    ordering = ["-date", "-time", "-id"]

    def get_queryset(self) -> QuerySet[Appointment]:
        tg_user_id = getattr(self.request, "authenticated_tg_user_id", None)
        if tg_user_id is None:
            return Appointment.objects.none()
        return Appointment.objects.filter(
            organizer_tg_id=tg_user_id
        ) | Appointment.objects.filter(
            participant_tg_id=tg_user_id
        )

    def perform_create(self, serializer: AppointmentSerializer) -> None:
        """
        Создание встречи: по умолчанию считаем инициатором владельца токена.
        """
        tg_user_id = getattr(self.request, "authenticated_tg_user_id", None)
        serializer.save(organizer_tg_id=tg_user_id)

    def perform_update(self, serializer: AppointmentSerializer) -> None:
        """
        Обновлять может организатор встречи.
        """
        tg_user_id = getattr(self.request, "authenticated_tg_user_id", None)
        instance: Appointment = self.get_object()
        if instance.organizer_tg_id != tg_user_id:
            raise PermissionError("Only organizer can modify appointment")
        serializer.save()


# -------- Статистика (только админы) --------

class BotStatsViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    /api/stats/ — read-only статистика для админов через SessionAuth.
    Просто зайди в админку (логин), затем открой DRF Browsable API.
    """

    queryset = BotStatistics.objects.all().order_by("-date")
    serializer_class = BotStatisticsSerializer
    permission_classes = [permissions.IsAdminUser]
