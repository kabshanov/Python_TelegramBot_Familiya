from django.db import models


class Event(models.Model):
    """
    Событие календаря, созданное пользователем бота.

    Эта модель привязана к существующей таблице 'events', в которую
    пишет сам телеграм-бот через psycopg2 (db.Calendar.create_event и т.д.).

    Таблица 'events' в базе ожидается примерно такой:
        id SERIAL PRIMARY KEY
        name TEXT/VARCHAR
        date DATE
        time TIME
        details TEXT
        user_id BIGINT  -- Telegram ID владельца события

    Мы говорим Django:
    - не управлять миграциями этой таблицы (managed = False)
    - использовать имя таблицы events (db_table = "events")
    - мэппить поле tg_user_id на столбец user_id
    """

    id = models.BigAutoField(
        primary_key=True,
        db_column="id",
        verbose_name="ID события",
    )
    name = models.CharField(
        "Название события",
        max_length=255,
        db_column="name",
    )
    date = models.DateField(
        "Дата",
        db_column="date",
    )
    time = models.TimeField(
        "Время",
        db_column="time",
    )
    details = models.TextField(
        "Описание",
        blank=True,
        default="",
        db_column="details",
    )
    tg_user_id = models.BigIntegerField(
        "ID пользователя Telegram",
        db_column="user_id",
        help_text="ID владельца события в Telegram",
    )

    class Meta:
        managed = False               # Django не создаёт/не мигрирует эту таблицу
        db_table = "events"           # использовать уже существующую таблицу
        verbose_name = "Событие"
        verbose_name_plural = "События"

    def __str__(self):
        return f"{self.name} @ {self.date} {self.time}"


class BotStatistics(models.Model):
    """
    Суточная статистика активности бота.

    Эту таблицу мы создавали через Django миграции (calendarapp_botstatistics).
    В неё бот пишет данные через ORM (bot.py):
    - user_count        (сколько новых пользователей за день)
    - event_count       (сколько создано событий)
    - edited_events     (сколько событий отредактировали)
    - cancelled_events  (сколько удалили)
    """

    date = models.DateField(
        "Дата",
        unique=True,
        help_text="Статистика за этот день",
    )
    user_count = models.PositiveIntegerField(
        "Пользователей всего (новых за день)",
        default=0,
    )
    event_count = models.PositiveIntegerField(
        "Создано событий",
        default=0,
    )
    edited_events = models.PositiveIntegerField(
        "Отредактировано событий",
        default=0,
    )
    cancelled_events = models.PositiveIntegerField(
        "Отменено событий",
        default=0,
    )

    class Meta:
        verbose_name = "Статистика бота"
        verbose_name_plural = "Статистика бота"

    def __str__(self):
        return f"Статистика {self.date}"
