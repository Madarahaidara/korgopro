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
    #: Dernier refus metier (session deja ouverte ailleurs) affiche par la vue.
    #: `None` = pas de probleme particular.
    last_error = None
    #: Code brut du refus (`SESSION_ACTIVE`, ...) : permet a la vue de savoir
    #: si elle doit proposer la reprise de main (« Deconnecter l'autre ... »).
    last_error_code = None

    def authenticate(self, username: str, password: str, force: bool = False):
        """Authentifier un utilisateur (Supabase Auth en priorite).

        SESSION UNIQUE : apres verification du mot de passe, la session
        applicative est ouverte (core.single_session). Si un autre appareil est
        deja connecte a ce compte, la connexion est REFUSEE (None) et
        `last_error` / `last_error_code` expliquent pourquoi (affiches par
        LoginView, qui propose alors la reprise avec `force=True`). Une panne
        reseau ou une base non migree ne bloque jamais la connexion
        (fail-open, cf. core.single_session).
        """
        # Chaque tentative repart d'un blanc : un refus de session ne doit pas
        # s'afficher apres un simple mauvais mot de passe (et inversement).
        self.last_error = None
        self.last_error_code = None
        try:
            with SessionLocal() as session:
                if supabase_available(session):
                    return self._authenticate_supabase(
                        session, username, password, force)
                return self._authenticate_local(session, username, password)
        except Exception as e:
            print(f"Erreur d'authentification: {e}")
            return None

    # ------------------------------------------------------------------
    # Source de verite : Supabase Auth
    # ------------------------------------------------------------------
    def _authenticate_supabase(self, session, username: str, password: str,
                               force: bool = False):
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
            self.last_error = None
            return None

        # Session unique : un seul appareil connecte par compte.
        self.last_error = self._open_single_session(email, force=force)
        if self.last_error:
            return None

        user.last_login = datetime.utcnow()
        session.commit()
        return self._as_dict(user)

    def _open_single_session(self, email: str, force: bool = False):
        """Ouvre la session applicative. Retourne un message si elle est refusee.

        Le refus doit intervenir AVANT `last_login` : un compte refuse ne doit
        pas laisser d'heure de connexion « reussie » dans l'historique.
        """
        from core import single_session

        holder = single_session.session
        held = (holder.email or "").strip().lower()
        target = (email or "").strip().lower()

        # Ecran verrouille : ce poste DETIENT deja le verrou. Un reset() avec
        # un nouvel UUID ferait croire au serveur qu'il s'agit d'un AUTRE
        # appareil, et la connexion serait refusee a tort. On rafraichit la
        # session existante (touch) au lieu d'en ouvrir une nouvelle.
        if not force and held and held == target:
            state = holder.touch()
            if state is None or state.get("active") is not False:
                # Session toujours la notre (ou verrou indisponible :
                # fail-open, cf. core.single_session).
                return None
            # Session reprise par un autre appareil : on retente une ouverture
            # normale, qui sera refusee (sauf force) avec le code metier.

        # Changement de compte sur ce poste : liberer le verrou de l'ancien.
        if holder.email and held != target:
            holder.close("CHANGEMENT_COMPTE")

        self.last_error_code = None
        holder.reset()
        result = holder.open(email, force=force)
        if result.get("ok"):
            holder.opened_at = datetime.utcnow()
            return None
        self.last_error_code = result.get("code")

        if result.get("code") != "SESSION_ACTIVE":
            # Erreur metier explicite (compte inconnu, profil inactif...).
            return result.get("message") or (
                "Connexion refusee par le verrou de session."
            )
        # SESSION_ACTIVE : la vue affiche le message et propose le bouton
        # « Déconnecter l'autre appareil et se connecter » (force=True).
        other = result.get("other") or {}
        device = other.get("platform_label") or "un autre appareil"
        if other.get("device"):
            device = f"{device} ({other['device']})"
        return (
            f"Deja connecte ailleurs : {device} depuis "
            f"{other.get('since_minutes', 0)} min. "
            "Choisissez « Déconnecter l'autre appareil » pour reprendre la main."
        )

    def close_session(self, reason: str = "DECONNEXION") -> None:
        """Libere le verrou de session (deconnexion / fermeture)."""
        from core import single_session

        single_session.session.close(reason)

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