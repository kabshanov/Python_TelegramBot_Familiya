"""
tgapp.fsm
=========

Небольшой слой FSM (finite state machine) для бота.

Хранит состояние пользователя в памяти процесса:
    user_id -> {"flow": <str|None>, "step": <str|None>, "data": <dict>}

Особенности:
- Без зависимостей от telegram/django.
- Потоки (flow) и шаги (step) — произвольные строки (например, "CREATE", "EDIT").
- Данные (data) — произвольный словарь с промежуточными значениями.
- Предоставляет функции для чтения/записи состояния и простые парсеры даты/времени.

Важно:
- Все данные живут в памяти процесса. При рестарте бота состояние теряется.
- Типы возвращаемых значений у парсеров (str|None) согласованы с текущими хендлерами.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Final, Optional, TypedDict


class FSMState(TypedDict, total=False):
    """Структура FSM-состояния одного пользователя."""
    flow: Optional[str]
    step: Optional[str]
    data: Dict[str, Any]

# --- SHARE (публикация события) ---------------------------------------------
FLOW_SHARE = "SHARE"
STATE_SHARE_WAIT_EVENT_ID = "SHARE_WAIT_EVENT_ID"
STATE_SHARE_WAIT_VISIBILITY = "STATE_SHARE_WAIT_VISIBILITY"


# Хранилище состояний для всех пользователей (in-memory).
_USER_STATES: Dict[int, FSMState] = {}

# Состояние по умолчанию (когда записей нет).
_DEFAULT_STATE: Final[FSMState] = {"flow": None, "step": None, "data": {}}


# ---------------------------------------------------------------------------
# Базовые операции со состоянием
# ---------------------------------------------------------------------------

def set_state(user_id: int, flow: Optional[str], step: Optional[str], data: Optional[dict]) -> None:
    """
    Установить состояние FSM для пользователя.

    :param user_id: Telegram user_id
    :param flow: имя потока (например, "CREATE") или None
    :param step: имя шага (например, "WAIT_NAME") или None
    :param data: словарь с произвольными данными (может быть None)
    """
    _USER_STATES[user_id] = {
        "flow": flow,
        "step": step,
        "data": data or {},
    }


def get_state(user_id: int) -> FSMState:
    """
    Получить текущее состояние FSM пользователя.

    :param user_id: Telegram user_id
    :return: словарь состояния {'flow': ..., 'step': ..., 'data': {...}}
    """
    return _USER_STATES.get(user_id, _DEFAULT_STATE.copy())


def clear_state(user_id: int) -> None:
    """
    Сбросить состояние пользователя (удалить запись из хранилища).

    :param user_id: Telegram user_id
    """
    _USER_STATES.pop(user_id, None)


def update_state_data(user_id: int, **kwargs: Any) -> None:
    """
    Обновить поле data у состояния (слить ключи поверх существующих).

    :param user_id: Telegram user_id
    :param kwargs: пары ключ-значение, которые нужно добавить/обновить
    """
    state = _USER_STATES.setdefault(user_id, _DEFAULT_STATE.copy())
    data = state.get("data") or {}
    data.update(kwargs)
    state["data"] = data
    _USER_STATES[user_id] = state


def is_in_flow(user_id: int, flow: str) -> bool:
    """
    Проверить, находится ли пользователь в указанном потоке.

    :param user_id: Telegram user_id
    :param flow: имя потока
    :return: True/False
    """
    return get_state(user_id).get("flow") == flow


# ---------------------------------------------------------------------------
# Парсеры ввода пользователя
# ---------------------------------------------------------------------------

def parse_date(text: str) -> Optional[str]:
    """
    Проверить, что дата в формате YYYY-MM-DD (строка).
    Вернуть нормализованную строку или None при ошибке.

    :param text: исходная строка (например, "2025-11-03")
    :return: "YYYY-MM-DD" либо None
    """
    s = (text or "").strip()
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except ValueError:
        return None


def parse_time(text: str) -> Optional[str]:
    """
    Проверить, что время в формате HH:MM (24-часовой формат).
    Вернуть нормализованную строку или None при ошибке.

    :param text: исходная строка (например, "09:05")
    :return: "HH:MM" либо None
    """
    s = (text or "").strip()
    try:
        datetime.strptime(s, "%H:%M")
        return s
    except ValueError:
        return None


__all__ = [
    "FSMState",
    "set_state",
    "get_state",
    "clear_state",
    "update_state_data",
    "is_in_flow",
    "parse_date",
    "parse_time",
]
