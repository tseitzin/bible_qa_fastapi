"""Tests for configuration helpers."""
from app.config import Settings


def test_db_config_uses_database_url():
    settings = Settings(database_url="postgres://user:pass@localhost:6543/mydb")

    cfg = settings.db_config

    assert cfg["dbname"] == "mydb"
    assert cfg["user"] == "user"
    assert cfg["port"] == 6543


def test_db_config_falls_back_to_individual_fields():
    settings = Settings(
        database_url="",
        db_name="custom",
        db_user="app",
        db_password="secret",
        db_host="db",
        db_port=5433,
    )

    cfg = settings.db_config

    assert cfg == {
        "dbname": "custom",
        "user": "app",
        "password": "secret",
        "host": "db",
        "port": 5433,
    }
