"""
urls.py
=======

Маршруты (URL patterns) приложения `calendarapp`.

Содержит базовые URL-адреса для проверки состояния приложения и
дальнейшего расширения (например, REST API для событий и встреч).

Текущие маршруты:
- `/` — healthcheck: простая проверка, что сервер Django запущен
  и приложение calendarapp доступно.
"""
from django.urls import path
from . import views

urlpatterns = [
    path("", views.healthcheck, name="healthcheck"),
    path("export/<str:fmt>/", views.export_events, name="export_events"),  # <-- новый эндпоинт
]
