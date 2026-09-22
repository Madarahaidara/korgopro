"""Test bout-en-bout de la refonte "creation d'utilisateur = Supabase uniquement".

Verifie que Supabase Auth est la source de verite unique :
  1. provision_auth_user cree le compte auth.users ET le profil (trigger) ;
  2. aucun mot de passe local n'est stocke (public.users.password_hash vide) ;
  3. la connexion desktop (AuthController) accepte email OU username ;
  4. changement de mot de passe -> ancien refuse, nouveau accepte (desktop + web) ;
  5. desactivation -> connexion refusee (desktop ET web), mot de passe conserve ;
  6. reactivation -> connexion a nouveau possible ;
  7. changement d'email -> le profil suit, connexion avec le nouvel email ;
  8. suppression -> profil supprime par le trigger, plus aucune connexion.

Usage : python _test_supabase_only_users.py
Nettoyage automatique en fin de test.
"""
import io
import json
import sys
import urllib.error
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import os

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, ".env"))

from sqlalchemy import create_engine, text  # noqa: E402

from controllers.auth_controller import AuthController  # noqa: E402
from core.supabase_auth import (  # noqa: E402
    delete_auth_user,
    provision_auth_user,
    set_auth_active,
    supabase_available,
    update_auth_email,
    update_auth_password,
    update_auth_profile,
    verify_credentials,
)

URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
KEY = (os.environ.get("SUPABASE_ANON_KEY")
       or os.environ.get("SUPABASE_PUBLISHABLE_KEY") or "")
# La cle publique vit dans web/.env (comme pour _test_auth_sync.py).
if not KEY:
    web_env = os.path.join(ROOT, "web", ".env")
    if os.path.exists(web_env):
        with io.open(web_env, encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VITE_SUPABASE_ANON_KEY="):
                    KEY = line.split("=", 1)[1].strip()
                elif line.startswith("VITE_SUPABASE_URL=") and not URL:
                    URL = line.split("=", 1)[1].strip().rstrip("/")
if not URL:
    db_url = os.environ.get("DATABASE_URL", "")
    user = db_url.split("://", 1)[-1].split("@")[0].split("/")[-1]
    if user.startswith("postgres.") and ":" in user:
        URL = "https://" + user.split(".", 1)[1].split(":")[0] + ".supabase.co"

EMAIL = "_test_supabase_only@example.com"
EMAIL2 = "_test_supabase_only_renamed@example.com"
USERNAME = "_testsupabaseonly"
PWD = "Test#Supabase2026"
PWD2 = "New#Supabase2027"

FAILS = []


def check(name, ok, detail=""):
    print(("OK    " if ok else "ECHEC ") + name + (f"  -- {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)
    return ok


def web_login(email, pwd):
    """Connexion via l'API Supabase Auth (comme le fait l'app web)."""
    if not KEY:
        return None, {"msg": "cle publique absente (test web ignore)"}
    body = json.dumps({"email": email, "password": pwd}).encode()
    req = urllib.request.Request(
        URL + "/auth/v1/token?grant_type=password", data=body,
        headers={"apikey": KEY, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read() or b"{}")
        except Exception:
            return exc.code, {}


url = os.environ["DATABASE_URL"]
if url.startswith("postgresql:"):
    url = "postgresql+psycopg2://" + url.split("://", 1)[1]
engine = create_engine(url)


def cleanup():
    with engine.begin() as conn:
        conn.execute(text("delete from auth.users where lower(email) in (:a, :b)"),
                     {"a": EMAIL, "b": EMAIL2})
        conn.execute(text("delete from public.users where lower(email) in (:a, :b)"),
                     {"a": EMAIL, "b": EMAIL2})


cleanup()
controller = AuthController()
db = engine.connect()

try:
    print("== 0. Supabase Auth joignable ==")
    from core.database import SessionLocal
    with SessionLocal() as session:
        check("0. auth.users accessible", supabase_available(session))
    print()

    print("== 1. Creation : Supabase Auth + profil par trigger ==")
    ok, msg = provision_auth_user(db, EMAIL, PWD, username=USERNAME, role="CAISSIER")
    db.commit()
    check("1a. provision_auth_user", ok, msg)

    row = db.execute(text(
        "select username, role, active, coalesce(password_hash, '<null>') as ph "
        "  from public.users where lower(email) = :e"), {"e": EMAIL}).one_or_none()
    check("1b. profil public.users cree par le trigger", row is not None,
          str(row.username) if row else "absent")
    if row:
        check("1c. username propage", row.username == USERNAME, str(row.username))
        check("1d. role propage", row.role == "CAISSIER", str(row.role))
        check("1e. compte actif par defaut", bool(row.active) is True, str(row.active))
        check("1f. AUCUN mot de passe local (password_hash vide)", row.ph == "",
              f"password_hash={row.ph!r}")
    print()

    print("== 2. Connexion desktop (AuthController -> Supabase Auth) ==")
    by_username = controller.authenticate(USERNAME, PWD)
    check("2a. connexion desktop par username", by_username is not None,
          str(by_username.get("email")) if by_username else "refusee")
    by_email = controller.authenticate(EMAIL, PWD)
    check("2b. connexion desktop par email", by_email is not None)
    check("2c. mauvais mot de passe refuse",
          controller.authenticate(USERNAME, "mauvais-mdp") is None)
    check("2d. verifier avec mauvais mot de passe -> False",
          controller.verify_password(USERNAME, "mauvais-mdp") is False)
    print()

    print("== 3. Connexion web (GoTrue) avec le meme compte ==")
    status, payload = web_login(EMAIL, PWD)
    if status is None:
        print("     (ignore : cle publique Supabase absente)")
    else:
        check("3a. login web accepte", status == 200,
              f"HTTP {status} {payload.get('error_description') or payload.get('msg') or ''}")
    print()

    print("== 4. Changement de mot de passe (desktop -> Supabase Auth) ==")
    ok, msg = update_auth_password(db, EMAIL, PWD2, must_change_password=False)
    db.commit()
    check("4a. update_auth_password", ok, msg)
    check("4b. ancien mot de passe refuse (desktop)",
          controller.authenticate(USERNAME, PWD) is None)
    check("4c. nouveau mot de passe accepte (desktop)",
          controller.authenticate(USERNAME, PWD2) is not None)
    if KEY:
        status, _ = web_login(EMAIL, PWD)
        check("4d. ancien mot de passe refuse (web)", status != 200, f"HTTP {status}")
        status, _ = web_login(EMAIL, PWD2)
        check("4e. nouveau mot de passe accepte (web)", status == 200, f"HTTP {status}")
    print()

    print("== 5. Desactivation : refus desktop ET web, mot de passe conserve ==")
    ok, msg = set_auth_active(db, EMAIL, False)
    db.commit()
    check("5a. set_auth_active(False)", ok, msg)
    active_flag = db.execute(text(
        "select active from public.users where lower(email) = :e"), {"e": EMAIL}).scalar()
    check("5b. profil marque inactif par le trigger", active_flag is False, str(active_flag))
    check("5c. connexion desktop refusee",
          controller.authenticate(USERNAME, PWD2) is None)
    if KEY:
        status, _ = web_login(EMAIL, PWD2)
        check("5d. connexion web refusee", status != 200, f"HTTP {status}")
    pwd_kept = db.execute(text(
        "select encrypted_password is not null from auth.users where lower(email) = :e"),
        {"e": EMAIL}).scalar()
    check("5e. mot de passe CONSERVE (pas de suppression du compte)", bool(pwd_kept))
    print()

    print("== 6. Reactivation ==")
    ok, msg = set_auth_active(db, EMAIL, True)
    db.commit()
    check("6a. set_auth_active(True)", ok, msg)
    check("6b. connexion desktop a nouveau possible",
          controller.authenticate(USERNAME, PWD2) is not None)
    if KEY:
        status, _ = web_login(EMAIL, PWD2)
        check("6c. connexion web a nouveau possible", status == 200, f"HTTP {status}")
    print()

    print("== 7. Changement d'email (profil suit le compte) ==")
    ok, msg = update_auth_profile(db, EMAIL, username="testsupabaseonly2",
                                 role="GERANT", new_email=EMAIL2)
    db.commit()
    check("7a. update_auth_profile", ok, msg)
    renamed = db.execute(text(
        "select username, role from public.users where lower(email) = :e"),
        {"e": EMAIL2}).one_or_none()
    check("7b. profil deplace vers le nouvel email", renamed is not None,
          str(renamed) if renamed else "absent")
    if renamed:
        check("7c. username mis a jour", renamed.username == "testsupabaseonly2",
              str(renamed.username))
        check("7d. role mis a jour", renamed.role == "GERANT", str(renamed.role))
    check("7e. connexion desktop avec le nouveau nom",
          controller.authenticate("testsupabaseonly2", PWD2) is not None)
    check("7f. connexion desktop avec le nouveau email",
          controller.authenticate(EMAIL2, PWD2) is not None)
    leftover = db.execute(text(
        "select count(*) from public.users where lower(email) = :e"), {"e": EMAIL}).scalar()
    check("7g. aucun profil residuel sur l'ancien email", int(leftover or 0) == 0,
          str(leftover))
    print()

    print("== 8. Suppression : compte + profil disparaissent ==")
    ok, msg = delete_auth_user(db, EMAIL2)
    db.commit()
    check("8a. delete_auth_user", ok, msg)
    remaining = db.execute(text(
        "select count(*) from public.users where lower(email) = :e"),
        {"e": EMAIL2}).scalar()
    check("8b. profil supprime par le trigger", int(remaining or 0) == 0, str(remaining))
    check("8c. connexion desktop impossible",
          controller.authenticate(EMAIL2, PWD2) is None)
    if KEY:
        status, _ = web_login(EMAIL2, PWD2)
        check("8d. connexion web impossible", status != 200, f"HTTP {status}")
    print()
finally:
    db.close()
    cleanup()
    print("NETTOYAGE : comptes de test supprimes (auth.users + public.users)")

print()
print("RESULTAT :", "TOUS OK" if not FAILS else f"ECHECS -> {FAILS}")
sys.exit(1 if FAILS else 0)