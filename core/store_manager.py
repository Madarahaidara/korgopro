# core/store_manager.py
# ---------------------------------------------------------------------------
# Gestion multi-magasins (version desktop).
#
# Rôle du module :
#   - garantir l'existence d'un magasin « par défaut » et rattacher les données
#     historiques (produits / mouvements / ventes dont store_id est NULL) ;
#   - mémoriser le magasin actif (setting « active_store_id » du
#     SettingsManager, donc persisté dans company_settings.json) ;
#   - fournir les opérations CRUD utilisées par l'écran de gestion des
#     magasins (création, modification, activation, suppression) ;
#   - exposer `store_scope()` pour filtrer les requêtes SQLAlchemy sur le
#     magasin actif.
#
# Les règles métier sont alignées sur la version web :
#   * un magasin ne peut pas être supprimé s'il contient des produits, des
#     mouvements ou des ventes ;
#   * le dernier magasin (ou le dernier magasin actif) ne peut pas être
#     supprimé / désactivé.
# ---------------------------------------------------------------------------
import re
from contextlib import contextmanager
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import or_

from core.database import SessionLocal

if TYPE_CHECKING:  # Annotation seule : évite tout cycle d'import à l'exécution.
    from core.models.store import Store

DEFAULT_STORE_NAME = "Magasin principal"
DEFAULT_STORE_CODE = "MAG-0001"
ACTIVE_STORE_SETTING_KEY = "active_store_id"

_SETTINGS_UNSET = object()
_settings_cache = _SETTINGS_UNSET


# ---------------------------------------------------------------------------
# Utilitaires internes
# ---------------------------------------------------------------------------
def _settings_manager():
    """Instance partagée de SettingsManager, ou None si indisponible.

    L'import est différé pour que ce module reste utilisable en ligne de
    commande (scripts de migration) même sans PySide6 installé.
    """
    global _settings_cache
    if _settings_cache is _SETTINGS_UNSET:
        try:
            from utils.settings_manager import SettingsManager
            _settings_cache = SettingsManager()
        except Exception:  # pragma: no cover - dépendance Qt absente
            _settings_cache = None
    return _settings_cache


@contextmanager
def _session_scope(session=None):
    """Fournit une session : celle passée, sinon une session temporaire."""
    own = session is None
    if own:
        session = SessionLocal()
    try:
        yield session
    finally:
        if own:
            session.close()


def _models():
    """Import différé des modèles (évite les cycles d'import)."""
    from core.models.store import Store
    from core.models.stock_models import Product, InventoryMovement
    from core.models.sale_models import Sale
    return Store, Product, InventoryMovement, Sale


# ---------------------------------------------------------------------------
# Magasin par défaut / données historiques
# ---------------------------------------------------------------------------
def default_store(session) -> Optional["Store"]:
    """Retourne le magasin par défaut (ou le plus ancien) sans créer."""
    Store = _models()[0]
    store = session.query(Store).filter(Store.is_default == True).first()  # noqa: E712
    if store is None:
        store = session.query(Store).order_by(Store.id).first()
    return store


def default_store_id(session=None) -> Optional[int]:
    """Identifiant du magasin par défaut, ou None si aucun magasin."""
    with _session_scope(session) as session:
        try:
            store = default_store(session)
            return store.id if store else None
        except Exception:
            return None


def ensure_default_store(session) -> Optional["Store"]:
    """Garantit qu'au moins un magasin existe et rattache les données historiques.

    Idempotent : peut être appelé à chaque démarrage de l'application.
    Retourne le magasin par défaut. Lève une exception si la table `stores`
    n'existe pas encore (migration non appliquée) : l'appelant décide alors de
    continuer sans multi-magasins.
    """
    try:
        Store, Product, InventoryMovement, Sale = _models()

        stores = session.query(Store).order_by(Store.id).all()
        if not stores:
            store = Store(
                code=DEFAULT_STORE_CODE,
                name=DEFAULT_STORE_NAME,
                notes="Magasin créé automatiquement (multi-magasins).",
                active=True,
                is_default=True,
            )
            session.add(store)
            session.flush()
        else:
            store = next((s for s in stores if s.is_default), stores[0])
            if not store.is_default:
                store.is_default = True

        # Rattacher les enregistrements antérieurs au multi-magasins.
        for model in (Product, InventoryMovement, Sale):
            session.query(model).filter(model.store_id.is_(None)).update(
                {model.store_id: store.id}, synchronize_session=False
            )

        session.commit()
        # expire_on_commit=True : rafraîchir l'instance pour que l'appelant
        # puisse lire ses attributs après la fermeture éventuelle de la session.
        session.refresh(store)
        return store
    except Exception:
        session.rollback()
        raise


# ---------------------------------------------------------------------------
# Magasin actif
# ---------------------------------------------------------------------------
def get_active_store_id(session=None) -> Optional[int]:
    """Identifiant du magasin actif, validé en base ; None si aucun magasin."""
    settings = _settings_manager()
    raw_id = settings.get_setting(ACTIVE_STORE_SETTING_KEY) if settings else None

    with _session_scope(session) as session:
        try:
            Store = _models()[0]
            store = None
            if raw_id:
                try:
                    store = session.query(Store).filter(
                        Store.id == int(raw_id), Store.active == True  # noqa: E712
                    ).first()
                except (TypeError, ValueError):
                    store = None
            if store is None:
                store = session.query(Store).filter(
                    Store.active == True  # noqa: E712
                ).order_by(Store.is_default.desc(), Store.id).first()
            if store is None:
                return None
            if str(raw_id) != str(store.id) and settings is not None:
                # emit=False : changement technique, les vues se rechargent
                # elles-mêmes (sinon settings_changed déclenche un double
                # rechargement complet sur le thread UI = gel).
                settings.set_setting(ACTIVE_STORE_SETTING_KEY, store.id,
                                     emit=False)
            return int(store.id)
        except Exception:
            return None


def set_active_store_id(store_id, session=None) -> int:
    """Définit le magasin actif (doit exister et être actif)."""
    Store = _models()[0]
    with _session_scope(session) as session:
        store = session.query(Store).filter(Store.id == int(store_id)).first()
        if store is None:
            raise ValueError("Magasin introuvable.")
        if not store.active:
            raise ValueError(
                f"Le magasin « {store.name} » est désactivé : "
                "réactivez-le avant de l'utiliser."
            )
        settings = _settings_manager()
        if settings is not None:
            # emit=False : voir la note dans get_active_store_id.
            settings.set_setting(ACTIVE_STORE_SETTING_KEY, store.id, emit=False)
        return int(store.id)


def get_active_store(session=None) -> Optional["Store"]:
    """Objet magasin actif (ou None si aucun magasin n'existe)."""
    store_id = get_active_store_id(session)
    if store_id is None:
        return None
    with _session_scope(session) as session:
        Store = _models()[0]
        return session.query(Store).filter(Store.id == store_id).first()


def current_store_id_for(session=None) -> Optional[int]:
    """Magasin actif, ou magasin par défaut si aucun n'a été choisi."""
    store_id = get_active_store_id(session)
    if store_id is not None:
        return store_id
    return default_store_id(session)


# ---------------------------------------------------------------------------
# Filtrage des requêtes
# ---------------------------------------------------------------------------
def store_scope(session, column):
    """Critère SQLAlchemy limitant `column` au magasin actif.

    Retourne None si aucun magasin n'existe (base non migrée : aucun filtrage).
    Les lignes sans magasin (store_id NULL) restent visibles dans le magasin
    par défaut, par sécurité.
    """
    store_id = get_active_store_id(session)
    if store_id is None:
        return None
    store = default_store(session)
    if store is not None and store.id == store_id:
        return or_(column == store_id, column.is_(None))
    return column == store_id


def apply_store_scope(query, session, column):
    """Applique `store_scope` à une requête si un magasin existe."""
    scope = store_scope(session, column)
    return query if scope is None else query.filter(scope)


# ---------------------------------------------------------------------------
# CRUD magasins (UI)
# ---------------------------------------------------------------------------
class StoreManager:
    """Opérations de gestion des magasins pour l'interface.

    La session fournie appartient à l'appelant (vue Stock) : elle n'est pas
    fermée par cette classe.
    """

    def __init__(self, session=None):
        self._own_session = session is None
        self.session = session or SessionLocal()

    # -- interne ----------------------------------------------------------
    def close(self):
        if self._own_session:
            self.session.close()

    def _stores(self):
        return _models()[0]

    def _commit(self, *instances):
        """Commit + rollback en cas d'erreur, puis rafraîchit les instances."""
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        for instance in instances:
            if instance is not None:
                self.session.refresh(instance)

    # -- lecture ----------------------------------------------------------
    def list_stores(self, include_inactive: bool = True) -> List["Store"]:
        """Liste des magasins, triés par nom."""
        Store = self._stores()
        query = self.session.query(Store)
        if not include_inactive:
            query = query.filter(Store.active == True)  # noqa: E712
        return query.order_by(Store.name).all()

    def active_stores(self) -> List["Store"]:
        """Uniquement les magasins actifs (sélecteur de magasin)."""
        return self.list_stores(include_inactive=False)

    def get_store(self, store_id) -> Optional["Store"]:
        """Magasin par identifiant."""
        if store_id is None:
            return None
        Store = self._stores()
        return self.session.query(Store).filter(Store.id == int(store_id)).first()

    def get_active_store(self) -> Optional["Store"]:
        """Magasin actuellement sélectionné."""
        return get_active_store(self.session)

    def default_store(self) -> Optional["Store"]:
        """Magasin par défaut (reçoit les données non rattachées)."""
        return default_store(self.session)

    def default_store_id(self) -> Optional[int]:
        store = default_store(self.session)
        return int(store.id) if store else None

    def store_name(self, store_id) -> str:
        store = self.get_store(store_id)
        return str(store.name) if store else "—"

    def active_store_name(self) -> str:
        store = self.get_active_store()
        return str(store.name) if store else "—"

    # -- création / modification -----------------------------------------
    def _next_code(self) -> str:
        """Génère un code MAG-XXXX libre."""
        Store = self._stores()
        codes = [row[0] for row in self.session.query(Store.code).all() if row[0]]
        max_number = 0
        for code in codes:
            match = re.match(r"^MAG-(\d+)$", code.strip().upper())
            if match:
                max_number = max(max_number, int(match.group(1)))
        return f"MAG-{max_number + 1:04d}"

    def create_store(self, name, address="", phone="", manager_name="", notes="",
                     code=None, active=True) -> "Store":
        """Crée un magasin. Le tout premier magasin devient celui par défaut."""
        Store = self._stores()
        name = (name or "").strip()
        if not name:
            raise ValueError("Le nom du magasin est obligatoire.")

        if self.session.query(Store).filter(Store.name.ilike(name)).first():
            raise ValueError(f"Un magasin nommé « {name} » existe déjà.")

        final_code = (code or "").strip() or self._next_code()
        if self.session.query(Store).filter(Store.code == final_code).first():
            raise ValueError(f"Le code magasin « {final_code} » est déjà utilisé.")

        is_first = self.session.query(Store).count() == 0
        store = Store(
            code=final_code,
            name=name,
            address=(address or "").strip() or None,
            phone=(phone or "").strip() or None,
            manager_name=(manager_name or "").strip() or None,
            notes=(notes or "").strip() or None,
            active=bool(active),
            is_default=is_first,
        )
        self.session.add(store)
        self._commit(store)
        return store

    def update_store(self, store_id, **fields) -> "Store":
        """Met à jour les champs fournis d'un magasin."""
        Store = self._stores()
        store = self.get_store(store_id)
        if store is None:
            raise ValueError("Magasin introuvable.")

        if "name" in fields:
            name = (fields["name"] or "").strip()
            if not name:
                raise ValueError("Le nom du magasin est obligatoire.")
            duplicate = self.session.query(Store).filter(
                Store.name.ilike(name), Store.id != store.id
            ).first()
            if duplicate:
                raise ValueError(f"Un magasin nommé « {name} » existe déjà.")
            store.name = name

        for field in ("address", "phone", "manager_name", "notes"):
            if field in fields:
                value = fields[field]
                setattr(store, field, (value or "").strip() or None)

        if "active" in fields:
            store.active = bool(fields["active"])

        self._commit(store)
        return store

    def toggle_active(self, store_id) -> bool:
        """Active / désactive un magasin. Retourne le nouvel état."""
        Store = self._stores()
        store = self.get_store(store_id)
        if store is None:
            raise ValueError("Magasin introuvable.")

        if store.active:
            active_count = self.session.query(Store).filter(
                Store.active == True  # noqa: E712
            ).count()
            if active_count <= 1:
                raise ValueError(
                    "Impossible de désactiver le dernier magasin actif :\n"
                    "activez d'abord un autre magasin."
                )
            store.active = False
        else:
            store.active = True

        self._commit(store)
        return store.active

    def set_default_store(self, store_id) -> "Store":
        """Définit le magasin par défaut (reçoit les données non rattachées)."""
        Store = self._stores()
        store = self.get_store(store_id)
        if store is None:
            raise ValueError("Magasin introuvable.")

        self.session.query(Store).update(
            {Store.is_default: False}, synchronize_session=False
        )
        store.is_default = True
        self._commit(store)
        return store

    def delete_store(self, store_id):
        """Supprime un magasin vide (aucun produit, mouvement ni vente)."""
        Store, Product, InventoryMovement, Sale = _models()
        store = self.get_store(store_id)
        if store is None:
            raise ValueError("Magasin introuvable.")

        if self.session.query(Store).count() <= 1:
            raise ValueError(
                "Impossible de supprimer le dernier magasin.\n"
                "Désactivez-le plutôt si vous ne l'utilisez plus."
            )

        product_count = self.session.query(Product).filter(
            Product.store_id == store.id
        ).count()
        sale_count = self.session.query(Sale).filter(
            Sale.store_id == store.id
        ).count()
        movement_count = self.session.query(InventoryMovement).filter(
            InventoryMovement.store_id == store.id
        ).count()
        if product_count or sale_count or movement_count:
            raise ValueError(
                "Ce magasin contient encore des données :\n"
                f"• {product_count} produit(s)\n"
                f"• {sale_count} vente(s)\n"
                f"• {movement_count} mouvement(s)\n\n"
                "Videz-le ou désactivez-le plutôt (les données historiques "
                "seraient perdues)."
            )

        was_default = bool(store.is_default)
        self.session.delete(store)
        self._commit()

        if was_default:
            remaining = default_store(self.session)
            if remaining is not None and not remaining.is_default:
                remaining.is_default = True
                self._commit()

    # -- statistiques -----------------------------------------------------
    def store_summary(self, store_id) -> dict:
        """Résumé d'un magasin (produits, quantité, valeur du stock, alertes)."""
        _, Product, _, _ = _models()
        products = self.session.query(Product).filter(
            Product.store_id == int(store_id),
            Product.active == True,  # noqa: E712
        ).all()
        return {
            "products": len(products),
            "quantity": sum(p.quantity or 0 for p in products),
            "stock_value": sum(p.stock_value for p in products),
            "low_stock": len([p for p in products if p.is_low_stock]),
            "out_of_stock": len([p for p in products if p.is_out_of_stock]),
        }


def scope_products_query(query, session, model=None):
    """Applique la portée magasin à une requête portant sur `products`."""
    if model is None:
        model = _models()[1]
    return apply_store_scope(query, session, model.store_id)