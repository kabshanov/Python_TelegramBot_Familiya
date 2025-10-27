import logging
from datetime import datetime
import psycopg2
from psycopg2 import Error as PGError

logger = logging.getLogger(__name__)


def get_connection():
    """
    Возвращает подключение к PostgreSQL.
    В учебной среде включён autocommit, чтобы не зависать в 'прерванной транзакции'.
    Для продакшена autocommit можно отключить и управлять транзакциями явно.
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
    """Проверяет наличие пользователя в таблице users по Telegram ID."""
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE tg_user_id = %s;", (tg_user_id,))
        exists = cur.fetchone() is not None
        cur.close()
        logger.info("DB: user_exists tg_user_id=%s -> %s", tg_user_id, exists)
        return exists
    except PGError as e:
        logger.exception("DB: user_exists ошибка tg_user_id=%s", tg_user_id)
        raise


def register_user(conn, tg_user_id: int, username: str, first_name: str) -> None:
    """
    Регистрирует пользователя (upsert по tg_user_id).
    Требуются права INSERT/UPDATE на users и USAGE/SELECT на users_id_seq (для serial).
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
    except PGError as e:
        logger.exception("DB: register_user ошибка tg_user_id=%s", tg_user_id)
        raise


class Calendar:
    """
    Календарь с хранением в PostgreSQL.
    Таблица events: id, name, date, time, details, user_id.
    """

    def __init__(self, conn):
        self.conn = conn
        logger.info("Calendar: инициализировано подключение к БД.")

    def create_event(self, user_id: int, name: str, date_str: str, time_str: str, details: str) -> int:
        """Создаёт событие пользователя и возвращает его ID."""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            datetime.strptime(time_str, "%H:%M")
        except ValueError:
            raise ValueError("Дата должна быть в формате ГГГГ-ММ-ДД, время — ЧЧ:ММ.")

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
        """Возвращает строку с описанием события пользователя или None."""
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
            logger.info("DB: read_event user_id=%s id=%s found=%s", user_id, event_id, bool(row))
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
        """Обновляет описание события пользователя."""
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
            logger.info("DB: edit_event user_id=%s id=%s updated=%s", user_id, event_id, updated)
            return updated
        except PGError:
            logger.exception("DB: edit_event ошибка user_id=%s id=%s", user_id, event_id)
            raise

    def delete_event(self, user_id: int, event_id: int) -> bool:
        """Удаляет событие пользователя."""
        try:
            cur = self.conn.cursor()
            cur.execute(
                "DELETE FROM events WHERE id = %s AND user_id = %s;",
                (event_id, user_id),
            )
            deleted = cur.rowcount > 0
            cur.close()
            logger.info("DB: delete_event user_id=%s id=%s deleted=%s", user_id, event_id, deleted)
            return deleted
        except PGError:
            logger.exception("DB: delete_event ошибка user_id=%s id=%s", user_id, event_id)
            raise

    def display_events(self, user_id: int) -> str:
        """Возвращает отсортированный список событий пользователя."""
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
            logger.info("DB: display_events user_id=%s count=%s", user_id, len(rows))
            if not rows:
                return "Событий пока нет."
            lines = ["Список событий:"]
            for eid, name, d, t in rows:
                lines.append(f"ID: {eid} | {d} {t} | {name}")
            return "\n".join(lines)
        except PGError:
            logger.exception("DB: display_events ошибка user_id=%s", user_id)
            raise
