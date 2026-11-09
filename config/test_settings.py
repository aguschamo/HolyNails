"""Settings para la suite de tests.

Sólo cambia la base de datos: SQLite en memoria para poder correr
`python manage.py test core users --settings=config.test_settings`
desde un clon limpio, sin PostgreSQL y sin variables de entorno.
La configuración de desarrollo (`config.settings`) no se modifica.
"""

from config.settings import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
