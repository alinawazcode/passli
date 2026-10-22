from django.apps import AppConfig
from django.db.backends.signals import connection_created


def configure_sqlite_pragmas(sender, connection, **kwargs):
    if connection.vendor == 'sqlite':
        try:
            with connection.cursor() as cursor:
                cursor.execute('PRAGMA journal_mode=WAL;')
                cursor.execute('PRAGMA busy_timeout=60000;')
        except Exception:
            pass


class SharingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sharing'

    def ready(self):
        connection_created.connect(configure_sqlite_pragmas)

