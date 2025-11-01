"""
urls.py (API)
=============

Маршрутизация DRF-эндпоинтов.
"""

from __future__ import annotations

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    PublicEventsListView,
    MyEventsViewSet,
    MyAppointmentsViewSet,
    BotStatsViewSet,
)

router = DefaultRouter()
router.register(r"my/events", MyEventsViewSet, basename="my-events")
router.register(r"my/appointments", MyAppointmentsViewSet, basename="my-appointments")
router.register(r"stats", BotStatsViewSet, basename="stats")

urlpatterns = [
    # Публичные события пользователя: /api/public/events/?owner=<tg_id>
    path("public/events/", PublicEventsListView.as_view(), name="public-events"),
    # CRUD-эндпоинты:
    path("", include(router.urls)),
]
