"""Settings aislados para tests, sin PostgreSQL ni variables externas.

Usa SQLite en memoria y una SECRET_KEY fija exclusiva de tests antes de
importar la configuración general.
"""

import os

os.environ['SECRET_KEY'] = 'test-only-secret-key-not-for-production'

from config.settings import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
