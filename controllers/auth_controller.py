"""Authentification de l'application desktop.

ARCHITECTURE : Supabase Auth (auth.users) est la SOURCE DE VERITE des comptes.
`authenticate()` resout le username en email puis delegue la verification du
mot de passe a Supabase Auth (core.supabase_auth) : aucun mot de passe n'est
plus verifie contre une copie locale.

REPLI DE DEVELOPPEMENT : si la base active n'est pas Supabase (SQLite locale
sans schema `auth`, utilisee par les tests), on retombe sur l'ancienne
verification bcrypt/SHA256 de public.users.password_hash. Ce repli n'existe
que pour permettre le developpement hors-ligne : il n'est jamais utilise
lorsque Supabase est disponible.
"""
from datetime import datetime

from core.database import SessionLocal
from core.models.user import User
from core.security import (
    _is_bcrypt_hash,
    migrate_old_hash,
    verify_password as verify_password_hash,
)
from core.supabase_auth import resolve_email, supabase_available, verify_credentials


class AuthController:
    def authenticate(self, username: str, password: str):
        """Authentifier un utilisateur (Supabase Auth en priorite)."""
        try:
            with SessionLocal() as session:
                if supabase_available(session):
                    return self._authenticate_supabase(session, username, password)
                return self._authenticate_local(session, username, password)
        except Exception as e:
            print(f"Erreur d'authentification: {e}")
            return None

    # ------------------------------------------------------------------
    # Source de verite : Supabase Auth
    # ------------------------------------------------------------------
    def _authenticate_supabase(self, session, username: str, password: str):
        email = resolve_email(session, username)
        if not email:
            return None

        ok, message = verify_credentials(session, email, password)
        if not ok:
            # Message volontairement generique cote appelant (pas d'oracle).
            print(f"[AUTH] Refus Supabase Auth pour '{username}' : {message}")
            return None

        user = session.query(User).filter(User.email == email).first()
        if not user or not user.active:
            # Compte banni cote Supabase Auth, ou profil desactive : l'acces
            # desktop suit le meme statut que l'acces web.
            return None

        user.last_login = datetime.utcnow()
        session.commit()
        return self._as_dict(user)

    # ------------------------------------------------------------------
    # Repli de developpement (SQLite sans Supabase Auth)
    # ------------------------------------------------------------------
    def _authenticate_local(self, session, username: str, password: str):
        user = session.query(User).filter(User.username == username).first()
        if not user or not user.active:
            return None

        if verify_password_hash(password, user.password_hash):
            user.last_login = datetime.utcnow()

            # Migration automatique SHA256 -> bcrypt (repli uniquement).
            if user.password_hash and not _is_bcrypt_hash(user.password_hash):
                user.password_hash = migrate_old_hash(password, user.password_hash)
                print(f"[INFO] Mot de passe de '{user.username}' migre SHA256 vers bcrypt")

            session.commit()
            return self._as_dict(user)
        return None

    @staticmethod
    def _as_dict(user):
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "active": user.active,
            "last_login": user.last_login,
        }

    def verify_password(self, username: str, password: str) -> bool:
        """Verifie un mot de passe (actions sensibles)."""
        try:
            with SessionLocal() as session:
                if supabase_available(session):
                    email = resolve_email(session, username)
                    if not email:
                        return False
                    ok, _ = verify_credentials(session, email, password)
                    return ok

                user = session.query(User).filter(User.username == username).first()
                if not user:
                    return False
                return verify_password_hash(password, user.password_hash)
        except Exception as e:
            print(f"Erreur lors de la vérification du mot de passe: {e}")
            return False

    def get_user_by_id(self, user_id: int):
        """Récupérer un utilisateur par son ID"""
        try:
            with SessionLocal() as session:
                user = session.query(User).filter(User.id == user_id).first()
                if user:
                    return {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "role": user.role,
                        "active": user.active,
                        "created_at": user.created_at,
                        "last_login": user.last_login
                    }
                return None
        except Exception as e:
            print(f"Erreur lors de la récupération de l'utilisateur: {e}")
            return None