"""Diagnostic LECTURE SEULE : correspondance public.users <-> auth.users."""
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

JOIN = text("""
    select u.id, u.username, u.email, u.role, u.active,
           (a.id is not null) as has_auth,
           (i.identity_id is not null) as has_identity
      from public.users u
      left join auth.users a on lower(a.email) = lower(u.email)
      left join (
            select user_id, min(id::text) as identity_id
              from auth.identities group by user_id
      ) i on i.user_id = a.id
     order by u.id
""")

ORPHANS = text("""
    select a.id, a.email, a.created_at
      from auth.users a
      left join public.users u on lower(u.email) = lower(a.email)
     where u.id is null
     order by a.created_at
""")

try:
    engine = create_engine(url)
    with engine.connect() as conn:
        print("== public.users <-> auth.users ==")
        print(f"  {'uid':<4}{'username':<18}{'email':<32}{'role':<14}{'act':<6}{'auth':<6}{'ident'}")
        for r in conn.execute(JOIN):
            print(f"  {r.id:<4}{str(r.username):<18}{str(r.email):<32}{str(r.role):<14}"
                  f"{str(r.active):<6}{str(r.has_auth):<6}{r.has_identity}")

        print()
        print("== Comptes auth.users SANS profil public.users ==")
        rows = list(conn.execute(ORPHANS))
        if not rows:
            print("  aucun")
        for r in rows:
            print(f"  {r.id}  {r.email}  {r.created_at}")
except Exception as exc:
    print("ERREUR:", type(exc).__name__, str(exc)[:400])