from contextlib import contextmanager
from django.db import connection, connections, transaction


@contextmanager
def atomic_immediate(using=None):
    """
    Transaction wrapper that begins with an immediate write lock on SQLite.
    On PostgreSQL and other backends, standard transaction.atomic() is used.
    On SQLite, executes 'BEGIN IMMEDIATE' when starting an outer transaction
    so concurrent writers serialize at transaction start instead of on first write.
    """
    with transaction.atomic(using=using):
        conn = connection if using is None else connections[using]
        if conn.vendor == 'sqlite' and not conn.savepoint_ids:
            cursor = conn.cursor()
            if getattr(conn.connection, 'in_transaction', False):
                cursor.execute('COMMIT')
            cursor.execute('BEGIN IMMEDIATE')
        yield
