"""
permissions.py
==============

Кастомные права доступа для API.
"""

from __future__ import annotations

import logging
from typing import Optional

from django.core import signing
from rest_framework import permissions
from rest_framework.request import Request

from calendarapp.utils import verify_export_token

logger = logging.getLogger(__name__)


def extract_tg_user_id_from_request(request: Request) -> Optional[int]:
    """
    Извлечь tg_user_id из:
    - query-параметра ?token=...
    - либо из заголовка Authorization: Bearer <token>

    Возвращает tg_user_id или None.
    """
    token = request.query_params.get("token")
    if not token:
        auth = request.headers.get("Authorization", "")
        # Формат: "Bearer <token>"
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()

    if not token:
        return None

    try:
        tg_user_id = verify_export_token(token)
        return tg_user_id
    except (signing.BadSignature, signing.SignatureExpired):
        logger.warning("Invalid/expired API token")
        return None


class HasValidExportToken(permissions.BasePermission):
    """
    Разрешение: у запроса должен быть валидный экспортный токен.

    Если токен валидный — кладём tg_user_id в request.authenticated_tg_user_id.
    """

    def has_permission(self, request: Request, view) -> bool:
        tg_user_id = extract_tg_user_id_from_request(request)
        if tg_user_id is None:
            return False
        # положим в request, чтобы вьюхи забрали
        setattr(request, "authenticated_tg_user_id", tg_user_id)
        return True
