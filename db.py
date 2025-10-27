"""
db.py

Модуль прямой работы с PostgreSQL (psycopg2).

Отвечает за:
- подключение к базе данных;
- регистрацию и проверку пользователей;
- CRUD-операции по событиям календаря.

Слои:
- Функции user_exists / register_user управляют таблицей users.
- Класс Calendar инкапсулирует операции с таблицей events.

Важно:
- Подключение (get_connection) использует autocommit=True, чтобы в учебной
  среде не ловить подвисшие транзакции.
- В продакшене autocommit обычно отключают и работают через явные транзакции.
"""

import logging
from datetime import datetime

import psycopg2
from psycopg2 import Error as PGError

logger = logging.getLogger(__name__)


def get_connection():
    """
    Установить подключение к PostgreSQL и вернуть объект соединения.

    Возвращает:
        psycopg2.extensions.connection: активное соединение с автокоммитом.
    """
    conn = psycopg2.connect(
        host="localhost",
        database="calendar_db",
        user="calendar_user",
        password="calendar_password",
    )
    conn.autocommit = True
    logger.info("DB: подключение установлено (autocommit=%s).", conn.autocommit)
    return conn


def user_exists(conn, tg_user_id: int) -> bool:
    """
    Проверить, зарегистрирован ли пользователь с заданным Telegram ID.

    Параметры:
        conn: psycopg2 connection.
        tg_user_id (int): Telegram user id.

    Возвращает:
        bool: True, если пользователь есть в таблице users, иначе False.
    """
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE tg_user_id = %s;", (tg_user_id,))
        exists = cur.fetchone() is not None
        cur.close()
        logger.info("DB: user_exists tg_user_id=%s -> %s", tg_user_id, exists)
        return exists
    except PGError:
        logger.exception("DB: user_exists ошибка tg_user_id=%s", tg_user_id)
        raise


def register_user(conn, tg_user_id: int, username: str, first_name: str) -> None:
    """
    Зарегистрировать пользователя или обновить его данные (upsert по tg_user_id).

    Параметры:
        conn: psycopg2 connection.
        tg_user_id (int): Telegram user id.
        username (str): username в Telegram.
        first_name (str): имя (first_name) в Telegram.

    Поведение:
        INSERT в таблицу users, при конфликте по tg_user_id выполняется UPDATE.

    Требования к БД:
        - Таблица users с полем tg_user_id уникальным/PRIMARY KEY.
        - Права INSERT/UPDATE на таблицу users.
    """
    try:
        cur = conn.cursor()
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
        cur.close()
        logger.info("DB: register_user tg_user_id=%s", tg_user_id)
    except PGError:
        logger.exception("DB: register_user ошибка tg_user_id=%s", tg_user_id)
        raise


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

    def __init__(self, conn):
        """
        Инициализировать Calendar с уже установленным соединением.
        """
        self.conn = conn
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
            user_id (int): Telegram ID владельца события.
            name (str): название события.
            date_str (str): дата в формате 'ГГГГ-ММ-ДД'.
            time_str (str): время в формате 'ЧЧ:ММ'.
            details (str): произвольное описание.

        Возвращает:
            int: ID вставленной записи (events.id).

        Исключения:
            ValueError: если формат даты/времени неверный.
            PGError: внутренняя ошибка PostgreSQL.
        """
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            datetime.strptime(time_str, "%H:%M")
        except ValueError:
            raise ValueError(
                "Дата должна быть в формате ГГГГ-ММ-ДД, "
                "время — ЧЧ:ММ."
            )

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO events (name, date, time, details, user_id)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (name, date_str, time_str, details, user_id),
            )
            eid = cur.fetchone()[0]
            cur.close()
            logger.info("DB: create_event ok user_id=%s id=%s", user_id, eid)
            return eid
        except PGError:
            logger.exception("DB: create_event ошибка user_id=%s", user_id)
            raise

    def read_event(self, user_id: int, event_id: int):
        """
        Получить текстовое описание события пользователя.

        Параметры:
            user_id (int): Telegram ID владельца.
            event_id (int): ID события в таблице events.

        Возвращает:
            str | None: форматированное описание события или None,
                        если событие не найдено/не принадлежит.
        """
        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT id, name, date, time, details
                FROM events
                WHERE id = %s AND user_id = %s;
                """,
                (event_id, user_id),
            )
            row = cur.fetchone()
            cur.close()
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
            logger.exception(
                "DB: read_event ошибка user_id=%s id=%s",
                user_id,
                event_id,
            )
            raise

    def edit_event(self, user_id: int, event_id: int, new_details: str) -> bool:
        """
        Обновить описание (details) события пользователя.

        Параметры:
            user_id (int): Telegram ID владельца.
            event_id (int): ID события.
            new_details (str): новый текст.

        Возвращает:
            bool: True, если обновили хотя бы одну строку.
        """
        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                UPDATE events
                SET details = %s
                WHERE id = %s AND user_id = %s;
                """,
                (new_details, event_id, user_id),
            )
            updated = cur.rowcount > 0
            cur.close()
            logger.info(
                "DB: edit_event user_id=%s id=%s updated=%s",
                user_id,
                event_id,
                updated,
            )
            return updated
        except PGError:
            logger.exception(
                "DB: edit_event ошибка user_id=%s id=%s",
                user_id,
                event_id,
            )
            raise

    def delete_event(self, user_id: int, event_id: int) -> bool:
        """
        Удалить событие пользователя.

        Параметры:
            user_id (int): Telegram ID владельца.
            event_id (int): ID события.

        Возвращает:
            bool: True, если строка была удалена.
        """
        try:
            cur = self.conn.cursor()
            cur.execute(
                "DELETE FROM events WHERE id = %s AND user_id = %s;",
                (event_id, user_id),
            )
            deleted = cur.rowcount > 0
            cur.close()
            logger.info(
                "DB: delete_event user_id=%s id=%s deleted=%s",
                user_id,
                event_id,
                deleted,
            )
            return deleted
        except PGError:
            logger.exception(
                "DB: delete_event ошибка user_id=%s id=%s",
                user_id,
                event_id,
            )
            raise

    def display_events(self, user_id: int) -> str:
        """
        Получить краткий список событий пользователя, отсортированный
        по дате и времени.

        Параметры:
            user_id (int): Telegram ID владельца.

        Возвращает:
            str: человекочитаемый список событий
                 или "Событий пока нет." если пусто.
        """
        try:
            cur = self.conn.cursor()
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
            cur.close()
            logger.info(
                "DB: display_events user_id=%s count=%s",
                user_id,
                len(rows),
            )
            if not rows:
                return "Событий пока нет."

            lines = ["Список событий:"]
            for eid, name, date_val, time_val in rows:
                lines.append(f"ID: {eid} | {date_val} {time_val} | {name}")
            return "\n".join(lines)

        except PGError:
            logger.exception(
                "DB: display_events ошибка user_id=%s",
                user_id,
            )
            raise
