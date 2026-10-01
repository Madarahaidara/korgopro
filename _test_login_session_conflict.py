# -*- coding: utf-8 -*-
"""Test hors écran du refus « compte déjà connecté ailleurs » (LoginView).

Vérifie la gestion de la session unique côté interface desktop :
 * refus SESSION_ACTIVE -> message métier + bouton « Déconnecter l'autre
   appareil et se connecter », identifiants conservés (ils sont justes) ;
 * clic sur ce bouton -> nouvelle tentative avec force=True ;
 * mauvais mot de passe -> message générique, bouton masqué, mdp effacé.

Lancement : python _test_login_session_conflict.py
(0 requête réseau : AuthController.authenticate est remplacé par un faux.)
"""
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from controllers.auth_controller import AuthController  # noqa: E402
from ui.views.login_view import LoginView  # noqa: E402

ECHECS = []
# Historique des appels au faux authenticate : {"username", "force"}.
APPELS = []
# Résultat que le faux authenticate doit produire à l'appui.
REPONSE = {"user": None, "error": None, "code": None}


def check(label, condition, detail=""):
    """Assert remplaçable : ne lance pas d'exception, totalise les échecs."""
    ok = bool(condition)
    print(f"[{'OK  ' if ok else 'ECHEC'}] {label}"
          + (f" -> {detail}" if detail and not ok else ""))
    if not ok:
        ECHECS.append(label)


def _faux_authenticate(self, username, password, force=False):
    """Remplace AuthController.authenticate (aucun appel Supabase)."""
    APPELS.append({"username": username, "force": force})
    self.last_error = REPONSE["error"]
    self.last_error_code = REPONSE["code"]
    return REPONSE["user"]


AuthController.authenticate = _faux_authenticate


def tenter(view, clic_reprise=False):
    """Lance une tentative de connexion et attend la fin du worker."""
    if clic_reprise:
        view.btn_takeover.click()
    else:
        view.on_login_pressed()
    worker = getattr(view, "worker", None)
    if worker is not None:
        worker.wait(8000)
    # Livre les signaux mis en file depuis le thread du worker.
    for _ in range(20):
        app.processEvents()
        time.sleep(0.01)


view = LoginView()
view.show()
app.processEvents()
view.username.input.setText("admin")
view.password.input.setText("secret")

check("0. bouton de reprise créé et masqué au démarrage",
      view.btn_takeover.isHidden())

# --- 1. Refus SESSION_ACTIVE : message métier + bouton, mdp conservé --------
REPONSE.update(
    user=None,
    code="SESSION_ACTIVE",
    error="Deja connecte ailleurs : logiciel de bureau (Chrome - Windows 10) "
          "depuis 3 min. Choisissez « Déconnecter l'autre appareil » pour "
          "reprendre la main.",
)
tenter(view)
check("1. tentative initiale SANS force",
      APPELS and APPELS[-1]["force"] is False, str(APPELS[-1:]))
check("2. message métier affiché",
      "Deja connecte ailleurs" in view.error_label.text(),
      view.error_label.text())
check("3. bouton de reprise visible", not view.btn_takeover.isHidden())
check("4. identifiants conservés (le mot de passe est juste)",
      view.password.text() == "secret", repr(view.password.text()))

# --- 2. Clic sur le bouton : reprise avec force=True -----------------------
REPONSE.update(user={"id": 1, "username": "admin", "role": "ADMIN"},
               error=None, code=None)
tenter(view, clic_reprise=True)
check("5. reprise envoyée avec force=True",
      APPELS[-1]["force"] is True, str(APPELS[-1:]))
check("6. bouton masqué après reprise", view.btn_takeover.isHidden())
check("7. état « Connecté » affiché",
      "Connect" in view.btn_login.text(), view.btn_login.text())

# --- 3. Mauvais mot de passe : aucun bouton, mdp effacé --------------------
view.password.input.setText("mauvais")
REPONSE.update(user=None, error=None, code=None)
tenter(view)
check("8. message générique de mauvais identifiants",
      "Identifiants incorrects" in view.error_label.text(),
      view.error_label.text())
check("9. bouton de reprise masqué", view.btn_takeover.isHidden())
check("10. mot de passe effacé",
      view.password.text() == "", repr(view.password.text()))

# --- 4. Autre refus avec message métier mais code non-SESSION_ACTIVE -------
# (ex. profil inconnu) : message affiché, mais PAS de bouton de reprise.
view.password.input.setText("secret")
REPONSE.update(user=None, error="Profil introuvable.", code="UNKNOWN_USER")
tenter(view)
check("11. message métier non-SESSION_ACTIVE affiché",
      "Profil introuvable" in view.error_label.text(),
      view.error_label.text())
check("12. pas de bouton de reprise hors SESSION_ACTIVE",
      view.btn_takeover.isHidden())

print("-" * 60)
if ECHECS:
    print(f"ECHECS: {len(ECHECS)}")
    for e in ECHECS:
        print(f"  - {e}")
    sys.exit(1)
print("TOUT OK - controles de session au login passes")
sys.exit(0)
