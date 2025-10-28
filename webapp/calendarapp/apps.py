"""
apps.py
=======

Конфигурация Django-приложения `calendarapp`.

Назначение:
- регистрирует приложение в системе Django;
- определяет читаемое имя (verbose_name);
- задаёт автоинкрементное поле по умолчанию для моделей.

Приложение включает:
- модели событий (Event) и статистики (BotStatistics);
- админ-интерфейсы этих моделей;
- модель встреч (Appointment) и вспомогательные утилиты.
"""

from django.apps import AppConfig


class CalendarappConfig(AppConfig):
    """
    Конфигурация приложения календаря и телеграм-бота.

    Используется Django для инициализации пакета `calendarapp`
    при запуске проекта.
    """
    default_auto_field = "django.db.models.BigAutoField"
    name = "calendarapp"
    verbose_name = "Календарь / Бот"
