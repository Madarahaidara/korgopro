"""Test bout-en-bout : provision desktop -> connexion web (Supabase Auth)."""
import io, sys, json, urllib.request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from dotenv import load_dotenv; load_dotenv()
import os
from sqlalchemy import create_engine, text as t
from core.supabase_auth_sync import provision_auth_user, update_auth_password, delete_auth_user

load_dotenv()
engine = create_engine(os.environ['DATABASE_URL'])
URL = 'https://tvvvgrqzcjtzdqxhnxtc.supabase.co'
KEY = open('web/.env', encoding='utf-8').read().split('VITE_SUPABASE_ANON_KEY=')[1].splitlines()[0].strip()
EMAIL = '_test_sync@example.com'
PWD = 'Test#Sync2026'

fails = []
def check(name, ok, detail=''):
    print(('OK   ' if ok else 'ECHEC') + f'  {name}' + (f' -- {detail}' if detail else ''))
    if not ok: fails.append(name)

def web_login(email, pwd):
    body = json.dumps({'email': email, 'password': pwd}).encode()
    req = urllib.request.Request(
        URL + '/auth/v1/token?grant_type=password', data=body,
        headers={'apikey': KEY, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

with engine.begin() as conn:
    conn.execute(t("delete from auth.users where lower(email)=:e"), {'e': EMAIL})
    conn.execute(t("delete from users where lower(email)=:e"), {'e': EMAIL})

db = engine.connect()
try:
    # 1. Provision via le module (comme le ferait la vue admin)
    ok, msg = provision_auth_user(db, EMAIL, PWD, username='testsync', role='CAISSIER')
    db.commit()
    check('1. provision_auth_user', ok, msg)

    # 2. Connexion web REELLE avec le mot de passe en clair
    status, resp = web_login(EMAIL, PWD)
    check('2. login web (mot de passe pgcrypto accepte)', status == 200 and resp.get('user', {}).get('email') == EMAIL,
          f"HTTP {status} {resp.get('error_description') or resp.get('msg') or ''}")

    # 3. Changement de mot de passe + re-login
    PWD2 = 'New#Password9'
    ok, msg = update_auth_password(db, EMAIL, PWD2)
    db.commit()
    check('3. update_auth_password', ok, msg)
    status, resp = web_login(EMAIL, PWD2)
    check('3b. login web avec le NOUVEAU mot de passe', status == 200, f'HTTP {status}')
    status, _ = web_login(EMAIL, PWD)
    check('3c. ANCIEN mot de passe refuse', status != 200, f'HTTP {status}')

    # 4. Suppression de l'acces web
    ok, msg = delete_auth_user(db, EMAIL)
    db.commit()
    check('4. delete_auth_user', ok, msg)
    status, _ = web_login(EMAIL, PWD2)
    check('4b. login refuse apres suppression', status != 200, f'HTTP {status}')
finally:
    db.close()
    with engine.begin() as conn:
        conn.execute(t("delete from auth.users where lower(email)=:e"), {'e': EMAIL})
        conn.execute(t("delete from users where lower(email)=:e"), {'e': EMAIL})
print('NETTOYAGE: comptes test supprimes')
print()
print('RESULTAT:', 'TOUS OK' if not fails else f'ECHECS: {fails}')
