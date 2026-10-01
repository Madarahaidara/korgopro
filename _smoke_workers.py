# -*- coding: utf-8 -*-
"""Smoke test des chemins asynchrones P0 (hors production, base SQLite jetable).

Construit les vues corrigées, déclenche leurs rechargements (debounce +
workers) et attend la livraison des signaux. Vérifie que :
  * les slots de rendu sont appelés avec un payload ;
  * aucun worker ne tourne encore à la fin du délai ;
  * SaleView : deux chargements rapides ne bloquent pas et la génération
    écarte le résultat périmé ;
  * les LoadingOverlay (P0.5) s'apparent correctement : anti-scintillement
    de 150 ms, empilement profond, voile vendu (depth 0) après payload.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time

_DB_FILE = os.path.join(tempfile.gettempdir(), "_smoke_korgo.db")
if os.path.exists(_DB_FILE):
    os.remove(_DB_FILE)
os.environ["DATABASE_URL"] = "sqlite:///" + _DB_FILE.replace("\\", "/")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

# Aucune boîte modale dans le test : elles bloqueraient la boucle d'événements.
QMessageBox.warning = staticmethod(lambda *a, **k: print("  [box.w]", a[-1]))
QMessageBox.critical = staticmethod(lambda *a, **k: print("  [box.c]", a[-1]))
QMessageBox.information = staticmethod(lambda *a, **k: print("  [box.i]", a[-1]))

from core.database import Base, engine  # noqa: E402
import core.models.activity_log  # noqa: E402,F401
import core.models.customer  # noqa: E402,F401
import core.models.sale_log  # noqa: E402,F401
import core.models.store  # noqa: E402,F401
import core.models.stock_models  # noqa: E402,F401
import core.models.sale_models  # noqa: E402,F401
import core.models.treasury_models  # noqa: E402,F401

Base.metadata.create_all(bind=engine)

app = QApplication.instance() or QApplication([])
USER = {"id": 1, "username": "smoke", "role": "ADMIN"}

FAILURES: list[str] = []


def check(cond, label):
    print(f"{'OK ' if cond else 'ECHEC'} {label}")
    if not cond:
        FAILURES.append(label)


def wait_until(cond, timeout=20.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


def wait_idle(workers, timeout=20.0):
    """Attend la fin de tous les workers (None ignoré), puis vide la file."""
    ok = wait_until(
        lambda: all(w is None or not w.isRunning() for w in workers),
        timeout=timeout)
    if not ok:
        return False
    # Signaux émis par le worker encore en file d'attente (queued) :
    for _ in range(10):
        app.processEvents()
        time.sleep(0.01)
    return True


# --- LoadingOverlay (voile anti-gel) ----------------------------------------
print("\n== LoadingOverlay ==")
from PySide6.QtWidgets import QWidget  # noqa: E402
from ui.loading import LoadingOverlay  # noqa: E402

host = QWidget()
host.resize(300, 200)
host.show()
ov = LoadingOverlay(host, "Test latence…")
check(not ov.isVisible(), "overlay : masqué tant qu'aucune attente")

ov.start()
time.sleep(0.05)                           # < SHOW_DELAY_MS
app.processEvents()
check(not ov.isVisible(), "overlay : anti-scintillement (< 150 ms)")
check(wait_until(lambda: ov.isVisible(), timeout=2.0),
      "overlay : affiché après le délai anti-scintillement")

ov.start()                                 # 2e chargement superposé
ov.stop()
check(ov.depth == 1 and ov.isVisible(),
      "overlay : reste affiché tant qu'un chargement subsiste")
ov.stop()
check(ov.depth == 0 and not ov.isVisible(),
      "overlay : masqué au dernier stop()")

ov.start()                                 # réponse rapide : jamais d'affichage
ov.stop()
time.sleep(LoadingOverlay.SHOW_DELAY_MS / 1000 + 0.2)
app.processEvents()
check(not ov.isVisible(),
      "overlay : réponse rapide n'affiche jamais le voile")

# --- Dashboard --------------------------------------------------------------
print("\n== DashboardView ==")
from ui.views.dashboard_view import DashboardView  # noqa: E402

dash = DashboardView(USER)
check(wait_idle([getattr(dash, "_data_worker", None)]),
      "dashboard : worker initial terminé")
dash_hits = []
dash_orig = dash._apply_data
dash._apply_data = lambda d: (dash_hits.append(d), dash_orig(d))
dash.refresh_data()  # slot du timer 30 s
check(wait_idle([getattr(dash, "_data_worker", None)]),
      "dashboard : worker du refresh terminé")
check(len(dash_hits) == 1 and "total_today" in dash_hits[0],
      "dashboard : _apply_data appelé avec payload")
check(dash._overlay.depth == 0, "dashboard : voile soldé après payload")

# --- Registre factures ------------------------------------------------------
print("\n== InvoiceRegisterView ==")
from ui.views.invoice_register_view import InvoiceRegisterView  # noqa: E402

reg = InvoiceRegisterView(USER)
reg_hits = []
reg_orig = reg._populate
reg._populate = lambda p: (reg_hits.append(p), reg_orig(p))
reg.txt_search.setText("SMOKE")          # frappe → debounce
reg.txt_search.setText("SMOKE2")
check(wait_until(lambda: reg._worker is not None, timeout=5.0),
      "registre : worker lancé après debounce")
check(wait_idle([reg._worker], timeout=10.0),
      "registre : worker terminé")
check(len(reg_hits) >= 1 and "rows" in reg_hits[-1],
      "registre : _populate appelé (0 requête par frappe)")
check(wait_until(lambda: reg._overlay.depth == 0, timeout=5.0),
      "registre : voile soldé après livraison")

# --- Proforma ---------------------------------------------------------------
print("\n== EnhancedProformaInvoiceView ==")
from ui.views.proforma_invoice_view import EnhancedProformaInvoiceView  # noqa: E402

pro = EnhancedProformaInvoiceView(current_user_id=1)
pro_hits = []
pro_orig = pro._apply_proformas
pro._apply_proformas = lambda p: (pro_hits.append(p), pro_orig(p))
pro.search_input.setText("SMOKE")        # frappe → debounce
check(wait_until(lambda: pro._proforma_worker is not None, timeout=5.0),
      "proforma : worker lancé après debounce")
check(wait_idle([pro._proforma_worker], timeout=10.0),
      "proforma : worker terminé")
check(len(pro_hits) >= 1 and "rows" in pro_hits[-1],
      "proforma : _apply_proformas appelé (0 requête par frappe)")
check(wait_until(lambda: pro._overlay.depth == 0, timeout=5.0),
      "proforma : voile soldé après livraison")

# --- Admin ------------------------------------------------------------------
print("\n== AdminView ==")
from ui.views.admin_view import AdminView  # noqa: E402

adm = AdminView(USER)
adm_a_hits, adm_s_hits = [], []
adm_a_orig, adm_s_orig = adm._render_activities, adm._render_sale_logs
adm._render_activities = lambda p: (adm_a_hits.append(p), adm_a_orig(p))
adm._render_sale_logs = lambda p: (adm_s_hits.append(p), adm_s_orig(p))
adm.load_real_activities()               # bouton Filtrer
adm.load_real_activities()               # 2e clic pendant exécution
adm.load_sale_logs()
check(wait_idle([adm._activities_worker, adm._sale_logs_worker],
                timeout=10.0), "admin : workers terminés")
check(len(adm_a_hits) >= 1, "admin : _render_activities appelé")
check(len(adm_s_hits) >= 1, "admin : _render_sale_logs appelé")
check(wait_until(lambda: adm._activities_overlay.depth == 0
                 and adm._sale_logs_overlay.depth == 0, timeout=10.0),
      "admin : voiles soldés (y compris recharges en attente)")

# --- SaleView (P0.4 : génération) ------------------------------------------
print("\n== SaleView (P0.4) ==")
from ui.views.sale_view import SaleView  # noqa: E402

sale = SaleView(USER)
gen0 = sale._load_generation
sale.load_products_async()
sale.load_products_async()               # résultats périmés écartés
check(sale._load_generation == gen0 + 2, "sale : génération incrémentée")
check(wait_idle(list(sale._loader_refs) + [sale.loader_thread], timeout=15.0),
      "sale : threads terminés (aucun wait() bloquant)")
# La livraison des signaux (queued) peut précéder la fin de la boucle :
# on attend la libération des références et la réactivation de la table.
check(wait_until(lambda: not sale._loader_refs
                 and sale.products_table.isEnabled(), timeout=5.0),
      "sale : table réactivée + références libérées")
check(wait_until(lambda: sale._products_overlay.depth == 0, timeout=5.0),
      "sale : voile soldé (y compris résultat périmé écarté)")

print("\n" + ("=" * 40))
if FAILURES:
    print(f"ECHECS ({len(FAILURES)}) :")
    for f in FAILURES:
        print(" -", f)
    os._exit(1)
print("TOUS LES TESTS PASSEN")
os._exit(0)
