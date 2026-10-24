import time
from contextlib import contextmanager
from django.db import connection, connections, transaction, OperationalError


@contextmanager
def atomic_immediate(using=None):
    """
    Transaction wrapper that begins with an immediate write lock on SQLite.
    On PostgreSQL and other backends, standard transaction.atomic() is used.
    On SQLite, executes 'BEGIN IMMEDIATE' when starting an outer transaction
    so concurrent writers serialize at transaction start instead of on first write.
    """
    conn = connection if using is None else connections[using]
    if conn.vendor == 'sqlite':
        if conn.get_autocommit():
            conn.set_autocommit(False)
            try:
                for i in range(50):
                    try:
                        cursor = conn.cursor()
                        cursor.execute('BEGIN IMMEDIATE')
                        break
                    except OperationalError:
                        if i == 49:
                            raise
                        time.sleep(0.05 + 0.02 * (i % 5))
                try:
                    yield
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
            finally:
                conn.set_autocommit(True)
        else:
            with transaction.atomic(using=using):
                yield
    else:
        with transaction.atomic(using=using):
            yield
