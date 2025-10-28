"""
wsgi.py
=======

WSGI-точка входа Django-проекта **Calendar WebApp**.

Назначение:
- обеспечивает совместимость с любым WSGI-сервером (gunicorn, uWSGI и др.);
- используется при деплое проекта на сервер или облачный хостинг;
- создаёт объект `application`, который Django использует для обработки запросов.

Примечание:
При локальной разработке этот файл не используется напрямую —
сервер запускается через `python manage.py runserver`.
"""

import os
from django.core.wsgi import get_wsgi_application


# Указываем Django, какой модуль настроек использовать
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webapp.settings")

# Экземпляр приложения WSGI, используемый сервером
application = get_wsgi_application()
