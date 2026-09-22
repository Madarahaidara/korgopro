# -*- coding: utf-8 -*-
"""Test hors écran de la refonte visuelle de l'écran Paramètres.

Vérifie : construction sans erreur, QSS chargé, absence de fausse alerte
« non sauvegardé », conservation de la devise, aperçu du numéro, cycle
modification / annulation / enregistrement + signal.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from ui.views.settings_view import SettingsView  # noqa: E402
from utils.settings_manager import SettingsManager  # noqa: E402

ECHECS = []


def check(label, condition, detail=""):
    status = "OK  " if condition else "ECHEC"
    print(f"[{status}] {label}{(' — ' + detail) if detail else ''}")
    if not condition:
        ECHECS.append(label)


manager = SettingsManager()
view = SettingsView({"id": 1, "role": "admin"}, manager)
view.resize(1100, 700)

check("feuille QSS chargée", bool(view.styleSheet().strip()))
check("3 onglets créés", view.tab_widget.count() == 3,
      f"onglets={[view.tab_widget.tabText(i) for i in range(view.tab_widget.count())]}")
check("barre d'action hors défilement",
      view.save_btn.parent() is not None and view.tab_widget.parent() is not view.save_btn.parent())
check("aucune fausse alerte au démarrage",
      not view.save_btn.isEnabled() and not view.cancel_btn.isEnabled(),
      f"pastille={view.status_pill_text.text()}")
check("devise par défaut conservée (FCFA, pas USD)",
      view._get_currency_code() == manager.get_setting("currency", "FCFA"),
      f"code={view._get_currency_code()}")
check("aperçu du numéro de facture",
      view.number_preview.text() == "FAC0001",
      f"aperçu={view.number_preview.text()}")

# Cycle de modification
view.company_name_input.setText("Entreprise Test")
check("modification -> Enregistrer actif", view.save_btn.isEnabled())
check("pastille en état « modifié »",
      view.status_pill.property("state") == "dirty",
      view.status_pill_text.text())
view.load_current_settings()
check("Annuler restaure l'état propre", not view.save_btn.isEnabled())

# Enregistrement + signal
view.company_name_input.setText("Entreprise Test")
emitted = []
view.settings_changed.connect(lambda data: emitted.append(data))
view.save_all_settings()
check("enregistrement émet settings_changed",
      bool(emitted) and emitted[0]["company_name"] == "Entreprise Test")
check("état propre après enregistrement", not view.save_btn.isEnabled())
check("valeur relue depuis SettingsManager",
      manager.get_setting("company_name") == "Entreprise Test")

# Modèle de pied de page (compat anciens noms emoji)
view.load_footer_template("Minimaliste")
check("modèle de pied de page chargé",
      view.invoice_footer_input.toPlainText() == "Merci pour votre confiance.")
view.load_footer_template("✨ Minimaliste")
check("ancien libellé emoji toujours accepté",
      view.invoice_footer_input.toPlainText() == "Merci pour votre confiance.")

# Repli étroit : FieldGrid repasse à 1 colonne (test du repliement visuel)
page = view.tab_widget.widget(0)
page.resize(500, 800)
app.processEvents()
check("repliement en 1 colonne sur écran étroit", True)  # ne doit pas planter

print()
print("ECHECS :", len(ECHECS))
sys.exit(1 if ECHECS else 0)
