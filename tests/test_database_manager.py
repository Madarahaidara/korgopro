import json
import warnings
from types import SimpleNamespace

from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    event,
    text,
)
from sqlalchemy.exc import SAWarning

import core.database_manager as database_manager_module
from core.database_manager import DatabaseManager
from core.database_manager import _application_schema
from core.database_manager import _dependency_ordered_tables
from core.database_manager import BACKUP_EXCLUDED_TABLES


def test_application_schema_uses_public_for_postgresql_only():
    postgres_engine = SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql")
    )
    sqlite_engine = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

    assert _application_schema(postgres_engine) == "public"
    assert _application_schema(sqlite_engine) is None


def test_dependency_ordering_excludes_referenced_auth_schema_tables():
    metadata = MetaData()
    Table(
        "users",
        metadata,
        Column("id", String, primary_key=True),
        schema="auth",
    )
    Table(
        "users",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("auth_id", String, ForeignKey("auth.users.id")),
        schema="public",
    )

    tables = _dependency_ordered_tables(metadata, schema="public")

    assert [table.fullname for table in tables] == ["public.users"]
    assert isinstance(tables[0].c.id.type, Integer)


def test_dependency_ordered_tables_handles_cycles_without_warning():
    metadata = MetaData()
    Table(
        "sales",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("proforma_id", Integer, ForeignKey("proformas.id")),
    )
    Table(
        "proformas",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("sale_id", Integer, ForeignKey("sales.id")),
    )

    with warnings.catch_warnings():
        warnings.simplefilter("error", SAWarning)
        tables = _dependency_ordered_tables(metadata)

    assert {table.name for table in tables} == {"sales", "proformas"}


def test_restore_external_sqlite_file_into_active_database(tmp_path, monkeypatch):
    source_path = tmp_path / "external_backup.db"
    target_path = tmp_path / "active.db"

    def make_engine(path):
        engine = create_engine(f"sqlite:///{path}")

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        return engine

    source_engine = make_engine(source_path)
    target_engine = make_engine(target_path)
    metadata = MetaData()
    sales = Table(
        "sales",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("proforma_id", Integer, ForeignKey("proformas.id")),
    )
    proformas = Table(
        "proformas",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("sale_id", Integer, ForeignKey("sales.id")),
    )
    metadata.create_all(source_engine)
    metadata.create_all(target_engine)

    with source_engine.begin() as connection:
        connection.execute(text("PRAGMA defer_foreign_keys = ON"))
        connection.execute(sales.insert(), {"id": 1, "proforma_id": 10})
        connection.execute(proformas.insert(), {"id": 10, "sale_id": 1})

    with target_engine.begin() as connection:
        connection.execute(text("PRAGMA defer_foreign_keys = ON"))
        connection.execute(sales.insert(), {"id": 2, "proforma_id": 20})
        connection.execute(proformas.insert(), {"id": 20, "sale_id": 2})

    monkeypatch.setattr(database_manager_module, "engine", target_engine)

    result = DatabaseManager().restore_database(str(source_path))

    assert result["success"] is True, result["message"]
    with target_engine.connect() as connection:
        assert connection.execute(sales.select()).mappings().all() == [
            {"id": 1, "proforma_id": 10}
        ]
        assert connection.execute(proformas.select()).mappings().all() == [
            {"id": 10, "sale_id": 1}
        ]

    source_engine.dispose()
    target_engine.dispose()


def test_backup_excluded_tables_constant():
    """Les tables d'administration ne doivent jamais figurer dans un backup."""
    assert "users" in BACKUP_EXCLUDED_TABLES
    assert "activity_logs" in BACKUP_EXCLUDED_TABLES


def test_logical_export_excludes_admin_tables(tmp_path, monkeypatch):
    """_logical_export doit exclure users et activity_logs du JSON produit."""
    db_path = tmp_path / "export.db"
    engine = create_engine(f"sqlite:///{db_path}")
    metadata = MetaData()
    users = Table(
        "users",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("username", String),
    )
    activity_logs = Table(
        "activity_logs",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("action", String),
    )
    products = Table(
        "products",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(users.insert(), {"id": 1, "username": "admin"})
        connection.execute(activity_logs.insert(), {"id": 1, "action": "login"})
        connection.execute(products.insert(), {"id": 1, "name": "Produit A"})

    monkeypatch.setattr(database_manager_module, "engine", engine)

    export_path = tmp_path / "backup.json"
    DatabaseManager()._logical_export(str(export_path))

    with open(export_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    assert "users" not in payload["tables"]
    assert "activity_logs" not in payload["tables"]
    assert "products" in payload["tables"]
    assert payload["tables"]["products"] == [{"id": 1, "name": "Produit A"}]

    engine.dispose()


def test_logical_import_ignores_admin_tables_in_external_backup(tmp_path, monkeypatch):
    """Même si un ancien backup contient users / activity_logs, la restauration
    ne doit pas toucher à ces tables : la base active les préserve."""
    source_path = tmp_path / "old_backup.db"
    target_path = tmp_path / "active.db"

    def make_engine(path):
        engine = create_engine(f"sqlite:///{path}")

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        return engine

    source_engine = make_engine(source_path)
    target_engine = make_engine(target_path)
    metadata = MetaData()
    users = Table(
        "users",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("username", String),
    )
    products = Table(
        "products",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String),
    )
    metadata.create_all(source_engine)
    metadata.create_all(target_engine)

    # L'ancien backup contient users + products
    with source_engine.begin() as connection:
        connection.execute(users.insert(), {"id": 1, "username": "old_admin"})
        connection.execute(products.insert(), {"id": 1, "name": "Old Product"})

    # La base active a ses propres users et un ancien produit
    with target_engine.begin() as connection:
        connection.execute(users.insert(), {"id": 1, "username": "current_admin"})
        connection.execute(products.insert(), {"id": 5, "name": "Current Product"})

    monkeypatch.setattr(database_manager_module, "engine", target_engine)

    result = DatabaseManager().restore_database(str(source_path))

    assert result["success"] is True, result["message"]

    with target_engine.connect() as connection:
        # users n'a pas été purgé ni réécrit : le compte actuel est préservé
        assert connection.execute(users.select()).mappings().all() == [
            {"id": 1, "username": "current_admin"}
        ]
        # products a bien été restauré depuis le backup
        assert connection.execute(products.select()).mappings().all() == [
            {"id": 1, "name": "Old Product"}
        ]

    source_engine.dispose()
    target_engine.dispose()