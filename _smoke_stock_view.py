"""Sonde : la construction de StockView se termine-t-elle ? (offscreen)"""
import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

app = QApplication([])

print("import stock_view...", flush=True)
from ui.views.stock_view import StockView

print("construction StockView(ADMIN)...", flush=True)
view = StockView({"id": 1, "username": "test", "role": "ADMIN"})
print("StockView construite", flush=True)
print("_can_manage_stores =", view._can_manage_stores(), flush=True)

for role in ["GERANT", "SUPERVISEUR", "CAISSIER"]:
    print(f"construction StockView({role})...", flush=True)
    view = StockView({"id": 1, "username": "test", "role": role})
    print(f"StockView({role}) construite, stores = {view._can_manage_stores()}",
          flush=True)
