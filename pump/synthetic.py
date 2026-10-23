"""Fail-closed entry guard for the dedicated development laboratory."""
from pathlib import Path
from django.conf import settings
from django.core.management.base import CommandError
from django.db import connection


def require_synthetic_database():
    environment = settings.PUMP_ENVIRONMENT
    name = str(connection.settings_dict['NAME'])
    in_memory_test = environment == 'test' and (name == ':memory:' or name.startswith('file:memorydb_'))
    if (environment not in {'development', 'test'} or not settings.ALLOW_SYNTHETIC_DATA
            or (Path(name).name != 'synthetic.sqlite3' and not in_memory_test)):
        raise CommandError('Synthetic lab refused: enable it explicitly in development/test and use synthetic.sqlite3, never a station database.')
