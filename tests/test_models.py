# tests/test_models.py
from __future__ import annotations
import pytest
from django.utils import timezone
from calendarapp.models import TgUser, Appointment, BotStatistics


@pytest.mark.django_db
def test_tguser_create_and_fetch():
    u = TgUser.objects.create(
        tg_id=111,
        first_name="Test",
        last_name="User",
        username="test_user",
    )
    assert TgUser.objects.get(pk=111).username == "test_user"


@pytest.mark.django_db
def test_appointment_flow():
    appt = Appointment.objects.create(
        event_id=None,
        organizer_tg_id=111,
        participant_tg_id=222,
        date=timezone.now().date(),
        time=timezone.now().time().replace(microsecond=0),
        details="demo",
        status=Appointment.Status.PENDING,
    )
    appt.status = Appointment.Status.CONFIRMED
    appt.save(update_fields=["status"])
    assert Appointment.objects.get(pk=appt.pk).status == Appointment.Status.CONFIRMED


@pytest.mark.django_db
def test_botstats_increment():
    today = timezone.now().date()
    s = BotStatistics.objects.create(date=today)
    s.event_count += 1
    s.edited_events += 2
    s.save()
    s.refresh_from_db()
    assert s.event_count == 1 and s.edited_events == 2
