"""Tests PostgreSQL multi-tenant (0004-0006 + RLS).

Securite (REGLES ABSOLUES) :
- SKIPPED sauf si KORGO_TEST_DATABASE_URL pointe vers une base de TEST.
- Garde-fou : URL supabase.co exige KORGO_TEST_TARGET=staging (sinon FAIL).
- Aucun secret n'est affiche : les URLs sont masquees.
"""
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[1]
ORG_FUNCS_SQL = ROOT / "supabase_org_functions.sql"
RLS_SQL = ROOT / "supabase_rls_multitenant.sql"

NOT_NULL_TABLES = (
    "customers", "suppliers", "products", "stores", "sales",
    "sale_items", "payments", "sale_returns", "sale_return_items",
    "proforma_invoices", "proforma_invoice_items",
    "inventory_movements", "stock_alerts", "purchase_orders",
    "purchase_order_items", "treasury_accounts", "treasury_movements",
    "cash_register_sessions", "monthly_closures", "activity_logs",
    "sale_logs",
)


def _masked(url: str) -> str:
    return re.sub(r"://[^@]*@", "://***@", url)


def get_test_url() -> str:
    url = (os.environ.get("KORGO_TEST_DATABASE_URL")
           or os.environ.get("TEST_DATABASE_URL") or "").strip()
    if not url:
        pytest.skip("KORGO_TEST_DATABASE_URL non defini : test PG ignore.")
    low = url.lower()
    hostname = urlsplit(url).hostname or ""
    is_supabase = hostname == "supabase.co" or hostname.endswith(
        (".supabase.co", ".supabase.com"))
    if is_supabase and os.environ.get("KORGO_TEST_TARGET") != "staging":
        pytest.fail(
            "Refus de migration distante : KORGO_TEST_TARGET=staging requis.")
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url.split("://", 1)[1]
    if not (low.startswith("postgresql") or low.startswith("postgres")):
        pytest.skip(f"URL non-PostgreSQL ({_masked(url)[:40]}...).")
    return url


def make_engine(url: str):
    return create_engine(
        url,
        connect_args={"sslmode": os.environ.get("DB_SSLMODE", "prefer"),
                      "connect_timeout": 10},
        pool_pre_ping=True,
    )


def test_sql_files_sans_secrets_et_complets():
    """Statique, sans DB : pas de secret, fonctions/politiques attendues."""
    for path in (ORG_FUNCS_SQL, RLS_SQL):
        assert path.exists(), f"manquant : {path.name}"
    funcs = ORG_FUNCS_SQL.read_text(encoding="utf-8")
    rls = RLS_SQL.read_text(encoding="utf-8")
    for secret in ("service_role", "sb_secret_", "BEGIN PRIVATE KEY"):
        assert secret not in funcs and secret not in rls, secret
    for fn in ("current_organization_ids", "is_member_of",
               "is_admin_in_org", "current_member_role"):
        assert fn in funcs, fn
    for pol in ("org_read_", "org_tenant_gate", "org_delete_admin_gate"):
        assert pol in rls, pol



def test_pg_upgrade_head_backfill_et_not_null(monkeypatch):
    """Chaine 0001->0006 sur base PG de TEST (vide)."""
    url = get_test_url()
    from alembic import command
    from alembic.config import Config
    # env.py loads .env. Override DATABASE_URL explicitly so the migration
    # cannot silently fall back to the application's configured database.
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config(str(ROOT / "alembic.ini"))
    command.upgrade(cfg, "head")
    eng = make_engine(url)
    try:
        insp = inspect(eng)
        names = set(insp.get_table_names())
        assert "organizations" in names
        assert "organization_members" in names
        with eng.connect() as conn:
            ver = conn.execute(
                text("SELECT version_num FROM alembic_version")).scalar()
            assert ver == "0006_organization_id_required", ver
            n_org = conn.execute(
                text("SELECT COUNT(*) FROM organizations")).scalar()
            # Base vide mais migrations 0002/0003 creent 1 magasin + 1 ligne
            # app_settings : le backfill 0005 rattache donc 1 organisation
            # KORGO-DEFAULT (memes donnees que le test SQLite).
            assert n_org == 1, n_org
        for table in NOT_NULL_TABLES:
            col = next(c for c in insp.get_columns(table)
                       if c["name"] == "organization_id")
            assert col["nullable"] is False, table
    finally:
        eng.dispose()


def test_pg_meme_code_deux_organisations():
    """Meme code MAG-TEST-PG dans 2 orgs = OK (nettoye apres)."""
    url = get_test_url()
    eng = make_engine(url)
    try:
        from uuid import uuid4
        from sqlalchemy.orm import sessionmaker
        from core.models.organization import Organization
        from core.models.store import Store
        S = sessionmaker(bind=eng)
        s = S()
        suffix = uuid4().hex[:12].upper()
        code = f"MAG-{suffix}"
        org_codes = (f"A-{suffix}", f"B-{suffix}")
        try:
            o1 = Organization(name="Test A", code=org_codes[0])
            o2 = Organization(name="Test B", code=org_codes[1])
            s.add_all([o1, o2])
            s.commit()
            assert o1.id != o2.id
            s.add_all([
                Store(code=code, name="M1", organization_id=o1.id),
                Store(code=code, name="M1b", organization_id=o2.id),
            ])
            s.commit()
            n = s.execute(text(
                "SELECT COUNT(*) FROM stores WHERE code=:code"), {"code": code}
            ).scalar()
            assert n == 2, n
        finally:
            s.execute(text("DELETE FROM stores WHERE code=:code"),
                       {"code": code})
            s.execute(text("DELETE FROM organizations WHERE code IN (:a,:b)"),
                       {"a": org_codes[0], "b": org_codes[1]})
            s.commit()
            s.close()
    finally:
        eng.dispose()


def test_pg_fonctions_et_politiques():
    """Fonctions app_security + org_* (SKIP si SQL non deploye)."""
    url = get_test_url()
    eng = make_engine(url)
    try:
        with eng.connect() as conn:
            rows = conn.execute(text(
                "SELECT proname FROM pg_proc p JOIN pg_namespace n"
                " ON n.oid=p.pronamespace"
                " WHERE n.nspname='app_security'")).fetchall()
            names = {r[0] for r in rows}
            expected = {"current_organization_ids", "is_member_of",
                        "is_admin_in_org", "current_member_role"}
            if not expected.issubset(names):
                pytest.skip(f"fonctions manquantes : {sorted(names)}")
            n = conn.execute(text(
                "SELECT COUNT(*) FROM pg_policies"
                " WHERE schemaname='public'"
                " AND policyname LIKE 'org\\_%' ESCAPE '\\'")).scalar()
            if not n or n < 10:
                pytest.skip(f"RLS non deploye ({n})")
            assert n >= 10
    finally:
        eng.dispose()
