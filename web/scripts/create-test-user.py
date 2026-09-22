"""Création d'un compte de test SUPABASE AUTH via Self-Service Signup.

L'API Admin (/auth/v1/admin/users) exige la clé `service_role` (secrete).
Le endpoint public /auth/v1/signup n'en a pas besoin : il suffit de la
clé publique (anon/publishable). Attention toutefois :
  - si le projet a désactivé le signup, l'appel échoue (403 signup_disabled) ;
  - de nouveaux utilisateurs ne sont pas "email_confirmed" par défaut.
"""
import json, urllib.request, urllib.error, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from dotenv import dotenv_values

cfg = dotenv_values(os.path.join(os.path.dirname(__file__), '..', '.env'))
base = cfg['VITE_SUPABASE_URL'].rstrip('/')
key = cfg['VITE_SUPABASE_ANON_KEY']
email = "test.user@korgo-pro.com"
pwd = "Test#12345"
url = f"{base}/auth/v1/signup"
body = json.dumps({'email': email, 'password': pwd}).encode()
req = urllib.request.Request(
    url, data=body,
    headers={'apikey': key, 'Content-Type': 'application/json', 'Prefer': 'return=minimal'},
    method='POST',
)
try:
    r = urllib.request.urlopen(req, timeout=15)
    print("Signup HTTP", r.status)
    print("Réponse:", r.read().decode()[:200])
    if r.status == 200:
        print("Compte créé ; vérifiez confirmation email dans le Dashboard.")
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read().decode()[:400])
except Exception as e:
    print("ERR:", type(e).__name__, str(e)[:200])
