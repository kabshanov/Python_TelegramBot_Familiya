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
    # Проверка доступности приложения (возвращает простой ответ 200 OK)
    path("", views.healthcheck, name="healthcheck"),
]
