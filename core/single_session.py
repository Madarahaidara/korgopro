"""Session unique : un SEUL appareil connecte par compte Korgo Pro (desktop).

CONTEXTE
--------
Le logiciel de bureau se connecte DIRECTEMENT a PostgreSQL (SQLAlchemy) : il
n'a ni JWT Supabase Auth ni claim `session_id`. Il genere donc un UUID local et
appelle les RPC `app_desktop_session_*` (voir supabase_single_session.sql) :

    app_desktop_session_open(email, session_id, device, force)  -> connexion
    app_desktop_session_touch(session_id, email, device)        -> 5 min
    app_desktop_session_close(session_id, raison)               -> sortie

PRINCIPE DE SECURITE : FAIL-OPEN
---------------------------------
Une erreur reseau, une base non migree ou une RPC absente ne doit JAMAIS
empêcher un caissier de travailler. Dans ce cas on journalise et on laisse
passer (`None` = information indisponible, l'appelant n'agit pas). Seul un
refus EXPLICITE du serveur (`ok = false`, `code = SESSION_ACTIVE`) bloque.

Abreviations : le module expose un objet unique `session` (etat partage par
AuthController / MainWindow).
"""
import logging
import socket
import uuid
from datetime import datetime

from sqlalchemy import text

from core.database import SessionLocal, get_dialect_name

logger = logging.getLogger(__name__)

PLATFORM = "desktop"

# Duree sans battement au-dela de laquelle la session est jugee abandonnee
# (miroir de app_security.session_timeout() cote SQL).
HEARTBEAT_SECONDS = 300


def device_label() -> str:
    """Nom lisible du poste, affiche a l'utilisateur dans le message de refus."""
    try:
        host = socket.gethostname() or "poste"
    except Exception:  # noqa: BLE001 - l'OS peut refuser
        host = "poste"
    return f"Poste {host}"


def _uuid_ok(value) -> bool:
    """Un identifiant de session est un UUID (jamais une chaine libre)."""
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def _call(sql: str, params: dict):
    """Execute une RPC de session. Retourne le jsonb, ou None si indisponible."""
    if get_dialect_name() != "postgresql":
        # Repli de developpement (SQLite locale) : pas de verrou possible.
        return None
    try:
        with SessionLocal() as db:
            row = db.execute(text(sql), params).scalar()
            db.commit()
            return row if isinstance(row, dict) else None
    except Exception as exc:  # noqa: BLE001 - indisponible != refus
        logger.warning("[session] verrou multi-appareils indisponible : %s", exc)
        return None


class SingleSession:
    """Etat de session applicative du poste (module = singleton)."""

    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.email = None
        self.unavailable = False

    # ------------------------------------------------------------------
    def reset(self):
        """Nouvelle tentative de connexion : nouvel identifiant de session."""
        self.session_id = str(uuid.uuid4())
        self.email = None

    def forget(self):
        """Session fermee cote application (deconnexion, fermeture)."""
        self.email = None

    # ------------------------------------------------------------------
    def open(self, email, force: bool = False) -> dict:
        """Ouvre la session du compte. Refus explicite -> `code` = SESSION_ACTIVE."""
        if not email:
            return {"ok": False, "code": "UNKNOWN_USER",
                    "message": "Email de session manquant."}
        res = _call(
            "SELECT public.app_desktop_session_open("
            "  :email, CAST(:sid AS uuid), :device, :force) AS r",
            {"email": email, "sid": self.session_id,
             "device": device_label(), "force": bool(force)},
        )
        if res is None:
            # Indisponible : on laisse passer (fail-open).
            self.email = email
            return {"ok": True, "unavailable": True}
        if res.get("ok"):
            self.email = email
        elif res.get("code") == "SESSION_ACTIVE":
            # Refus : cette session ne detient PAS le verrou.
            self.email = None
        return res

    def touch(self) -> dict:
        """Battement de coeur. `active: False` = session reprise, se deconnecter."""
        if not self.email:
            return None
        res = _call(
            "SELECT public.app_desktop_session_touch("
            "  CAST(:sid AS uuid), :email, :device) AS r",
            {"sid": self.session_id, "email": self.email,
             "device": device_label()},
        )
        if res is None:
            return None
        if res.get("ok") and res.get("active") is False:
            self.forget()
        elif res.get("ok") and res.get("revived"):
            # Notre session avait ete expiree puis nous reprenons la main.
            self.email = res.get("email") or self.email
        return res

    def close(self, reason: str = "FERMETURE_APPLICATION") -> None:
        """Libere le verrou (deconnexion ou fermeture de l'application)."""
        if not self.email or not _uuid_ok(self.session_id):
            self.forget()
            return
        _call(
            "SELECT public.app_desktop_session_close("
            "  CAST(:sid AS uuid), :reason) AS r",
            {"sid": self.session_id, "reason": reason},
        )
        self.forget()

    def status(self) -> dict:
        """Etat lisible (journal de demarrage / support)."""
        return {
            "session_id": self.session_id,
            "email": self.email,
            "platform": PLATFORM,
            "device": device_label(),
            "opened_at": self.opened_at,
            "unavailable": self.unavailable,
            "server_time": datetime.utcnow().isoformat(timespec="seconds"),
        }

    opened_at = None


# Etat partage : AuthController (connexion) et MainWindow (battement / sortie).
session = SingleSession()
