"""Etat des acces desktop vs web (Supabase Auth)."""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from dotenv import load_dotenv; load_dotenv()
import os
from sqlalchemy import create_engine, text as t
e = create_engine(os.environ['DATABASE_URL'])
c = e.connect()
print('--- public.users (desktop + web) ---')
for r in c.execute(t("select id, username, email, role, active, (password_hash is not null) as has_pwd from users order by id")):
    print(f'id={r.id} {r.username:12s} {str(r.email):32s} {r.role:12s} actif={r.active} pwd_hash={r.has_pwd}')
print()
print('--- auth.users (Supabase Auth = acces web) ---')
for r in c.execute(t('select id, email, email_confirmed_at is not null as confirmed, created_at from auth.users order by id')):
    print(f'{str(r.email):32s} confirme={r.confirmed} cree={r.created_at:%Y-%m-%d}')
print()
print('--- liens profile <-> auth (via raw_user_meta_data ou identite) ---')
for r in c.execute(t("""
    select u.email, u.id as auth_id, p.id as profile_id, p.role
    from auth.users u left join users p on lower(p.email)=lower(u.email)
    order by u.email""")):
    print(f'{str(r.email):32s} auth_id={str(r.auth_id)[:8]} profile_id={r.profile_id} role={r.role}')
