import io
import csv
import pytest
from django.test import Client
from calendarapp.utils import make_export_token


@pytest.mark.django_db
def test_export_json(client: Client, make_event):
    tg_id = 99901
    make_event(tg_id, name="Событие-A")
    make_event(tg_id, name="Событие-B")
    token = make_export_token(tg_id)

    resp = client.get(f"/export/json/?token={token}")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    assert {"id", "name", "date", "time", "details", "tg_user_id"} <= set(data[0].keys())


@pytest.mark.django_db
def test_export_csv_cp1251(client: Client, make_event):
    tg_id = 99902
    make_event(tg_id, name="Событие-1")
    make_event(tg_id, name="Событие-2")
    token = make_export_token(tg_id)

    resp = client.get(f"/export/csv/?token={token}")
    assert resp.status_code == 200

    # Декод: сначала пробуем CP1251 (текущая реализация),
    # если вдруг где-то включили UTF-8(-SIG) — тоже поддержим.
    try:
        content = resp.content.decode("cp1251")
    except UnicodeDecodeError:
        content = resp.content.decode("utf-8-sig")

    # Читаем CSV через ';'
    f = io.StringIO(content)
    reader = csv.reader(f, delimiter=";")
    rows = [r for r in reader if any(cell.strip() for cell in r)]

    # Некоторые CSV-ридеры/редакторы любят лидирующую строку "sep=;"
    # Если она есть — пропустим.
    if rows and rows[0] and rows[0][0].lower().startswith("sep"):
        rows = rows[1:]

    assert len(rows) >= 2  # заголовок + минимум одна строка данных
    header = rows[0]
    assert header[:3] == ["id", "name", "date"]
