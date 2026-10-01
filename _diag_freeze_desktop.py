# -*- coding: utf-8 -*-
"""Diagnostic du gel d'ecran du desktop : requetes SQL sur le thread Qt.

OBJECTIF
--------
Le poste desktop parle DIRECTEMENT a PostgreSQL (Supabase, pooler eu-west-1)
via SQLAlchemy. Toutes les requetes executees dans le thread de l'interface
bloquent Qt : l'ecran ne se repeint plus et les clics sont ignores.

Ce script MESURE, sans toucher a la production :
  * le nombre de requetes SQL declenchees par la construction de chaque vue
    (orchestree par MainWindow._build_ui, donc sur le thread UI) ;
  * leur duree cumulee, en base SQLite jetable (cout local ~ 0) ;
  * l'effet d'une latence reseau `--rtt-ms` (aller-retour vers Supabase) pour
    estimer le gel reel : `requetes x RTT`.

USAGE
-----
    python _diag_freeze_desktop.py                 # mesures locales
    python _diag_freeze_desktop.py --rtt-ms 120    # simulation reseau
    python _diag_freeze_desktop.py --only stock    # un seul ecran

Aucune ecriture n'est faite en production : la base de travail est un fichier
SQLite temporaire cree par le script (DATABASE_URL forcee avant tout import).
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time

# --- Base jetable AVANT tout import de core.database -----------------------
_DB_FILE = os.path.join(tempfile.gettempdir(), "_diag_freeze_korgo.db")
if os.path.exists(_DB_FILE):
    os.remove(_DB_FILE)
os.environ["DATABASE_URL"] = "sqlite:///" + _DB_FILE.replace("\\", "/")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import event  # noqa: E402

from core.database import Base, engine  # noqa: E402
import core.models.activity_log  # noqa: E402,F401
import core.models.customer  # noqa: E402,F401
import core.models.sale_log  # noqa: E402,F401
import core.models.store  # noqa: E402,F401
import core.models.stock_models  # noqa: E402,F401
import core.models.sale_models  # noqa: E402,F401
import core.models.treasury_models  # noqa: E402,F401

Base.metadata.create_all(bind=engine)

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

# --- Compteur de requetes + latence simulee --------------------------------
STATS = {"count": 0, "sql_ms": 0.0, "rtt_ms": 0.0}


@event.listens_for(engine, "before_cursor_execute")
def _before(conn, cursor, statement, parameters, context, executemany):
    STATS["_t0"] = time.perf_counter()
    if STATS["rtt_ms"]:
        time.sleep(STATS["rtt_ms"] / 1000.0)


@event.listens_for(engine, "after_cursor_execute")
def _after(conn, cursor, statement, parameters, context, executemany):
    STATS["count"] += 1
    STATS["sql_ms"] += (time.perf_counter() - STATS["_t0"]) * 1000.0


def measure(label: str, factory):
    """Execute `factory` en comptant les requetes SQL et la duree du thread UI."""
    STATS.update(count=0, sql_ms=0.0)
    t0 = time.perf_counter()
    obj, error = None, ""
    try:
        obj = factory()
    except Exception as exc:  # noqa: BLE001 - un diagnostic ne doit pas planter
        error = f"{type(exc).__name__}: {exc}"
    wall = (time.perf_counter() - t0) * 1000.0
    print(
        f"{label:26s} {STATS['count']:4d} req.  {STATS['sql_ms']:9.1f} ms SQL"
        f"  {wall:9.1f} ms UI   {error}",
        flush=True,
    )
    return obj


USER = {"id": 1, "username": "diag", "role": "ADMIN"}


def build_views():
    """Fabriques des ecrans, dans l'ordre ou MainWindow les construit."""
    from ui.views.dashboard_view import DashboardView
    from ui.views.sale_view import SaleView
    from ui.views.invoice_register_view import InvoiceRegisterView
    from ui.views.stock_view import StockView
    from ui.views.treasury_view import TreasuryView
    from ui.views.admin_view import AdminView
    from ui.views.settings_view import SettingsView
    from ui.views.proforma_invoice_view import EnhancedProformaInvoiceView
    from utils.settings_manager import SettingsManager

    return {
        "settings_manager": lambda: SettingsManager(),
        "dashboard": lambda: DashboardView(USER),
        "sale": lambda: SaleView(USER),
        "register": lambda: InvoiceRegisterView(USER),
        "proforma": lambda: EnhancedProformaInvoiceView(current_user_id=1),
        "stock": lambda: StockView(USER),
        "treasury": lambda: TreasuryView(USER),
        "admin": lambda: AdminView(USER),
        "settings": lambda: SettingsView(USER, SettingsManager()),
    }


def measure_startup():
    """Mesure le travail fait par main.py avant l'affichage du splash."""
    from core.database import SessionLocal
    from core.store_manager import ensure_default_store

    # 2e create_all = chemin reel (tables deja presentes) : 1 inspection par table.
    measure("Base.metadata.create_all", lambda: Base.metadata.create_all(bind=engine))

    def _default_store():
        with SessionLocal() as session:
            ensure_default_store(session)

    measure("ensure_default_store", _default_store)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rtt-ms", type=float, default=0.0,
                        help="latence simulee par requete (ms), ex. 120")
    parser.add_argument("--only", default="",
                        help="ne mesurer qu'un ecran (dashboard, sale, stock...)")
    parser.add_argument("--refresh", type=int, default=0, metavar="N",
                        help="mesurer N rafraichissements du tableau de bord "
                             "(timer 30 s)")
    args = parser.parse_args()
    STATS["rtt_ms"] = args.rtt_ms

    print(f"Base de travail : {engine.url}")
    print(f"Latence simulee : {args.rtt_ms:.0f} ms par requete\n")

    measure_startup()
    print()

    factories = build_views()
    if args.only:
        factories = {k: v for k, v in factories.items() if k == args.only}
        if not factories:
            print(f"Ecran inconnu : {args.only}")
            return 2

    total = {"count": 0, "ui_ms": 0.0}
    # Les vues lancent des QThread (workers) : on garde une référence, sinon le
    # GC détruit un QThread en cours et Qt termine le processus.
    keep = []
    for key, factory in factories.items():
        t0 = time.perf_counter()
        keep.append(measure(key, factory))
        total["count"] += STATS["count"]
        total["ui_ms"] += (time.perf_counter() - t0) * 1000.0

    print("-" * 72)
    print(f"TOTAL ecrans : {total['count']} requetes, {total['ui_ms']:.0f} ms "
          "de thread UI gele (avant MainWindow)")

    if not args.only:
        from ui.views.main_window import MainWindow

        keep.append(measure("MainWindow (login)", lambda: MainWindow(USER, None)))

    if args.refresh:
        from ui.views.dashboard_view import DashboardView

        view = DashboardView(USER)
        keep.append(view)
        for i in range(1, args.refresh + 1):
            measure(f"refresh_data #{i} (timer 30 s)", view.refresh_data)

    if args.rtt_ms:
        print("\nEstimation reseau : chaque requete ci-dessus coute "
              f"~{args.rtt_ms:.0f} ms d'aller-retour vers Supabase.")

    # Les vues lancent des QThread d'arriere-plan : sortie immediate.
    os._exit(0)


if __name__ == "__main__":
    sys.exit(main())
