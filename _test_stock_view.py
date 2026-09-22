  # -*- coding: utf-8 -*-
"""Test d'integration UI (headless) : StockView avec plusieurs magasins."""
import faulthandler
import os
import sys
import tempfile

faulthandler.dump_traceback_later(120, exit=True)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from PySide6.QtWidgets import QApplication

from core.database import Base
from core.store_manager import (
    StoreManager,
    ensure_default_store,
    get_active_store_id,
)


def main():
    app = QApplication.instance() or QApplication([])

    tmp = tempfile.mktemp(suffix=".db")
    engine = create_engine(f"sqlite:///{tmp}")
    # enregistre TOUS les modeles dans Base.metadata (comme au demarrage de l'app)
    import importlib
    import pkgutil
    import core.models as _cm

    for _m in pkgutil.iter_modules(_cm.__path__):
        importlib.import_module(f"core.models.{_m.name}")

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)

    # Patch le SessionLocal de la vue AVANT construction pour utiliser la base temporaire
    import ui.views.stock_view as sv

    sv.SessionLocal = Session

    session = Session()
    ensure_default_store(session)

    from ui.views.stock_view import StockView

    view = StockView(user={"id": 1, "username": "admin", "role": "admin"})
    view.db_session = session

    ok = 0
    fail = []

    def check(name, cond):
        nonlocal ok
        if cond:
            ok += 1
            print(f"  [OK] {name}")
        else:
            fail.append(name)
            print(f"  [ECHEC] {name}")

    # --- 1. Boutique par defaut dans le combo
    view.load_stores_combo()
    check("combo contient au moins 1 magasin", view.store_combo.count() >= 1)
    check(
        "magasin actif selectionne",
        view.store_combo.currentData() == get_active_store_id(session),
    )

    # --- 2. Creation d'un 2e magasin via StoreManager
    mgr = StoreManager(session)
    s2 = mgr.create_store(
        name="Magasin Secondaire", address="Douala", phone="690000000"
    )
    check("creation 2e magasin", s2 is not None and s2.id is not None)
    view.load_stores_combo()
    check("combo contient 2 magasins", view.store_combo.count() == 2)

    # --- 3. Changement de magasin actif via on_store_changed
    idx = view.store_combo.findData(s2.id)
    view.store_combo.setCurrentIndex(idx)
    view.on_store_changed(idx)
    check(
        "changement magasin met a jour l'actif",
        get_active_store_id(session) == s2.id,
    )

    # --- 4. Produit isole par magasin : cree dans s2, invisible dans s1
    from core.models.stock_models import Product

    p = Product(code="REF-S2", name="Produit S2", category="Test",
                purchase_price=100, sale_price=150, quantity=5,
                min_stock=5, max_stock=100, store_id=s2.id)
    session.add(p)
    session.commit()
    view.load_data()
    from core.store_manager import scope_products_query

    q = scope_products_query(session.query(Product), session)
    check("produit s2 visible sous s2", q.filter(Product.code == "REF-S2").count() == 1)

    view.load_stores_combo()
    idx1 = view.store_combo.findData(s2.id)  # retour au defaut
    default_id = mgr.default_store_id()
    idx_def = view.store_combo.findData(default_id)
    view.store_combo.setCurrentIndex(idx_def)
    view.on_store_changed(idx_def)
    check("retour au magasin par defaut", get_active_store_id(session) == default_id)

    # --- 5. Manager : liste / resume
    stores = mgr.list_stores()
    check("list_stores >= 2", len(stores) >= 2)
    summary = mgr.store_summary(s2.id)
    check("store_summary produit=1", summary.get("products", 0) >= 1)

    # --- 6. toggle / suppression protegee
    mgr.toggle_active(s2.id)
    check("toggle active", not mgr.get_store(s2.id).active)
    mgr.toggle_active(s2.id)
    try:
        mgr.delete_store(s2.id)
        check("suppression refusee si donnees", False)
    except ValueError:
        check("suppression refusee si donnees", True)
    except Exception as e:
        check(f"suppression refusee si donnees ({type(e).__name__})", isinstance(e, ValueError))
    session.delete(p)
    session.commit()
    try:
        mgr.delete_store(s2.id)
        check("suppression magasin vide", True)
    except Exception as e:
        check(f"suppression magasin vide ({e})", False)

    session.close()
    engine.dispose()
    try:
        os.remove(tmp)
    except OSError:
        pass

    print(f"\n{ok} tests passes, {len(fail)} echecs")
    if fail:
        print("Echecs:", fail)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
