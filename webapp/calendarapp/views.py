# webapp/calendarapp/views.py
"""
Представления (views) приложения `calendarapp`.

- healthcheck — проверка живости
- export_events — выгрузка событий по токену (CSV/JSON)

CSV особенности:
- кодировка Windows-1251 (cp1251) — без кракозябр в Excel (RU);
- первая строка 'sep=;' подсказывает Excel разделитель;
- разделитель ';', перевод строк '\r\n'.
JSON особенности:
- ensure_ascii=False — «живая» кириллица.
"""
from __future__ import annotations

import csv
import io
import logging
from typing import Dict, List

from django.core import signing
from django.http import (
    HttpResponse,
    JsonResponse,
    HttpResponseForbidden,
    HttpResponseBadRequest,
)
from django.views.decorators.http import require_GET

from .utils import verify_export_token, get_user_events_payload

logger = logging.getLogger(__name__)


def healthcheck(request) -> HttpResponse:
    """Простой healthcheck для аптайм-мониторинга."""
    return HttpResponse("Calendar WebApp is running.")


@require_GET
def export_events(request, fmt: str):
    """
    Выгрузка событий пользователя в CSV/JSON по токену.

    GET-параметры:
      - token: подписанный токен с tg_user_id (см. utils.make_export_token)

    Path-параметр:
      - fmt: 'csv' или 'json'

    Безопасность:
      verify_export_token() валидирует подпись и TTL.
    """
    token = request.GET.get("token")
    if not token:
        logger.warning("export_events: missing token")
        return HttpResponseBadRequest("missing token")

    try:
        tg_user_id = verify_export_token(token)
    except (signing.BadSignature, signing.SignatureExpired):
        logger.warning("export_events: invalid or expired token")
        return HttpResponseForbidden("invalid or expired token")

    data: List[Dict] = get_user_events_payload(tg_user_id)

    if fmt == "json":
        # Кириллица читаемая, файл скачивается
        resp = JsonResponse(
            data,
            safe=False,
            json_dumps_params={"ensure_ascii": False, "indent": 2},
        )
        resp["Content-Disposition"] = f'attachment; filename="events_{tg_user_id}.json"'
        logger.info("export_events: JSON %s items for tg_user_id=%s", len(data), tg_user_id)
        return resp

    if fmt == "csv":
        # Надёжный вариант для Excel (RU): Windows-1251, sep=';'
        # 1) Собираем CSV в память как текст (Unicode)
        buf = io.StringIO()
        buf.write("sep=;\r\n")  # подсказка Excel про разделитель
        writer = csv.writer(buf, delimiter=";", lineterminator="\r\n")
        writer.writerow(["id", "name", "date", "time", "details", "tg_user_id"])
        for row in data:
            writer.writerow([
                row.get("id", ""),
                row.get("name", ""),
                row.get("date", ""),
                row.get("time", ""),
                row.get("details", ""),
                row.get("tg_user_id", ""),
            ])

        # 2) Кодируем в cp1251 и отдаём как "Excel"
        payload = buf.getvalue().encode("cp1251", errors="replace")
        resp = HttpResponse(
            payload,
            content_type="application/vnd.ms-excel; charset=windows-1251",
        )
        resp["Content-Disposition"] = f'attachment; filename="events_{tg_user_id}.csv"'
        logger.info("export_events: CSV(cp1251) %s items for tg_user_id=%s", len(data), tg_user_id)
        return resp

    logger.warning("export_events: unsupported fmt=%r", fmt)
    return HttpResponseBadRequest("fmt must be csv or json")
