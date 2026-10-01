# -*- coding: utf-8 -*-
"""Temporisation fine de DashboardView.refresh_data (voie overlay vs libellé)."""
from __future__ import annotations

import os
import sys
import tempfile
import time

_DB_FILE = os.path.join(tempfile.gettempdir(), "_diag_refresh_korgo.db")
if os.path.exists(_DB_FILE):
    os.remove(_DB_FILE)
os.environ["DATABASE_URL"] = "sqlite:///" + _DB_FILE.replace("\\", "/")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication  # noqa: E402
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
app = QApplication.instance() or QApplication([])
USER = {"id": 1, "username": "diag", "role": "ADMIN"}

RTT_MS = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0
if RTT_MS:
    _t = {"t0": 0.0}

    @event.listens_for(engine, "before_cursor_execute")
    def _b(conn, cursor, statement, parameters, context, executemany):
        _t["t0"] = time.perf_counter()
        time.sleep(RTT_MS / 1000.0)

    @event.listens_for(engine, "after_cursor_execute")
    def _a(conn, cursor, statement, parameters, context, executemany):
        pass


def pump(seconds=0.0):
    t0 = time.time()
    while time.time() - t0 < seconds:
        app.processEvents()
        time.sleep(0.01)


def timed(label, fn):
    t0 = time.perf_counter()
    fn()
    print(f"{label:52s} {(time.perf_counter() - t0) * 1000:8.1f} ms")


print(f"latence simulee : {RTT_MS:.0f} ms/req")
from ui.views.dashboard_view import DashboardView  # noqa: E402

view = DashboardView(USER)
worker1 = view._data_worker
pump(0.3)
print(f"worker1 en cours : {worker1.isRunning() if worker1 else None}"
      f" | _data_loaded={view._data_loaded}"
      f" | overlay depth={view._overlay.depth}")

# 1) Voie reelle du timer 30 s
timed("refresh #1 (worker initial etat inconnu)", view.refresh_data)
print(f"   apres #1 : worker en cours="
      f"{view._data_worker.isRunning() if view._data_worker else None}"
      f" _data_loaded={view._data_loaded}")

# 2) Attendre la livraison du payload, puis rafraichir (voie libelle)
t0 = time.time()
while not view._data_loaded and time.time() - t0 < 15:
    app.processEvents()
    time.sleep(0.01)
print(f"payload livre : _data_loaded={view._data_loaded}")
pump(0.3)
timed("refresh #2 (charge, voie libelle)", view.refresh_data)
timed("refresh #3 (charge, voie libelle)", view.refresh_data)

# 3) Decomposer refresh_data pour isoler le cout
from PySide6.QtCore import QDate  # noqa: E402

timed("  date_label.setText", lambda: view.date_label.setText(
    QDate.currentDate().toString("dddd d MMMM yyyy")))
timed("  overlay.start() puis stop() immediat",
      lambda: (view._overlay.start(), view._overlay.stop()))
pump(0.4)
print(f"fin : overlay visible={view._overlay.isVisible()}"
      f" depth={view._overlay.depth}")
os._exit(0)
