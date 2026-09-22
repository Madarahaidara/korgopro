import io, os, sys, time, contextlib
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, ".")
from PySide6.QtWidgets import QApplication, QMessageBox
app = QApplication([])
QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
QMessageBox.critical = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
from ui.views.main_window import MENU_ENTRIES, MainWindow
buf = io.StringIO()
for role in ["ADMIN", "CAISSIER"]:
    t = time.time()
    with contextlib.redirect_stdout(buf):
        w = MainWindow({"id": 1, "username": "t", "role": role}, "light")
    visible = [a for a, p, v, ti in MENU_ENTRIES if getattr(w, a).isVisibleTo(w)]
    with contextlib.redirect_stdout(buf):
        w._check_and_switch_to_settings()
    page = w.page_title.text()
    w.close(); w.deleteLater(); app.processEvents()
    print(f"{role:10s} {time.time()-t:5.1f}s visible={visible} page_apres_settings={page!r}", flush=True)
