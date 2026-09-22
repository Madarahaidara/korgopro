"""Exécute supabase_rls_policies.sql contre la base Supabase active.

Usage : python sync_rls_to_supabase.py [--dry-run]
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except Exception:
    pass

from sqlalchemy import create_engine, text

url = os.environ.get("DATABASE_URL", "")
if not url or url.startswith("sqlite"):
    print("[ERREUR] DATABASE_URL doit pointer vers PostgreSQL/Supabase.")
    sys.exit(1)
if url.startswith("postgresql:"):
    url = "postgresql+psycopg2://" + url.split("://", 1)[1]

with open(os.path.join(PROJECT_ROOT, "supabase_rls_policies.sql"), encoding="utf-8-sig") as f:
    sql = f.read()

# Découpage en instructions : split sur ';' en ignorant les $$ ... $$ (corps
# des fonctions / blocs DO) et les commentaires '-- ...' (fin de ligne).
parts, buf = [], []
in_dollar = in_comment = False
i, n = 0, len(sql)
while i < n:
    if in_comment:
        if sql[i] == "\n":
            in_comment = False
            buf.append(sql[i])
        i += 1
        continue
    if sql.startswith("--", i):
        in_comment = True
        i += 2
        continue
    if sql.startswith("$$", i):
        in_dollar = not in_dollar
        buf.append("$$")
        i += 2
        continue
    if not in_dollar and sql[i] == ";":
        parts.append("".join(buf).strip())
        buf = []
        i += 1
        continue
    buf.append(sql[i])
    i += 1
if "".join(buf).strip():
    parts.append("".join(buf).strip())

stmts = [p for p in parts
         if p and not all(l.strip().startswith("--") or not l.strip()
                          for l in p.splitlines())]

engine = create_engine(url, connect_args={"sslmode": "require"})

with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
    who = conn.execute(text("SELECT current_user")).scalar()
    print(f"[OK] Connecté à Supabase en tant que : {who}")

    if "--dry-run" in sys.argv:
        print(f"[DRY-RUN] {len(stmts)} instructions détectées.")
        sys.exit(0)

    print(f"[1/2] Exécution de {len(stmts)} instructions (autocommit)...")
    raw = conn.connection.driver_connection.cursor()
    errors = 0
    for idx, stmt in enumerate(stmts, 1):
        first = next((l.strip() for l in stmt.splitlines()
                      if l.strip() and not l.strip().startswith("--")), "")
        try:
            raw.execute(stmt)
        except Exception as exc:
            errors += 1
            print(f"  [ERREUR] #{idx} {first[:70]!r} -> {str(exc).splitlines()[0]}")
    if errors:
        print(f"  ({errors} instruction(s) en échec — voir ci-dessus)")

    print("[2/2] Vérification de l'état RLS :")
    rows = conn.execute(text(
        "SELECT c.relname, c.relrowsecurity, "
        "(SELECT count(*) FROM pg_policies p "
        " WHERE p.schemaname='public' AND p.tablename=c.relname) "
        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND c.relkind='r' ORDER BY c.relname"))
    for name, rls, npol in rows:
        print(f"   - {name:28s} RLS={rls}  policies={npol}")

print("\nTerminé.")
