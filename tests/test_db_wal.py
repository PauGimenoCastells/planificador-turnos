import pytest
from django.db import connection


@pytest.mark.django_db
def test_sqlite_wal_mode_and_timeout():
    """R3: SQLite se inicializa con WAL mode (PRAGMA journal_mode=WAL) y timeout adecuado."""
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode;")
        journal_mode = cursor.fetchone()[0]
        cursor.execute("PRAGMA busy_timeout;")
        busy_timeout = cursor.fetchone()[0]

    assert journal_mode.lower() == "wal", f"journal_mode esperado 'wal', obtenido '{journal_mode}'"
    # timeout=30 segundos = 30000 ms
    assert busy_timeout >= 30000, f"busy_timeout esperado >= 30000 ms, obtenido {busy_timeout}"

    db_config = connection.settings_dict
    options = db_config.get("OPTIONS", {})
    assert options.get("transaction_mode") == "IMMEDIATE", "transaction_mode debe ser IMMEDIATE"
