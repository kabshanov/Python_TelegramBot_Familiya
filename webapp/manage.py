"""
manage.py
==========

Командный интерфейс Django-проекта **Calendar WebApp**.

Назначение:
------------
- является точкой входа для всех административных команд Django;
- используется для выполнения операций через CLI (терминал, PowerShell и т.п.);
- обеспечивает корректную инициализацию настроек проекта и окружения.

Примеры использования:
----------------------
1. **Запуск сервера разработки**
    python manage.py runserver

2. **Создание миграций (генерация схемы БД)**
    python manage.py makemigrations

3. **Применение миграций**
    python manage.py migrate

4. **Создание суперпользователя (для /admin/)**
    python manage.py createsuperuser

5. **Запуск интерактивной оболочки Django**
    python manage.py shell

6. **Сброс пароля суперпользователя или проверка БД**
    python manage.py changepassword <username>
    python manage.py dbshell

Технические детали:
-------------------
- Django ищет файл `manage.py` при выполнении CLI-команд.
- Скрипт задаёт переменную окружения `DJANGO_SETTINGS_MODULE`,
  указывающую на модуль настроек (`webapp.settings`).
- Затем импортирует и вызывает `django.core.management.execute_from_command_line()`,
  передавая туда аргументы из sys.argv.

Файл универсален: одинаково работает на Windows, Linux и macOS.
"""

import os
import sys


def main() -> None:
    """
    Точка входа командной оболочки Django.

    Выполняет:
    1. Установку переменной окружения DJANGO_SETTINGS_MODULE;
    2. Импорт функции `execute_from_command_line`;
    3. Вызов её с аргументами командной строки.

    При ошибках импорта Django выводит понятное сообщение пользователю.
    """
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webapp.settings")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Не удалось импортировать Django. "
            "Убедитесь, что оно установлено и доступно в текущем окружении."
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
