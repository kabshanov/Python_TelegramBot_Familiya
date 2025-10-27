import logging
from datetime import datetime

from telegram import BotCommand, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

import secrets  # файл с API_TOKEN
from db import get_connection, Calendar, register_user, user_exists

# -----------------------------------------
# Логирование
# -----------------------------------------
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# -----------------------------------------
# Подключение к базе данных и инициализация календаря
# -----------------------------------------
conn = get_connection()
calendar = Calendar(conn)

# -----------------------------------------
# FSM (Finite State Machine) для отслеживания шагов диалога
# -----------------------------------------
# user_states[user_id] = {"flow": ..., "step": ..., "data": {...}}
user_states = {}

def set_state(user_id, flow=None, step=None, data=None):
    """Устанавливает текущее состояние пользователя."""
    user_states[user_id] = {"flow": flow, "step": step, "data": data or {}}
    logger.info("FSM set user_id=%s flow=%s step=%s data=%s", user_id, flow, step, user_states[user_id]["data"])

def get_state(user_id):
    """Возвращает состояние пользователя или пустое значение по умолчанию."""
    return user_states.get(user_id, {"flow": None, "step": None, "data": {}})

def clear_state(user_id):
    """Очищает текущее состояние пользователя."""
    if user_id in user_states:
        logger.info("FSM clear user_id=%s (was %s)", user_id, user_states[user_id])
        del user_states[user_id]

# Клавиатура для действий отмены
CANCEL_KB = ReplyKeyboardMarkup([["Отмена"]], resize_keyboard=True, one_time_keyboard=True)

# -----------------------------------------
# Вспомогательные функции
# -----------------------------------------
def ensure_registered(user_id, username, first_name, update) -> bool:
    """Проверяет, зарегистрирован ли пользователь, и при необходимости предлагает регистрацию."""
    try:
        exists = user_exists(conn, user_id)
    except Exception:
        update.message.reply_text("Ошибка доступа к базе при проверке регистрации.")
        return False
    if exists:
        return True
    update.message.reply_text("Сначала выполните регистрацию: /register")
    return False

def setup_bot_commands(updater):
    """Добавляет команды в меню Telegram."""
    commands = [
        BotCommand("start", "Справка и команды"),
        BotCommand("help", "Справка"),
        BotCommand("register", "Регистрация"),
        BotCommand("create_event", "Создать событие (диалог)"),
        BotCommand("display_events", "Показать мои события"),
        BotCommand("read_event", "Показать событие по ID"),
        BotCommand("edit_event", "Изменить описание события"),
        BotCommand("delete_event", "Удалить событие"),
        BotCommand("cancel", "Отменить текущую операцию"),
    ]
    updater.bot.set_my_commands(commands)
    logger.info("TG меню команд установлено (%d шт.)", len(commands))

def parse_date(text: str):
    """Проверяет формат даты ГГГГ-ММ-ДД."""
    try:
        datetime.strptime(text, "%Y-%m-%d")
        return text
    except ValueError:
        return None

def parse_time(text: str):
    """Проверяет формат времени ЧЧ:ММ."""
    try:
        datetime.strptime(text, "%H:%M")
        return text
    except ValueError:
        return None

# -----------------------------------------
# Основные команды
# -----------------------------------------
def start(update, context):
    """Выводит справку с описанием доступных команд."""
    user = update.effective_user
    logger.info("/start user_id=%s @%s", user.id, user.username)
    text = (
        "Календарь-бот.\n\n"
        "Регистрация:\n"
        "• /register — создать учётную запись\n\n"
        "События:\n"
        "• /create_event — создать событие (диалог: имя → дата → время → описание)\n"
        "• /display_events — показать мои события\n"
        "• /read_event <id> — показать событие по ID\n"
        "• /edit_event — изменить описание (диалог) или /edit_event <id> <новое>\n"
        "• /delete_event — удалить (диалог) или /delete_event <id>\n"
        "• /cancel — отменить текущую операцию\n"
    )
    update.message.reply_text(text)

def help_command(update, context):
    """Повторно выводит справку."""
    start(update, context)

def register_command(update, context):
    """Добавляет нового пользователя в базу."""
    user = update.effective_user
    logger.info("/register user_id=%s @%s", user.id, user.username)
    try:
        register_user(conn, user.id, user.username or "", user.first_name or "")
        update.message.reply_text("Регистрация выполнена. Можно создавать события.")
    except Exception:
        update.message.reply_text("Ошибка регистрации (проверьте права на таблицу users).")

def cancel_command(update, context):
    """Отменяет текущее состояние пользователя."""
    user = update.effective_user
    logger.info("/cancel user_id=%s", user.id)
    clear_state(user.id)
    update.message.reply_text("Операция отменена.", reply_markup=ReplyKeyboardRemove())

# -----------------------------------------
# Создание события (FSM)
# -----------------------------------------
def create_event_start(update, context):
    """Запускает диалог по созданию нового события."""
    user = update.effective_user
    logger.info("/create_event start user_id=%s", user.id)
    if not ensure_registered(user.id, user.username, user.first_name, update):
        return
    set_state(user.id, flow="CREATE", step="WAIT_NAME", data={})
    update.message.reply_text("Введите название события:", reply_markup=CANCEL_KB)

def create_event_process(update, context, state):
    """Обрабатывает шаги диалога создания события."""
    user = update.effective_user
    msg = update.message.text.strip()
    logger.info("FSM CREATE user_id=%s step=%s msg=%s", user.id, state["step"], msg)

    if msg.lower() == "отмена":
        clear_state(user.id)
        update.message.reply_text("Операция отменена.", reply_markup=ReplyKeyboardRemove())
        return

    step = state["step"]
    data = state["data"]

    if step == "WAIT_NAME":
        data["name"] = msg
        set_state(user.id, flow="CREATE", step="WAIT_DATE", data=data)
        update.message.reply_text("Введите дату в формате ГГГГ-ММ-ДД:", reply_markup=CANCEL_KB)
        return

    if step == "WAIT_DATE":
        date_str = parse_date(msg)
        if not date_str:
            update.message.reply_text("Неверный формат. Пример: 2025-11-03. Попробуйте ещё раз:", reply_markup=CANCEL_KB)
            return
        data["date"] = date_str
        set_state(user.id, flow="CREATE", step="WAIT_TIME", data=data)
        update.message.reply_text("Введите время в формате ЧЧ:ММ (например, 14:30):", reply_markup=CANCEL_KB)
        return

    if step == "WAIT_TIME":
        time_str = parse_time(msg)
        if not time_str:
            update.message.reply_text("Неверный формат. Пример: 09:05. Попробуйте ещё раз:", reply_markup=CANCEL_KB)
            return
        data["time"] = time_str
        set_state(user.id, flow="CREATE", step="WAIT_DETAILS", data=data)
        update.message.reply_text("Введите описание события:", reply_markup=CANCEL_KB)
        return

    if step == "WAIT_DETAILS":
        data["details"] = msg
        try:
            eid = calendar.create_event(
                user_id=user.id,
                name=data["name"],
                date_str=data["date"],
                time_str=data["time"],
                details=data["details"],
            )
            update.message.reply_text(f"Событие создано. ID: {eid}", reply_markup=ReplyKeyboardRemove())
            logger.info("FSM CREATE done user_id=%s id=%s", user.id, eid)
        except ValueError as e:
            update.message.reply_text(str(e), reply_markup=ReplyKeyboardRemove())
        except Exception:
            update.message.reply_text("Не удалось создать событие.", reply_markup=ReplyKeyboardRemove())
        finally:
            clear_state(user.id)
        return

# -----------------------------------------
# Просмотр и чтение событий
# -----------------------------------------
def display_events_handler(update, context):
    """Выводит список событий пользователя."""
    user = update.effective_user
    logger.info("/display_events user_id=%s", user.id)
    if not ensure_registered(user.id, user.username, user.first_name, update):
        return
    try:
        update.message.reply_text(calendar.display_events(user.id))
    except Exception:
        update.message.reply_text("Ошибка при получении списка событий.")

def read_event_handler(update, context):
    """Выводит информацию о событии по его ID."""
    user = update.effective_user
    logger.info("/read_event user_id=%s", user.id)
    if not ensure_registered(user.id, user.username, user.first_name, update):
        return
    parts = update.message.text.split(maxsplit=1)
    if len(parts) < 2:
        update.message.reply_text("Формат: /read_event <id>")
        return
    try:
        eid = int(parts[1])
    except ValueError:
        update.message.reply_text("ID должен быть числом.")
        return
    try:
        res = calendar.read_event(user.id, eid)
        update.message.reply_text(res or "Событие не найдено.")
    except Exception:
        update.message.reply_text("Ошибка при чтении события.")

# -----------------------------------------
# Редактирование события (inline или FSM)
# -----------------------------------------
def edit_event_start_or_inline(update, context):
    """Редактирует описание события — сразу или через диалог."""
    user = update.effective_user
    logger.info("/edit_event user_id=%s", user.id)
    if not ensure_registered(user.id, user.username, user.first_name, update):
        return
    parts = update.message.text.split(maxsplit=2)
    if len(parts) >= 3:
        try:
            eid = int(parts[1])
        except ValueError:
            update.message.reply_text("ID должен быть числом.")
            return
        new_text = parts[2]
        try:
            ok = calendar.edit_event(user.id, eid, new_text)
            update.message.reply_text("Обновлено." if ok else "Событие не найдено.")
        except Exception:
            update.message.reply_text("Ошибка при изменении события.")
        return

    set_state(user.id, flow="EDIT", step="WAIT_ID", data={})
    update.message.reply_text("Введите ID события для изменения описания:", reply_markup=CANCEL_KB)

def edit_event_process(update, context, state):
    """Обрабатывает шаги редактирования события."""
    user = update.effective_user
    msg = update.message.text.strip()
    logger.info("FSM EDIT user_id=%s step=%s msg=%s", user.id, state["step"], msg)

    if msg.lower() == "отмена":
        clear_state(user.id)
        update.message.reply_text("Операция отменена.", reply_markup=ReplyKeyboardRemove())
        return

    if state["step"] == "WAIT_ID":
        try:
            eid = int(msg)
        except ValueError:
            update.message.reply_text("ID должен быть числом. Введите ID:", reply_markup=CANCEL_KB)
            return
        set_state(user.id, flow="EDIT", step="WAIT_NEW_DETAILS", data={"id": eid})
        update.message.reply_text("Введите новое описание:", reply_markup=CANCEL_KB)
        return

    if state["step"] == "WAIT_NEW_DETAILS":
        try:
            ok = calendar.edit_event(user.id, state["data"]["id"], msg)
            update.message.reply_text("Обновлено." if ok else "Событие не найдено.", reply_markup=ReplyKeyboardRemove())
        except Exception:
            update.message.reply_text("Ошибка при изменении события.", reply_markup=ReplyKeyboardRemove())
        finally:
            clear_state(user.id)
        return

# -----------------------------------------
# Удаление события (inline или FSM)
# -----------------------------------------
def delete_event_start_or_inline(update, context):
    """Удаляет событие — по ID или через диалог."""
    user = update.effective_user
    logger.info("/delete_event user_id=%s", user.id)
    if not ensure_registered(user.id, user.username, user.first_name, update):
        return
    parts = update.message.text.split(maxsplit=1)
    if len(parts) == 2:
        try:
            eid = int(parts[1])
        except ValueError:
            update.message.reply_text("ID должен быть числом.")
            return
        try:
            ok = calendar.delete_event(user.id, eid)
            update.message.reply_text("Удалено." if ok else "Событие не найдено.")
        except Exception:
            update.message.reply_text("Ошибка при удалении события.")
        return

    set_state(user.id, flow="DELETE", step="WAIT_ID", data={})
    update.message.reply_text("Введите ID события для удаления:", reply_markup=CANCEL_KB)

def delete_event_process(update, context, state):
    """Обрабатывает шаги удаления события."""
    user = update.effective_user
    msg = update.message.text.strip()
    logger.info("FSM DELETE user_id=%s step=%s msg=%s", user.id, state["step"], msg)

    if msg.lower() == "отмена":
        clear_state(user.id)
        update.message.reply_text("Операция отменена.", reply_markup=ReplyKeyboardRemove())
        return

    if state["step"] == "WAIT_ID":
        try:
            eid = int(msg)
        except ValueError:
            update.message.reply_text("ID должен быть числом. Введите ID:", reply_markup=CANCEL_KB)
            return
        try:
            ok = calendar.delete_event(user.id, eid)
            update.message.reply_text("Удалено." if ok else "Событие не найдено.", reply_markup=ReplyKeyboardRemove())
        except Exception:
            update.message.reply_text("Ошибка при удалении события.", reply_markup=ReplyKeyboardRemove())
        finally:
            clear_state(user.id)
        return

# -----------------------------------------
# Роутер FSM для текстовых сообщений
# -----------------------------------------
def text_router(update, context):
    """Определяет, какой процесс FSM обрабатывать в зависимости от текущего состояния."""
    user = update.effective_user
    state = get_state(user.id)
    flow = state["flow"]
    logger.info("TEXT user_id=%s flow=%s step=%s text=%s", user.id, flow, state["step"], update.message.text)

    if flow == "CREATE":
        return create_event_process(update, context, state)
    if flow == "EDIT":
        return edit_event_process(update, context, state)
    if flow == "DELETE":
        return delete_event_process(update, context, state)

    update.message.reply_text("Команда не распознана. Используйте /help.")

# -----------------------------------------
# Общий обработчик ошибок
# -----------------------------------------
def error_handler(update, context):
    """Фиксирует неперехваченные ошибки."""
    logger.exception("UNHANDLED ERROR: %s (update=%s)", context.error, update)

# -----------------------------------------
# Точка входа
# -----------------------------------------
def main():
    """Запускает бота, регистрирует обработчики и включает опрос Telegram API."""
    updater = Updater(token=secrets.API_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    setup_bot_commands(updater)

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("register", register_command))
    dispatcher.add_handler(CommandHandler("cancel", cancel_command))

    dispatcher.add_handler(CommandHandler("display_events", display_events_handler))
    dispatcher.add_handler(CommandHandler("read_event", read_event_handler))
    dispatcher.add_handler(CommandHandler("create_event", create_event_start))
    dispatcher.add_handler(CommandHandler("edit_event", edit_event_start_or_inline))
    dispatcher.add_handler(CommandHandler("delete_event", delete_event_start_or_inline))

    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, text_router))
    dispatcher.add_error_handler(error_handler)

    updater.start_polling()
    logger.info("BOT запущен (FSM, мультипользовательский режим, меню команд).")
    updater.idle()


if __name__ == "__main__":
    main()
