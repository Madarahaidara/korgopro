"""Validation : onglet « Rôles & Permissions » responsive (offscreen).

Vérifie :
  * le contenu vit dans une QScrollArea (rien n'est rogné) ;
  * le nombre de colonnes s'adapte à la largeur de la fenêtre ;
  * « Réinitialiser » reconstruit réellement les cases (fin du gel) ;
  * aucun avertissement Qt « already has a layout ».

Script de validation temporaire — supprimer après vérification.
"""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QMessageBox, QScrollArea, QStackedWidget, QVBoxLayout,
    QWidget,
)

app = QApplication([])

qt_messages = []


def _handler(_mode, _ctx, message):
    qt_messages.append(message)


qInstallMessageHandler(_handler)

import ui.views.admin_view as admin_module


class _Result(dict):
    """Résultat neutre des gestionnaires simulés (toutes clés `success=False`)."""

    def __getattr__(self, name):
        return None


class _Dummy:
    """Gestionnaire simulé : toute méthode absente renvoie ``None``."""

    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        return lambda *a, **k: None


class _LogManagerDummy(_Dummy):
    """Journal système : résultats vides mais bien formés."""

    def get_logs(self, *a, **k):
        return {"success": False, "logs": [], "total": 0}

    def get_statistics(self, *a, **k):
        return {"success": False, "total_logs": 0, "today_logs": 0, "users_stats": {}}


class _SaleLogManagerDummy(_Dummy):
    """Journal des ventes : résultats vides mais bien formés."""

    def get_sale_logs(self, *a, **k):
        return {"success": False, "logs": [], "total": 0}


class _Signal:
    def connect(self, *a, **k):
        pass


class _NoWorker:
    """Thread d'information base de données neutralisé (aucun accès réseau)."""

    def __init__(self, *a, **k):
        self.finished = _Signal()
        self.failed = _Signal()

    def start(self):
        pass


class _Query:
    def order_by(self, *a, **k):
        return self

    def all(self):
        return []


class _Session:
    def query(self, *a, **k):
        return _Query()

    def close(self):
        pass


admin_module.LogManager = _LogManagerDummy
admin_module.DatabaseManager = _Dummy
admin_module.SaleLogManager = _SaleLogManagerDummy
admin_module.SettingsManager = _Dummy
admin_module.DbInfoWorker = _NoWorker
admin_module.SessionLocal = _Session

QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
QMessageBox.critical = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

from core.permissions import PERMISSIONS  # noqa: E402

view = admin_module.AdminView({"id": 1, "username": "test", "role": "ADMIN"})
view.show()
app.processEvents()

failures = 0


def check(label, condition):
    global failures
    if not condition:
        failures += 1
    print(f"[{'OK ' if condition else 'ECHEC'}] {label}")


roles_count = len(view.roles_dict)
expected_boxes = roles_count * len(PERMISSIONS)

check("contenu dans une zone défilante (QScrollArea#rolesTabContentScroll)",
      isinstance(view.roles_tab.findChild(QScrollArea, "rolesTabContentScroll"), QScrollArea))
check("la zone défilante est redimensionnable (pas de rognage)",
      view.roles_scroll.widgetResizable())
check("le contenu des autres onglets d'administration est aussi défilant",
      all(isinstance(tab.findChild(QScrollArea), QScrollArea)
          for tab in (view.users_tab, view.activity_tab, view.sale_logs_tab)))
check(f"{expected_boxes} cases à cocher créées ({roles_count} rôles x {len(PERMISSIONS)} permissions)",
      len(view.roles_tab.findChildren(QCheckBox)) == expected_boxes)
check("nombre de colonnes borné par le nombre de rôles",
      view._roles_columns <= roles_count)

# Largeur disponible -> nombre de colonnes. On active d'abord l'onglet (la
# largeur réelle du viewport n'existe qu'une fois l'onglet affiché) puis on
# laisse la boucle d'événements travailler : c'est le QTimer de
# _schedule_roles_adapt (chemin réel de l'application) qui recalcule.
def _columns_for(width):
    view.setGeometry(0, 0, width, 700)
    QTest.qWait(250)
    return view._roles_columns, view.roles_scroll.viewport().width()


view.setMinimumSize(0, 0)
view.tab_widget.setCurrentWidget(view.roles_tab)
QTest.qWait(250)

# Diagnostic : qui impose encore une largeur minimale ?
print("        minimums par onglet :")
for i in range(view.tab_widget.count()):
    page = view.tab_widget.widget(i)
    lay = page.layout()
    print(f"          {view.tab_widget.tabText(i):22s} min={page.minimumSizeHint().width()}px "
          f"layout_min={lay.minimumSize().width() if lay else None}px")
    if lay:
        for j in range(lay.count()):
            item = lay.itemAt(j)
            w = item.widget()
            policy = w.sizePolicy().horizontalPolicy() if w else "-"
            print(f"             item{j}: {type(w).__name__ if w else type(item).__name__} "
                  f"min={item.minimumSize().width()}px policy={policy}")

# La section ne doit plus imposer sa largeur à la fenêtre : sinon la fenêtre
# principale ne peut plus rétrécir (cause de la non-responsivité constatée).
min_tab_width = view.roles_tab.minimumSizeHint().width()
worst_tab = max(
    view.tab_widget.widget(i).minimumSizeHint().width()
    for i in range(view.tab_widget.count())
)
print(f"        largeur minimale imposée par l'onglet Rôles : {min_tab_width}px "
      f"(pire onglet : {worst_tab}px)")
check("l'onglet Rôles n'impose plus ~2000px (< 1000px)", min_tab_width < 1000)
check("aucun onglet d'administration n'impose ~2000px (< 1000px)", worst_tab < 1000)

column_px = max(
    view.ROLE_GROUP_MIN_WIDTH,
    max(g.minimumSizeHint().width() for g in view._role_groups),
)
print(f"        largeur mesurée d'une colonne : {column_px}px")

# Largeurs balayées en fonction de la largeur réelle d'une colonne.
wide_px = min(int(column_px * roles_count) + 200, 2600)
medium_px = int(column_px * 3) + 100
narrow_px = int(column_px) + 100
large, large_vp = _columns_for(wide_px)
medium, medium_vp = _columns_for(medium_px)
narrow, narrow_vp = _columns_for(narrow_px)
print(f"        colonnes -> {wide_px}px : {large} (viewport {large_vp}px) | "
      f"{medium_px}px : {medium} (viewport {medium_vp}px) | "
      f"{narrow_px}px : {narrow} (viewport {narrow_vp}px)")
check("toutes les colonnes sur écran large", large == roles_count)
check("repliement sur écran étroit", medium < large and narrow <= medium)
check("jamais moins d'une colonne", narrow >= 1)
check("aucun groupe perdu lors du repliement",
      view._roles_grid.count() == roles_count)

# Vérification géométrique : les groupes sont réellement répartis en
# lignes/colonnes (le compteur seul ne suffit pas).
_columns_for(wide_px)
rows_wide = len({g.y() for g in view._role_groups})
_columns_for(narrow_px)
rows_narrow = len({g.y() for g in view._role_groups})
print(f"        lignes distinctes : {rows_wide} en écran large, {rows_narrow} en écran étroit")
check("une seule ligne quand toutes les colonnes tiennent", rows_wide == 1)
check("autant de lignes que de rôles en une seule colonne",
      rows_narrow == roles_count)

# Intégration : l'AdminView dans un QStackedWidget, comme dans MainWindow.
shell = QWidget()
shell.resize(900, 650)
shell_layout = QVBoxLayout(shell)
stack = QStackedWidget(shell)
stack.addWidget(QWidget())  # une autre vue, comme les autres écrans
stack.addWidget(view)
shell_layout.addWidget(stack)
shell.show()
QTest.qWait(200)
stack.setCurrentWidget(view)
QTest.qWait(300)

stacked_width = view.tab_widget.width()
print(f"        dans un conteneur de 900px : AdminView={view.width()}px, "
      f"onglets={stacked_width}px, colonnes={view._roles_columns}")
check("l'Administration tient dans un conteneur de 900px (pas de débordement)",
      stacked_width <= 940)
check("les colonnes se replient dans un conteneur de 900px",
      view._roles_columns < roles_count)

# « Réinitialiser » doit reconstruire les cases depuis core.permissions.
box = view.roles_tab.findChild(QCheckBox, "perm_CAISSIER_manage_users")
box.setChecked(True)
check("modification prise en compte dans roles_dict",
      view.roles_dict["CAISSIER"]["permissions"]["manage_users"] is True)

view.reset_permissions_to_default()
app.processEvents()

new_box = view.roles_tab.findChild(QCheckBox, "perm_CAISSIER_manage_users")
check("cases reconstruites après « Réinitialiser »", new_box is not None)
check("valeur par défaut restaurée",
      new_box is not None and new_box.isChecked() is False)
check("aucun avertissement Qt « already has a layout »",
      not any("already has a layout" in m for m in qt_messages))

if qt_messages:
    print("        messages Qt :", qt_messages[:3])

print()
print("ECHECS :", failures)
sys.stdout.flush()
os._exit(1 if failures else 0)
