"""
urls.py
=======

Корневой маршрутизатор Django-проекта **Calendar WebApp**.

Назначение:
- объединяет все маршруты проекта;
- подключает административную панель Django;
- направляет корневой URL (`/`) в приложение `calendarapp`.

Структура маршрутов:
- /admin/ — стандартная админка Django;
- / — healthcheck и API приложения календаря (`calendarapp`).
"""

from django.contrib import admin
from django.urls import path, include


urlpatterns = [
    # Панель администратора Django
    path("admin/", admin.site.urls),

    # Основное приложение календаря (корневой маршрут)
    path("", include("calendarapp.urls")),

    # DRF API
    path("api/", include("calendarapp.api.urls")),
]
