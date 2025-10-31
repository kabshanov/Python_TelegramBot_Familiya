"""
db.py

Модуль прямой работы с PostgreSQL (psycopg2).

Отвечает за:
- подключение к базе данных;
- регистрацию и проверку пользователей;
- CRUD-операции по событиям календаря;
- вспомогательные операции уровня БД (напр., добавление колонки is_public).

Слои:
- Функции user_exists / register_user управляют таблицей users.
- Класс Calendar инкапсулирует операции с таблицей events.

Важно:
- Подключение (get_connection) использует autocommit=True, чтобы в учебной
  среде не ловить подвисшие транзакции.
- В продакшене autocommit обычно отключают и работают через явные транзакции.
"""

from __future__ import annotations

import logging
from datetime import datetime

import psycopg2
from psycopg2 import Error as PGError
from psycopg2.extensions import connection as PGConnection

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Подключение к БД
# --------------------------------------------------------------------------- #
def get_connection() -> PGConnection:
    """
    Установить подключение к PostgreSQL и вернуть объект соединения.

    Возвращает:
        PGConnection: активное соединение с автокоммитом.
    """
    conn: PGConnection = psycopg2.connect(
        host="localhost",
        database="calendar_db",
        user="calendar_user",
        password="calendar_password",
    )
    conn.autocommit = True
    logger.info("DB: подключение установлено (autocommit=%s).", conn.autocommit)
    return conn


# --------------------------------------------------------------------------- #
# Служебное: гарантировать наличие колонки is_public (Task 5)
# --------------------------------------------------------------------------- #
def ensure_is_public_column(conn: PGConnection) -> None:
    """
    Гарантирует наличие колонки is_public в таблице public.events.
    Идемпотентно: если колонка уже есть — тихо выходим.

    Параметры:
        conn: psycopg2 connection.
    """
    try:
        with conn.cursor() as cur:
            # Проверяем, существует ли колонка
            cur.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name   = 'events'
                  AND column_name  = 'is_public'
                """
            )
            exists = cur.fetchone() is not None
            if exists:
                logger.debug("events.is_public уже существует — ок.")
                return

            # Колонки нет — добавляем
            logger.info(
                "Добавляю колонку events.is_public (BOOLEAN NOT NULL DEFAULT FALSE)"
            )
            cur.execute(
                "ALTER TABLE public.events "
                "ADD COLUMN IF NOT EXISTS is_public BOOLEAN NOT NULL DEFAULT FALSE"
            )
            cur.execute(
                "COMMENT ON COLUMN public.events.is_public "
                "IS 'Флаг публичности события (Task 5)'"
            )
    except Exception as e:  # noqa: BLE001
        # Не валим бота, просто логируем (напр., таблицы events ещё нет).
        logger.warning("Не удалось гарантировать events.is_public: %s", e)
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------------- #
# Пользователи
# --------------------------------------------------------------------------- #
def user_exists(conn: PGConnection, tg_user_id: int) -> bool:
    """
    Проверить, зарегистрирован ли пользователь с заданным Telegram ID.

    Параметры:
        conn: psycopg2 connection.
        tg_user_id: Telegram user id.

    Возвращает:
        True, если пользователь есть в таблице users, иначе False.
    """
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM users WHERE tg_user_id = %s;", (tg_user_id,))
            exists = cur.fetchone() is not None
        logger.info("DB: user_exists tg_user_id=%s -> %s", tg_user_id, exists)
        return exists
    except PGError:
        logger.exception("DB: user_exists ошибка tg_user_id=%s", tg_user_id)
        raise


def register_user(conn: PGConnection, tg_user_id: int, username: str, first_name: str) -> None:
    """
    Зарегистрировать пользователя или обновить его данные (upsert по tg_user_id).

    Параметры:
        conn: psycopg2 connection.
        tg_user_id: Telegram user id.
        username: @username в Telegram.
        first_name: имя (first_name) в Telegram.

    Поведение:
        INSERT в таблицу users, при конфликте по tg_user_id выполняется UPDATE.

    Требования к БД:
        - Таблица users с полем tg_user_id уникальным/PRIMARY KEY.
        - Права INSERT/UPDATE на таблицу users.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (tg_user_id, username, first_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (tg_user_id)
                DO UPDATE SET username = EXCLUDED.username,
                              first_name = EXCLUDED.first_name;
                """,
                (tg_user_id, username, first_name),
            )
        logger.info("DB: register_user tg_user_id=%s", tg_user_id)
    except PGError:
        logger.exception("DB: register_user ошибка tg_user_id=%s", tg_user_id)
        raise


# --------------------------------------------------------------------------- #
# Календарь (events)
# --------------------------------------------------------------------------- #
class Calendar:
    """
    Высокоуровневый интерфейс к событиям календаря (таблица events).

    Методы:
        create_event(...) -> int
        read_event(...) -> str | None
        edit_event(...) -> bool
        delete_event(...) -> bool
        display_events(...) -> str

    Таблица events должна иметь поля:
        id SERIAL PRIMARY KEY,
        name TEXT/VARCHAR,
        date DATE,
        time TIME,
        details TEXT,
        user_id BIGINT (Telegram ID владельца).
    """

    def __init__(self, conn: PGConnection) -> None:
        """Инициализировать Calendar с уже установленным соединением."""
        self.conn: PGConnection = conn
        logger.info("Calendar: инициализировано подключение к БД.")

    def create_event(
        self,
        user_id: int,
        name: str,
        date_str: str,
        time_str: str,
        details: str,
    ) -> int:
        """
        Создать новое событие во владении user_id.

        Параметры:
            user_id: Telegram ID владельца события.
            name: название события.
            date_str: дата в формате 'ГГГГ-ММ-ДД'.
            time_str: время в формате 'ЧЧ:ММ'.
            details: произвольное описание.

        Возвращает:
            ID вставленной записи (events.id).

        Исключения:
            ValueError: если формат даты/времени неверный.
            PGError: внутренняя ошибка PostgreSQL.
        """
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            datetime.strptime(time_str, "%H:%M")
        except ValueError as e:
            raise ValueError(
                "Дата должна быть в формате ГГГГ-ММ-ДД, "
                "время — ЧЧ:ММ."
            ) from e

        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO events (name, date, time, details, user_id)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (name, date_str, time_str, details, user_id),
                )
                eid = cur.fetchone()[0]
            logger.info("DB: create_event ok user_id=%s id=%s", user_id, eid)
            return eid
        except PGError:
            logger.exception("DB: create_event ошибка user_id=%s", user_id)
            raise

    def read_event(self, user_id: int, event_id: int) -> str | None:
        """
        Получить текстовое описание события пользователя.

        Параметры:
            user_id: Telegram ID владельца.
            event_id: ID события в таблице events.

        Возвращает:
            Форматированное описание события или None,
            если событие не найдено/не принадлежит.
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, name, date, time, details
                    FROM events
                    WHERE id = %s AND user_id = %s;
                    """,
                    (event_id, user_id),
                )
                row = cur.fetchone()

            logger.info(
                "DB: read_event user_id=%s id=%s found=%s",
                user_id,
                event_id,
                bool(row),
            )
            if not row:
                return None

            eid, name, date_val, time_val, details = row
            return (
                f"Событие (ID: {eid}): {name}\n"
                f"Дата: {date_val}\n"
                f"Время: {time_val}\n"
                f"Описание: {details or ''}"
            )
        except PGError:
            logger.exception("DB: read_event ошибка user_id=%s id=%s", user_id, event_id)
            raise

    def edit_event(self, user_id: int, event_id: int, new_details: str) -> bool:
        """
        Обновить описание (details) события пользователя.

        Параметры:
            user_id: Telegram ID владельца.
            event_id: ID события.
            new_details: новый текст.

        Возвращает:
            True, если обновили хотя бы одну строку.
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE events
                    SET details = %s
                    WHERE id = %s AND user_id = %s;
                    """,
                    (new_details, event_id, user_id),
                )
                updated = cur.rowcount > 0
            logger.info(
                "DB: edit_event user_id=%s id=%s updated=%s",
                user_id,
                event_id,
                updated,
            )
            return updated
        except PGError:
            logger.exception("DB: edit_event ошибка user_id=%s id=%s", user_id, event_id)
            raise

    def delete_event(self, user_id: int, event_id: int) -> bool:
        """
        Удалить событие пользователя.

        Параметры:
            user_id: Telegram ID владельца.
            event_id: ID события.

        Возвращает:
            True, если строка была удалена.
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM events WHERE id = %s AND user_id = %s;",
                    (event_id, user_id),
                )
                deleted = cur.rowcount > 0
            logger.info(
                "DB: delete_event user_id=%s id=%s deleted=%s",
                user_id,
                event_id,
                deleted,
            )
            return deleted
        except PGError:
            logger.exception("DB: delete_event ошибка user_id=%s id=%s", user_id, event_id)
            raise

    def display_events(self, user_id: int) -> str:
        """
        Получить краткий список событий пользователя, отсортированный
        по дате и времени.

        Параметры:
            user_id: Telegram ID владельца.

        Возвращает:
            Человекочитаемый список событий
            или "Событий пока нет." если пусто.
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, name, date, time
                    FROM events
                    WHERE user_id = %s
                    ORDER BY date, time;
                    """,
                    (user_id,),
                )
                rows = cur.fetchall()

            logger.info("DB: display_events user_id=%s count=%s", user_id, len(rows))
            if not rows:
                return "Событий пока нет."

            lines = ["Список событий:"]
            for eid, name, date_val, time_val in rows:
                lines.append(f"ID: {eid} | {date_val} {time_val} | {name}")
            return "\n".join(lines)

        except PGError:
            logger.exception("DB: display_events ошибка user_id=%s", user_id)
            raise


# --------------------------------------------------------------------------- #
# Вспомогательная выборка
# --------------------------------------------------------------------------- #
def get_event_by_id(conn: PGConnection, event_id: int) -> dict | None:
    """
    Получить событие из таблицы events по id.

    Параметры:
        conn: psycopg2 connection.
        event_id: идентификатор события.

    Возвращает:
        dict с полями события или None, если не найдено.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, date, time, details, user_id
            FROM events
            WHERE id = %s
            """,
            (event_id,),
        )
        row = cur.fetchone()

    if not row:
        return None

    return {
        "id": row[0],
        "name": row[1],
        "date": row[2],     # date
        "time": row[3],     # time
        "details": row[4],
        "user_id": row[5],
    }
