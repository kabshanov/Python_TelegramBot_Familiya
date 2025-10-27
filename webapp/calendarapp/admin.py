from django.contrib import admin
from .models import Event, BotStatistics


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "date", "time", "tg_user_id")
    list_filter = ("date",)
    search_fields = ("name", "details", "tg_user_id")


@admin.register(BotStatistics)
class BotStatisticsAdmin(admin.ModelAdmin):
    list_display = ("date", "user_count", "event_count", "edited_events", "cancelled_events")
    list_filter = ("date",)
