"""Validation Lot 1 : navigation par rôle (offscreen, sans accès réseau).

Les 8 vues sont remplacées par des QWidget vides : on teste la logique de
permissions (boutons visibles + vues réellement construites), pas les vues.

Script de validation temporaire — supprimer après vérification.
"""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

app = QApplication([])

refused = []


def _warning(_parent, _title, text, *args, **kwargs):
    refused.append(text)
    return QMessageBox.StandardButton.Ok


QMessageBox.warning = staticmethod(_warning)
QMessageBox.critical = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

import ui.views.main_window as main_window_module
from core.permissions import ENFORCED_PERMISSIONS
from ui.views.main_window import MENU_ENTRIES, MainWindow

class _FakeView(QWidget):
    """Faux écran acceptant n'importe quelle signature de constructeur."""

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.args = args
        self.kwargs = kwargs


# Vues factices : aucune requête base de données / réseau.
for _name in (
    "DashboardView", "SaleView", "InvoiceRegisterView",
    "EnhancedProformaInvoiceView", "StockView", "TreasuryView",
    "AdminView", "SettingsView",
):
    setattr(main_window_module, _name, _FakeView)

ROLE_CASES = [
    ("ADMIN", {"dashboard", "sale", "register", "proforma", "stock",
               "treasury", "admin", "settings"}),
    ("GESTIONNAIRE", {"dashboard", "sale", "register", "proforma", "stock",
                      "treasury"}),
    # Bug P0 : GERANT était proposé à la création mais absent de sale_view.ROLES.
    ("GERANT", {"dashboard", "sale", "register", "proforma", "stock",
                "treasury"}),
    # Bug P0 : incohérence de casse (menu insensible à la casse, vue non).
    ("Gestionnaire", {"dashboard", "sale", "register", "proforma", "stock",
                      "treasury"}),
    ("SUPERVISEUR", {"dashboard", "sale", "register", "proforma", "stock",
                     "treasury", "admin"}),
    ("ASSISTANT", {"dashboard", "sale", "register", "proforma"}),
    ("CAISSIER", {"dashboard", "sale", "register", "proforma", "treasury"}),
    # Bug P0 : rôle inconnu -> dashboard seul, sans verrouillage silencieux.
    ("STOCKIST", {"dashboard"}),
]

VIEW_ATTR = {
    "dashboard": "dashboard_view", "sale": "sale_view",
    "register": "register_view", "proforma": "proforma_view",
    "stock": "stock_view", "treasury": "treasury_view",
    "admin": "admin_view", "settings": "settings_view",
}

failures = 0
for role, expected in ROLE_CASES:
    refused.clear()
    window = MainWindow({"id": 1, "username": "test", "role": role}, "light")

    visible = {
        attr.replace("btn_", "")
        for attr, _permission, _view, _title in MENU_ENTRIES
        if getattr(window, attr).isVisibleTo(window)
    }
    built = set(window.views)
    expected_views = {VIEW_ATTR[name] for name in expected}

    window._check_and_switch_to_settings()
    page = window.page_title.text()
    expected_page = "Paramètres" if "settings" in expected else "Dashboard"

    ok = visible == expected and built == expected_views and page == expected_page
    failures += 0 if ok else 1
    print(
        f"[{'OK ' if ok else 'ECHEC'}] {role:14s} "
        f"boutons={sorted(visible)}\n"
        f"{'':20s} vues={sorted(built)}\n"
        f"{'':20s} clic_Parametres -> {page!r} (refus={bool(refused)})"
    )
    window.close()

# Chaque permission pilotant le menu est déclarée comme réellement contrôlée.
menu_permissions = {permission for _a, permission, _v, _t in MENU_ENTRIES}
assert menu_permissions <= ENFORCED_PERMISSIONS, menu_permissions - ENFORCED_PERMISSIONS

print()
print("ECHECS :", failures)
sys.stdout.flush()
os._exit(1 if failures else 0)
