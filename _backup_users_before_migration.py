"""Sauvegarde (lecture seule) de public.users + auth.users avant migration.

Ecrit un JSON horodate a la racine, sans jamais modifier la base.
Usage : python _backup_users_before_migration.py
"""
import json
import os
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from sqlalchemy import create_engine, text

url = os.environ.get("DATABASE_URL", "")
if url.startswith("postgresql:"):
    url = "postgresql+psycopg2://" + url.split("://", 1)[1]

engine = create_engine(url)
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
out = os.path.join(PROJECT_ROOT, f"users_backup_{stamp}.json")

with engine.connect() as conn:
    public_rows = [dict(r._mapping) for r in conn.execute(text(
        "select id, username, email, role, active, created_at, last_login, "
        "       last_ip, must_change_password, password_hash "
        "  from public.users order by id"))]
    auth_rows = [dict(r._mapping) for r in conn.execute(text(
        "select id, email, created_at, banned_until, deleted_at, "
        "       email_confirmed_at, raw_user_meta_data, "
        "       left(encrypted_password, 10) as enc_prefix "
        "  from auth.users order by created_at"))]

payload = {"created_at": stamp, "public_users": public_rows, "auth_users": auth_rows}
with open(out, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2, ensure_ascii=False, default=str)

print(f"[OK] Sauvegarde ecrite : {os.path.basename(out)}")
print(f"     {len(public_rows)} profil(s) public.users, {len(auth_rows)} compte(s) auth.users")
for r in public_rows:
    print(f"     - id={r['id']} {r['username']} <{r['email']}> role={r['role']} actif={r['active']}")