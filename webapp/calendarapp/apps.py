from django.apps import AppConfig


class CalendarappConfig(AppConfig):
    """
    Конфигурация Django-приложения calendarapp.

    Это приложение отвечает за:
    - модели Event, BotStatistics;
    - админку событий и статистики;
    - дальнейшие сущности (Appointment и т.д. по заданию №3+).
    """
    default_auto_field = "django.db.models.BigAutoField"
    name = "calendarapp"
    verbose_name = "Календарь / Бот"
