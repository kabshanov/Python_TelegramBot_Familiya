"""
views.py
========

Представления (views) приложения `calendarapp`.

Содержит базовую проверку работоспособности приложения Django
и служит точкой расширения для будущих REST API эндпоинтов.

Текущие представления:
- healthcheck — возвращает HTTP 200 OK, подтверждая, что сервер работает.
"""

from django.http import HttpResponse
from django.http import HttpRequest


def healthcheck(request: HttpRequest) -> HttpResponse:
    """
    Простейшая проверка состояния приложения (healthcheck).

    Используется для мониторинга, чтобы убедиться,
    что Django-сервер запущен и обрабатывает запросы.

    :param request: объект HttpRequest
    :return: HttpResponse с текстом подтверждения
    """
    return HttpResponse("Calendar WebApp is running.")
