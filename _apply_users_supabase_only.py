"""Applique supabase_users_supabase_only.sql a la base Supabase active.

Rend la creation des utilisateurs exclusivement dependante de Supabase Auth :
  - public.users devient une table de PROFIL (plus de mot de passe local) ;
  - triggers auth.users -> public.users (creation / renommage / suppression) ;
  - backfill des comptes orphelins dans les deux sens ;
  - RPC administrateur pour l'app web (sans cle service_role).

Usage :
    python _apply_users_supabase_only.py [--dry-run]

Idempotent : peut etre rejoue sans risque.
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

SQL_FILE = os.path.join(PROJECT_ROOT, "supabase_users_supabase_only.sql")
with open(SQL_FILE, encoding="utf-8-sig") as f:
    sql = f.read()

# Decoupage en instructions : split sur ';' en ignorant les corps $$ ... $$ et
# les commentaires '-- ...' (meme approche que sync_rls_to_supabase.py).
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

# Ne conserver que les instructions reellement executables (pas de commentaires
# seuls, pas de requetes de verification commentees).
stmts = [p for p in parts
         if p and not all(l.strip().startswith("--") or not l.strip()
                          for l in p.splitlines())]

engine = create_engine(url, connect_args={"sslmode": "require"})

with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
    who = conn.execute(text("SELECT current_user")).scalar()
    print(f"[OK] Connecte a Supabase en tant que : {who}")

    if "--dry-run" in sys.argv:
        print(f"[DRY-RUN] {len(stmts)} instructions detectees :")
        for idx, stmt in enumerate(stmts, 1):
            first = next((l.strip() for l in stmt.splitlines()
                          if l.strip() and not l.strip().startswith("--")), "")
            print(f"  {idx:2d}. {first[:95]}")
        sys.exit(0)

    print(f"[1/3] Execution de {len(stmts)} instructions (autocommit)...")
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
        print(f"  ({errors} instruction(s) en echec -- voir ci-dessus)")
    else:
        print("  Toutes les instructions ont ete appliquees.")

    print("[2/3] Triggers sur auth.users :")
    for (name,) in conn.execute(text(
        "select t.tgname from pg_trigger t "
        "join pg_class c on c.oid = t.tgrelid "
        "join pg_namespace n on n.oid = c.relnamespace "
        "where n.nspname = 'auth' and c.relname = 'users' and not t.tgisinternal "
        "order by t.tgname"
    )):
        print(f"   - {name}")

    print("[3/3] Correspondance public.users <-> auth.users :")
    rows = conn.execute(text(
        "select u.id, u.username, u.email, u.role, u.active, "
        "       (a.id is not null) as has_auth "
        "  from public.users u "
        "  left join auth.users a on lower(a.email) = lower(u.email) "
        " order by u.id"
    )).all()
    orphan = 0
    for r in rows:
        flag = "OK" if r.has_auth else "!! SANS COMPTE SUPABASE AUTH"
        if not r.has_auth:
            orphan += 1
        print(f"   - id={r.id:<3} {str(r.username):<14} {str(r.email):<34} "
              f"{str(r.role):<12} actif={str(r.active):<5} {flag}")

    rpc = conn.execute(text(
        "select p.proname from pg_proc p join pg_namespace n on n.oid = p.pronamespace "
        "where n.nspname = 'public' and p.proname like 'admin_%' order by 1"
    )).all()
    print("RPC administrateur installees : " + (", ".join(r[0] for r in rpc) or "aucune"))

    print()
    if orphan:
        print(f"[ATTENTION] {orphan} profil(s) sans compte Supabase Auth.")
    else:
        print("[OK] Tous les profils possedent un compte Supabase Auth.")

print("\nTermine.")