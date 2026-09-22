"""Liste les domaines autorisés et la configuration du signup Supabase Auth."""
import urllib.request, urllib.error, sys, os, json
from dotenv import dotenv_values

cfg = dotenv_values('.env')
base = cfg['VITE_SUPABASE_URL'].rstrip('/')
key = cfg['VITE_SUPABASE_ANON_KEY']
headers = {'apikey': key, 'Authorization': f'Bearer {key}'}

r = urllib.request.urlopen(urllib.request.Request(f'{base}/auth/v1/settings', headers=headers), timeout=15)
d = json.loads(r.read())
print(json.dumps(d, indent=2, ensure_ascii=False)[:2000])

print('=== Résumé clé ===')
print('Signup autorisé:', d.get('signup_allows_public'))
print('Signup désactivé:', d.get('disable_signup'))
print('Confirmation email requise:', d.get('confirmable', 'indéfini'))
print('Domaines whitelistés:', d.get('allowed_domains', 'tous acceptés'))
print('Redirect URLs:', d.get('external_url', '—'))