# ============================================================================
# Supabase Auth = SOURCE DE VERITE UNIQUE des comptes (desktop + web).
#
# REGLE D'ARCHITECTURE :
#   - auth.users (Supabase Auth) detient l'EMAIL, le MOT DE PASSE et le STATUT ;
#   - public.users n'est qu'un PROFIL (username, role, active,
#     must_change_password, last_login) relie par email et alimente par les
#     triggers `on_auth_user_changed` / `on_auth_user_deleted` ;
#   - AUCUN mot de passe n'est plus stocke en local : toute creation, tout
#     changement de mot de passe, d'email, d'activation ou toute suppression
#     passe par ce module.
#
# Deux chemins possibles, sans jamais dupliquer les credentials :
#   1. API REST Supabase Auth (recommande) — utilise si SUPABASE_URL +
#      SUPABASE_ANON_KEY sont renseignes dans l'environnement ;
#   2. acces direct a Postgres/Supabase (auth.users) — toujours disponible
#      pour l'app desktop (connexion SQLAlchemy existante), sans cle
#      supplementaire a gerer.
#
# Les deux ecrivent dans la MEME table auth.users : il n'y a jamais deux
# verites. `password_matches_auth_hash()` reproduit exactement la verification
# bcrypt de Supabase Auth (GoTrue), donc un compte cree ici est utilisable sur
# le web et inversement.
# ============================================================================
import json
import os
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import text

# Sonde "auth.users est-il joignable ?" mise en cache par moteur.
_PROBE_CACHE = {}

# Colonnes ecrites dans auth.users — jeu valide pour GoTrue : les jetons non
# utilises doivent rester a '' (chaine vide) et non NULL.
_AUTH_COLUMNS = (
    "instance_id, id, aud, \"role\", email, encrypted_password, "
    "email_confirmed_at, raw_app_meta_data, raw_user_meta_data, "
    "created_at, updated_at, confirmation_token, recovery_token, "
    "email_change_token_new, email_change, email_change_token_current, "
    "phone_change_token, phone_change, email_change_confirm_status"
)


def _norm(email):
    return (email or "").strip().lower()


def hash_password(password):
    """Hash bcrypt au format attendu par Supabase Auth ($2b$)."""
    return bcrypt.hashpw(str(password).encode(), bcrypt.gensalt()).decode()


def password_matches_auth_hash(password, auth_hash):
    """Reproduit la verification bcrypt de Supabase Auth (GoTrue).

    GoTrue stocke le mot de passe en bcrypt ; `bcrypt.checkpw` accepte les
    prefixes $2a$ / $2b$ / $2y$ utilises par Supabase.
    """
    if not password or not auth_hash:
        return False
    try:
        return bcrypt.checkpw(str(password).encode(), str(auth_hash).encode())
    except (ValueError, TypeError):
        return False


def supabase_available(db):
    """True si la connexion pointe vers un Supabase dont auth.users est lisible."""
    try:
        bind = db.get_bind()
    except Exception:
        return False
    engine = getattr(bind, "engine", None)
    if engine is None or engine.dialect.name != "postgresql":
        return False
    key = id(engine)
    if key not in _PROBE_CACHE:
        try:
            db.execute(text("select 1 from auth.users limit 1"))
            _PROBE_CACHE[key] = True
        except Exception:
            _PROBE_CACHE[key] = False
    return _PROBE_CACHE[key]


def resolve_email(db, identifier):
    """Email correspondant a un username OU a un email (insensible a la casse)."""
    ident = (identifier or "").strip()
    if not ident:
        return None
    try:
        row = db.execute(text(
            "select email from public.users "
            " where lower(username) = lower(:i) or lower(email) = lower(:i) "
            " order by (lower(email) = lower(:i)) desc limit 1"
        ), {"i": ident}).scalar()
        if row:
            return _norm(row)
        return db.execute(text(
            "select email from auth.users where lower(email) = lower(:i) limit 1"
        ), {"i": ident}).scalar()
    except Exception:
        return None


def get_auth_id(db, email):
    """Identifiant auth.users associe a un email (ou None)."""
    try:
        return db.execute(
            text("select id from auth.users where lower(email) = :e"),
            {"e": _norm(email)},
        ).scalar()
    except Exception:
        return None
# ---------------------------------------------------------------------------
# API REST Supabase Auth (optionnelle : SUPABASE_URL + SUPABASE_ANON_KEY)
# ---------------------------------------------------------------------------
def _rest_config():
    """(url, cle) de l'API Supabase Auth, ou (None, None) si non configuree."""
    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = (os.environ.get("SUPABASE_ANON_KEY")
           or os.environ.get("SUPABASE_PUBLISHABLE_KEY") or "")
    if not url:
        # Repli : deduire l'URL du projet depuis la chaine Postgres
        # (utilisateur `postgres.<ref>` des poolers Supabase).
        db_url = os.environ.get("DATABASE_URL", "")
        user = db_url.split("://", 1)[-1].split("@")[0].split("/")[-1]
        if user.startswith("postgres.") and ":" in user:
            ref = user.split(".", 1)[1].split(":")[0]
            if ref:
                url = f"https://{ref}.supabase.co"
    return (url, key) if url and key else (None, None)


def rest_sign_in(email, password):
    """Connexion via l'API Supabase Auth (GoTrue). Retourne (ok, message)."""
    base, key = _rest_config()
    if not base:
        return False, "API REST Supabase non configuree"
    body = json.dumps({"email": _norm(email), "password": password}).encode()
    req = urllib.request.Request(
        base + "/auth/v1/token?grant_type=password",
        data=body,
        headers={"apikey": key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read() or b"{}")
        if payload.get("access_token"):
            return True, "Authentifie par Supabase Auth"
        return False, "Reponse Supabase Auth invalide"
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read() or b"{}")
        except Exception:
            detail = {}
        msg = (detail.get("error_description") or detail.get("msg")
               or detail.get("error") or f"HTTP {exc.code}")
        return False, msg
    except Exception as exc:  # reseau indisponible -> repli SQL
        return False, f"API Supabase Auth injoignable : {exc}"


# ---------------------------------------------------------------------------
# Verification des identifiants
# ---------------------------------------------------------------------------
def verify_credentials(db, email, password):
    """Verifie un couple email / mot de passe dans Supabase Auth.

    Retourne (ok: bool, message: str). Le mot de passe est compare au hash
    bcrypt stocke par Supabase Auth : aucune copie locale n'est utilisee.
    """
    email = _norm(email)
    if not email or not password:
        return False, "Email ou mot de passe manquant"

    # 1) Voie REST (GoTrue) si elle est configuree : delegation complete.
    base, _ = _rest_config()
    if base:
        ok, msg = rest_sign_in(email, password)
        if ok:
            return True, msg
        # API injoignable (reseau) -> repli SQL ; refus explicite -> on s'arrete.
        if "injoignable" not in msg:
            return False, msg

    # 2) Repli : verification directe du hash Supabase Auth (auth.users).
    try:
        row = db.execute(text(
            "select encrypted_password, banned_until, deleted_at, email_confirmed_at "
            "  from auth.users where lower(email) = :e"
        ), {"e": email}).one_or_none()
        if row is None:
            return False, "Aucun compte Supabase Auth pour cet email"
        if row.deleted_at is not None:
            return False, "Compte supprime"
        if (row.banned_until is not None
                and row.banned_until > datetime.now(timezone.utc)):
            return False, "Compte desactive"
        if not password_matches_auth_hash(password, row.encrypted_password):
            return False, "Mot de passe incorrect"
        return True, "Authentifie par Supabase Auth"
    except Exception as exc:
        db.rollback()
        return False, f"Verification Supabase Auth impossible : {exc}"
# ---------------------------------------------------------------------------
# Ecritures : creation / mot de passe / email / statut / suppression
#
# Toutes les fonctions renvoient (ok: bool, message: str) et sont idempotentes.
# Le PROFIL public.users est ensuite synchronise par le trigger Supabase
# (`on_auth_user_changed`) : on ne l'ecrit pas a la main pour eviter les
# divergences.
# ---------------------------------------------------------------------------
def _metadata(username=None, role=None, active=True, must_change_password=True):
    """Metadonnees lues par le trigger pour construire le profil."""
    meta = {
        "active": bool(active),
        "must_change_password": bool(must_change_password),
    }
    if username:
        meta["username"] = str(username)
    if role:
        meta["role"] = str(role)
    return json.dumps(meta, ensure_ascii=False)


def provision_auth_user(db, email, password, username=None, role=None,
                        active=True, must_change_password=True):
    """Cree (ou reinitialise) le compte Supabase Auth d'un utilisateur.

    C'est LE point d'entree unique de la creation d'utilisateur : le compte
    n'existe nulle part ailleurs. Le profil public.users est cree par le
    trigger Supabase a partir des metadonnees (username, role, active).
    """
    email = _norm(email)
    if not email or "@" not in email:
        return False, "Email manquant ou invalide : Supabase Auth l'exige"
    if not password or len(str(password)) < 6:
        return False, "Mot de passe trop court (6 caracteres minimum)"
    pwd_hash = hash_password(password)
    meta = _metadata(username, role, active, must_change_password)
    try:
        db.execute(text(f"""
            insert into auth.users ({_AUTH_COLUMNS})
            values ('00000000-0000-0000-0000-000000000000'::uuid, gen_random_uuid(),
                    'authenticated', 'authenticated', :email, :pwd_hash, now(),
                    '{{"provider":"email","providers":["email"]}}'::jsonb,
                    cast(:meta as jsonb), now(), now(),
                    '', '', '', '', '', '', '', 0)
            on conflict do nothing
        """), {"email": email, "pwd_hash": pwd_hash, "meta": meta})

        # Unicite de l'email garantie par un index partiel : `on conflict do
        # nothing` ne suffit pas, on traite donc explicitement le cas existant.
        if int(db.execute(text(
                "select count(*) from auth.users where lower(email) = :e"),
                {"e": email}).scalar() or 0) > 0:
            db.execute(text("""
                update auth.users
                   set encrypted_password = :pwd_hash,
                       email_confirmed_at = coalesce(email_confirmed_at, now()),
                       banned_until = case when :active then null
                                           else now() + interval '100 years' end,
                       updated_at = now(),
                       raw_user_meta_data = coalesce(raw_user_meta_data, '{}'::jsonb)
                           || cast(:meta as jsonb)
                 where lower(email) = :email
            """), {
                "email": email,
                "pwd_hash": pwd_hash,
                "meta": meta,
                "active": bool(active),
            })
        return True, "Compte Supabase Auth provisionne"
    except Exception as exc:
        db.rollback()
        return False, f"Creation Supabase Auth impossible : {exc}"


def update_auth_password(db, email, password, must_change_password=False):
    """Change le mot de passe du compte Supabase Auth (source de verite)."""
    email = _norm(email)
    if not email:
        return False, "Email manquant"
    if not password or len(str(password)) < 6:
        return False, "Mot de passe trop court (6 caracteres minimum)"
    try:
        res = db.execute(text("""
            update auth.users
               set encrypted_password = :pwd_hash,
                   email_confirmed_at = coalesce(email_confirmed_at, now()),
                   updated_at = now(),
                   raw_user_meta_data = coalesce(raw_user_meta_data, '{}'::jsonb)
                       || jsonb_build_object('must_change_password', :mcp)
             where lower(email) = :e
        """), {
            "e": email,
            "pwd_hash": hash_password(password),
            "mcp": bool(must_change_password),
        })
        if res.rowcount == 0:
            return False, "Aucun compte Supabase Auth pour cet email"
        return True, "Mot de passe Supabase Auth mis a jour"
    except Exception as exc:
        db.rollback()
        return False, f"Mise a jour Supabase Auth impossible : {exc}"
def update_auth_email(db, old_email, new_email):
    """Renomme l'email du compte Supabase Auth.

    Le trigger `on_auth_user_changed` deplace le profil public.users associe.
    Si aucun compte n'existe pour l'ancien email, on provisionne le nouveau.
    """
    old_email = _norm(old_email)
    new_email = _norm(new_email)
    if not new_email or "@" not in new_email:
        return False, "Nouvel email manquant ou invalide"
    try:
        res = db.execute(text("""
            update auth.users
               set email = :ne, email_confirmed_at = now(), updated_at = now()
             where lower(email) = :oe
        """), {"oe": old_email, "ne": new_email})
        if res.rowcount == 0:
            # L'ancien compte n'existait pas : on cree le nouveau. Le mot de
            # passe devra etre reinitialise par l'administrateur.
            return provision_auth_user(db, new_email, secrets.token_urlsafe(16),
                                       must_change_password=True)
        return True, "Email Supabase Auth synchronise"
    except Exception as exc:
        db.rollback()
        return False, f"Mise a jour Supabase Auth impossible : {exc}"


def delete_auth_user(db, email):
    """Supprime le compte Supabase Auth (le trigger supprime le profil)."""
    email = _norm(email)
    if not email:
        return True, "Rien a faire (pas d'email)"
    try:
        db.execute(text("delete from auth.users where lower(email) = :e"),
                   {"e": email})
        return True, "Compte Supabase Auth supprime"
    except Exception as exc:
        db.rollback()
        return False, f"Suppression Supabase Auth impossible : {exc}"


def set_auth_active(db, email, active):
    """Active / desactive le compte Supabase Auth (bannissement GoTrue).

    Le compte et son mot de passe sont CONSERVES : seule la connexion est
    refusee (web comme desktop). Plus besoin de supprimer puis recreer.
    """
    email = _norm(email)
    if not email:
        return False, "Email manquant"
    try:
        res = db.execute(text("""
            update auth.users
               set banned_until = case when :active then null
                                       else now() + interval '100 years' end,
                   updated_at = now(),
                   raw_user_meta_data = coalesce(raw_user_meta_data, '{}'::jsonb)
                       || jsonb_build_object('active', :active)
             where lower(email) = :e
        """), {"e": email, "active": bool(active)})
        if res.rowcount == 0:
            return False, "Aucun compte Supabase Auth pour cet email"
        return True, ("Compte Supabase Auth active" if active
                      else "Compte Supabase Auth desactive")
    except Exception as exc:
        db.rollback()
        return False, f"Changement de statut Supabase Auth impossible : {exc}"


def list_auth_users(db):
    """Comptes Supabase Auth (diagnostic / rapprochement des profils)."""
    try:
        return db.execute(text(
            "select id, email, created_at, banned_until, deleted_at "
            "  from auth.users order by created_at"
        )).all()
    except Exception:
        return []
def update_auth_profile(db, email, username=None, role=None, active=None,
                        new_email=None):
    """Met a jour les metadonnees Supabase Auth d'un compte (profil).

    Le trigger `on_auth_user_changed` repercute ensuite username / role /
    active / email sur public.users : une seule ecriture suffit, le profil ne
    peut donc pas diverger du compte.
    """
    email = _norm(email)
    if not email:
        return False, "Email manquant"

    payload = {}
    if username:
        payload["username"] = str(username)
    if role:
        payload["role"] = str(role)
    if active is not None:
        payload["active"] = bool(active)

    try:
        res = db.execute(text("""
            update auth.users
               set email = coalesce(cast(:new_email as text), email),
                   updated_at = now(),
                   banned_until = case
                       when cast(:active as boolean) is null then banned_until
                       when cast(:active as boolean) then null
                       else now() + interval '100 years' end,
                   raw_user_meta_data = coalesce(raw_user_meta_data, '{}'::jsonb)
                       || cast(:meta as jsonb)
             where lower(email) = :e
        """), {
            "e": email,
            "new_email": _norm(new_email) or None,
            "active": None if active is None else bool(active),
            "meta": json.dumps(payload, ensure_ascii=False),
        })
        if res.rowcount == 0:
            return False, "Aucun compte Supabase Auth pour cet email"
        return True, "Profil Supabase Auth synchronise"
    except Exception as exc:
        db.rollback()
        return False, f"Mise a jour Supabase Auth impossible : {exc}"