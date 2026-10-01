"""Diagnostic des SESSIONS Supabase Auth (base de la regle « une seule session »).

Verifie ce sur quoi repose le verrou multi-sessions :
  1. existence et colonnes de `auth.sessions` (id, user_id, updated_at, not_after) ;
  2. sessions actuellement ouvertes par utilisateur ;
  3. presence de `auth.jwt()` (lecture des claims dans les RPC) ;
  4. presence du claim `session_id` dans un access token reel (creation d'un
     compte de test jetable, connexion via l'API Auth, decodage du JWT).

Usage : python _diag_user_sessions.py
"""
import base64
import json
import os
import urllib.error
import urllib.request
import uuid

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


def engine_from_env():
    load_dotenv(".env")
    url = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+psycopg2://")
    return create_engine(url, connect_args={"sslmode": "require"})


def show_schema(c):
    print("== auth.sessions (colonnes) ==")
    rows = c.execute(text("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'auth' AND table_name = 'sessions'
        ORDER BY ordinal_position""")).all()
    if not rows:
        print("   (table absente)")
    for r in rows:
        print(f"   {r[0]:22} {r[1]:26} null={r[2]}")

    print("\n== auth.sessions (dernieres lignes) ==")
    try:
        for r in c.execute(text("""
            SELECT s.id, u.email, s.created_at, s.updated_at, s.not_after,
                   s.ip, left(coalesce(s.user_agent, ''), 45)
            FROM auth.sessions s
            JOIN auth.users u ON u.id = s.user_id
            ORDER BY s.updated_at DESC
            LIMIT 10""")):
            print(f"   {str(r[0])[:8]}... {str(r[1])[:30]:30} cree={r[2]} "
                  f"maj={r[3]} fin={r[4]} ip={r[5]}")
    except Exception as exc:                                   # noqa: BLE001
        print(f"   lecture impossible : {type(exc).__name__}: {exc}")

    print("\n== helpers auth utilises par les RPC ==")
    for r in c.execute(text("""
        SELECT p.proname, pg_get_function_result(p.oid)
        FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'auth'
          AND p.proname IN ('jwt', 'uid', 'role', 'email')
        ORDER BY p.proname""")):
        print(f"   auth.{r[0]}() -> {r[1]}")


def rest_credentials():
    """URL + cle publique Supabase depuis mobile/.env puis web/.env."""
    for path, url_key, key_key in (
        ("mobile/.env", "EXPO_PUBLIC_SUPABASE_URL",
         "EXPO_PUBLIC_SUPABASE_ANON_KEY"),
        ("web/.env", "VITE_SUPABASE_URL", "VITE_SUPABASE_ANON_KEY"),
    ):
        if not os.path.exists(path):
            continue
        values = {}
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    values[k.strip()] = v.strip().strip('"')
        url = values.get(url_key)
        key = (values.get(key_key)
               or values.get("EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
               or values.get("VITE_SUPABASE_PUBLISHABLE_KEY"))
        if url and key:
            return url, key, path
    return None, None, None


def decode_jwt(token):
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def probe_session_claim(engine):
    """Cree un compte jetable, se connecte, verifie le claim `session_id`."""
    url, key, source = rest_credentials()
    if not url:
        print("\n== claim session_id : IGNORE (aucune .env Supabase trouvee) ==")
        return

    email = f"probe-session-{uuid.uuid4().hex[:10]}@korgo-pro.test"
    password = uuid.uuid4().hex + "Aa1!"
    print(f"\n== claim session_id (compte jetable via {source}) ==")

    with engine.begin() as c:
        c.execute(text("""
            INSERT INTO auth.users (
                instance_id, id, aud, "role", email, encrypted_password,
                email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
                created_at, updated_at, confirmation_token, recovery_token,
                email_change_token_new, email_change,
                email_change_token_current, phone_change_token, phone_change,
                email_change_confirm_status)
            VALUES ('00000000-0000-0000-0000-000000000000'::uuid,
                    gen_random_uuid(), 'authenticated', 'authenticated', :email,
                    crypt(:pwd, gen_salt('bf')), now(),
                    '{"provider":"email","providers":["email"]}'::jsonb,
                    jsonb_build_object('username', :uname, 'role', 'CAISSIER',
                                       'active', false),
                    now(), now(), '', '', '', '', '', '', '', 0)"""),
            {"email": email, "pwd": password, "uname": email.split("@")[0]})

    try:
        request = urllib.request.Request(
            f"{url.rstrip('/')}/auth/v1/token?grant_type=password",
            data=json.dumps({"email": email, "password": password}).encode(),
            headers={"apikey": key, "Content-Type": "application/json"},
            method="POST")
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read())
        claims = decode_jwt(payload["access_token"])
        print("   claims du JWT :", ", ".join(sorted(claims.keys())))
        print("   session_id    :", claims.get("session_id"))
        print("   jti           :", claims.get("jti"))
        with engine.connect() as c:
            known = c.execute(text(
                "SELECT id FROM auth.sessions WHERE user_id = :u"),
                {"u": claims.get("sub")}).scalar()
        print("   auth.sessions :", known)
        print("   VERDICT       :",
              "claim present" if claims.get("session_id") else "claim ABSENT")
    except urllib.error.HTTPError as exc:                      # noqa: BLE001
        print(f"   connexion impossible : {exc.code} {exc.read()[:200]!r}")
    finally:
        with engine.begin() as c:
            c.execute(text("DELETE FROM auth.users WHERE email = :e"), {"e": email})
        print("   (compte jetable supprime)")


def main():
    engine = engine_from_env()
    with engine.connect() as c:
        show_schema(c)
    probe_session_claim(engine)


if __name__ == "__main__":
    main()
