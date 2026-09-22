"""Smoke test Lot 1 : navigation par role (offscreen). Temporaire."""
import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication, QMessageBox

app = QApplication([])

refused = []
QMessageBox.warning = staticmethod(lambda *a, **k: (refused.append(a[2] if len(a) > 2 else ""), QMessageBox.StandardButton.Ok)[1])
QMessageBox.critical = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

from ui.views.main_window import MENU_ENTRIES, MainWindow

print("role            | boutons visibles")
print("-" * 70)
for role in ["ADMIN", "GESTIONNAIRE", "GERANT", "Gestionnaire", "SUPERVISEUR", "ASSISTANT", "CAISSIER", "STOCKIST"]:
    window = MainWindow({"id": 1, "username": "test", "role": role}, "light")
    visible = [attr.replace("btn_", "") for attr, _p, _v, _t in MENU_ENTRIES
               if getattr(window, attr).isVisibleTo(window)]
    print(f"{role:15s} | {', '.join(visible)}")
    # Garde Parametres
    window._check_and_switch_to_settings()
    titre = window.page_title.text()
    print(f"{'':15s} | apres clic Parametres -> page = {titre!r}")
    window.close()
    window.deleteLater()
    app.processEvents()

# Les vues créent des QThread de rafraîchissement : sortie immédiate pour ne
# pas attendre leur terminaison (script de validation uniquement).
os._exit(0)
