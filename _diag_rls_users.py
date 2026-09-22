"""Diagnostic LECTURE SEULE : policies RLS + formats de hash existants."""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from sqlalchemy import create_engine, text

url = os.environ.get("DATABASE_URL", "")
if url.startswith("postgresql:"):
    url = "postgresql+psycopg2://" + url.split("://", 1)[1]

HASHES = text("""
    select id, username, email,
           case when password_hash like '$2%' then 'bcrypt'
                when password_hash ~ '^[0-9a-f]{64}$' then 'sha256'
                else 'autre' end as fmt,
           left(password_hash, 7) as prefix
      from public.users order by id
""")

POLICIES = text("""
    select tablename, policyname, cmd, roles::text, qual, with_check
      from pg_policies
     where schemaname = 'public' and tablename in ('users')
     order by policyname
""")

RLS_FLAGS = text("""
    select c.relname, c.relrowsecurity as rls_enabled, c.relforcerowsecurity as rls_forced
      from pg_class c join pg_namespace n on n.oid = c.relnamespace
     where n.nspname = 'public' and c.relname in ('users')
""")

EXT = text("select extname, extnamespace::regnamespace::text from pg_extension order by 1")

GRANTS = text("""
    select grantee, privilege_type
      from information_schema.role_table_grants
     where table_schema='public' and table_name='users'
     order by grantee, privilege_type
""")

try:
    engine = create_engine(url)
    with engine.connect() as conn:
        print("== Formats de password_hash (public.users) ==")
        for r in conn.execute(HASHES):
            print(f"  id={r.id:<3} {str(r.username):<12} {str(r.email):<32} {r.fmt:<8} {r.prefix}")

        print()
        print("== RLS public.users ==")
        for r in conn.execute(RLS_FLAGS):
            print(f"  {r.relname}: enabled={r.rls_enabled} forced={r.rls_forced}")

        print()
        print("== Policies public.users ==")
        for r in conn.execute(POLICIES):
            print(f"  [{r.policyname}] cmd={r.cmd} roles={r.roles}")
            print(f"      using     = {str(r.qual)[:160]}")
            print(f"      with check= {str(r.with_check)[:160]}")

        print()
        print("== Extensions ==")
        for r in conn.execute(EXT):
            print(f"  {r.extname:<24} -> {r[1]}")

        print()
        print("== Grants sur public.users ==")
        for r in conn.execute(GRANTS):
            print(f"  {r.grantee:<24} {r.privilege_type}")
except Exception as exc:
    print("ERREUR:", type(exc).__name__, str(exc)[:400])