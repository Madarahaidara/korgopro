# -*- coding: utf-8 -*-
"""Test de bout en bout du multi-magasins (base SQLite temporaire).

Usage: python _test_multi_store.py
Le script crée sa propre base jetable et ne touche ni korgo_pro.db ni
company_settings.json (les paramètres sont simulés).
"""
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_test_multi_store.db")
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
os.environ["DATABASE_URL"] = "sqlite:///" + DB_PATH.replace("\\", "/")

from core.database import Base, engine, SessionLocal  # noqa: E402
import core.models.store  # noqa: E402,F401
import core.models.stock_models  # noqa: E402,F401
import core.models.sale_models  # noqa: E402,F401
import core.models.treasury_models  # noqa: E402,F401
from core.models.stock_models import Product, InventoryMovement  # noqa: E402
from core.models.sale_models import Sale  # noqa: E402
from core.models.user import User  # noqa: E402
import core.store_manager as sm  # noqa: E402

FAILURES = []


class _FakeSettings:
    """Remplace SettingsManager (évite d'écrire company_settings.json)."""

    def __init__(self):
        self._data = {}

    def get_setting(self, key, default=None):
        return self._data.get(key, default)

    def set_setting(self, key, value, emit=False):
        self._data[key] = value
        return True


sm._settings_cache = _FakeSettings()
Base.metadata.create_all(bind=engine)


def check(label, condition, extra=""):
    status = "OK " if condition else "ECHEC"
    print(f"[{status}] {label} {extra}")
    if not condition:
        FAILURES.append(label)


def scoped_products(session):
    """Produits visibles dans le magasin actif (même logique que l'UI)."""
    query = sm.apply_store_scope(session.query(Product), session, Product.store_id)
    return query.all()


def main():
    session = SessionLocal()

    # --- Données historiques (sans magasin) --------------------------------
    user = User(username="caissier_test", password_hash="x",
                email="caissier_test@korgo.local", role="CAISSIER", active=True)
    session.add(user)
    session.flush()

    for index in range(3):
        session.add(Product(
            code=f"HIST-{index}", name=f"Produit historique {index}",
            category="Test", quantity=10, purchase_price=1000, sale_price=1500,
        ))
    session.flush()

    session.add(Sale(sale_number="S-OLD-1", cashier_id=user.id, subtotal=1500,
                     total_amount=1500, amount_paid=1500))
    session.commit()

    product = session.query(Product).first()
    session.add(InventoryMovement(product_id=product.id, movement_type="IN", quantity=10))
    session.commit()

    # --- 1. Magasin par défaut + rattachement ------------------------------
    store = sm.ensure_default_store(session)
    check("magasin par défaut créé", store.name == sm.DEFAULT_STORE_NAME, f"= {store.code}")
    check("magasin par défaut marqué is_default", store.is_default is True)
    orphan_products = session.query(Product).filter(Product.store_id.is_(None)).count()
    check("produits historiques rattachés", orphan_products == 0, f"({orphan_products} restants)")
    orphan_sales = session.query(Sale).filter(Sale.store_id.is_(None)).count()
    check("ventes historiques rattachées", orphan_sales == 0)
    orphan_moves = session.query(InventoryMovement).filter(
        InventoryMovement.store_id.is_(None)
    ).count()
    check("mouvements historiques rattachés", orphan_moves == 0)

    store_again = sm.ensure_default_store(session)
    check("ensure_default_store idempotent", store_again.id == store.id)
    check("un seul magasin après double appel", session.query(sm._models()[0]).count() == 1)

    # Règles métier : le magasin unique ne peut être ni supprimé ni désactivé
    early_manager = sm.StoreManager(session)
    try:
        early_manager.delete_store(store.id)
        check("dernier magasin protégé", False, "(aucune erreur levée)")
    except ValueError as exc:
        check("dernier magasin protégé", "dernier magasin" in str(exc), str(exc))
    try:
        early_manager.toggle_active(store.id)
        check("dernier magasin actif protégé", False, "(aucune erreur levée)")
    except ValueError as exc:
        check("dernier magasin actif protégé", "dernier magasin actif" in str(exc), str(exc))

    # --- 2. Magasin actif ---------------------------------------------------
    check("magasin actif = par défaut", sm.get_active_store_id(session) == store.id)

    manager = sm.StoreManager(session)
    cotonou = manager.create_store(name="Magasin Cotonou", address="Cotonou",
                                   phone="+229 97 00 00 00", manager_name="Alice")
    check("code auto MAG-0002", cotonou.code == "MAG-0002", f"= {cotonou.code}")
    check("nouveau magasin non par défaut", cotonou.is_default is False)

    sm.set_active_store_id(cotonou.id, session)
    check("changement de magasin actif", sm.get_active_store_id(session) == cotonou.id)

    # --- 3. Cloisonnement des données --------------------------------------
    check("catalogue Cotonou vide", len(scoped_products(session)) == 0)
    session.add(Product(code="COT-1", name="Produit Cotonou", category="Test",
                        quantity=5, purchase_price=1000, sale_price=1200,
                        store_id=cotonou.id))
    session.commit()
    check("produit Cotonou visible", len(scoped_products(session)) == 1)

    sm.set_active_store_id(store.id, session)
    names = [p.code for p in scoped_products(session)]
    check("produit Cotonou masqué du magasin principal", "COT-1" not in names, f"({names})")
    check("produits historiques visibles", len(names) == 3)

    run_business_rules(manager, session, store, cotonou)

    session.close()
    print()
    if FAILURES:
        print(f" {len(FAILURES)} test(s) en échec : {FAILURES}")
        return 1
    print("✅ Tous les tests multi-magasins sont passés.")
    return 0


def run_business_rules(manager, session, store, cotonou):
    """Règles métier : suppression, désactivation, unicité, résumé."""
    try:
        manager.delete_store(cotonou.id)
        check("suppression refusée si produits", False, "(aucune erreur levée)")
    except ValueError as exc:
        check("suppression refusée si produits", "contient encore des données" in str(exc))

    manager.create_store(name="Magasin Vide")
    empty_store = [s for s in manager.list_stores() if s.name == "Magasin Vide"][0]
    try:
        manager.delete_store(empty_store.id)
        check("suppression magasin vide autorisée", True)
    except ValueError as exc:
        check("suppression magasin vide autorisée", False, str(exc))

    try:
        manager.delete_store(store.id)
        check("suppression refusée (magasin non vide)", False, "(aucune erreur levée)")
    except ValueError as exc:
        check("suppression refusée (magasin non vide)", "contient encore des données" in str(exc))

    manager.create_store(name="Magasin Porto-Novo")
    porto = [s for s in manager.list_stores() if s.name == "Magasin Porto-Novo"][0]
    check("désactivation possible avec 2 actifs", manager.toggle_active(porto.id) is False)
    try:
        sm.set_active_store_id(porto.id, session)
        check("magasin désactivé non sélectionnable", False, "(aucune erreur levée)")
    except ValueError:
        check("magasin désactivé non sélectionnable", True)

    manager.update_store(cotonou.id, name="Magasin Cotonou Centre", phone="")
    check("mise à jour du nom", manager.get_store(cotonou.id).name == "Magasin Cotonou Centre")
    try:
        manager.update_store(store.id, name="")
        check("nom obligatoire", False, "(aucune erreur levée)")
    except ValueError:
        check("nom obligatoire", True)
    try:
        manager.create_store(name=cotonou.name)
        check("nom unique", False, "(aucune erreur levée)")
    except ValueError:
        check("nom unique", True)

    summary = manager.store_summary(cotonou.id)
    check("résumé magasin (1 produit)", summary["products"] == 1, str(summary))
    check("valeur du stock cohérente", summary["stock_value"] == 5 * 1000,
          str(summary["stock_value"]))

    manager.set_default_store(cotonou.id)
    defaults = [s for s in manager.list_stores() if s.is_default]
    check("un seul magasin par défaut", len(defaults) == 1 and defaults[0].id == cotonou.id)


if __name__ == "__main__":
    import sys
    sys.exit(main())