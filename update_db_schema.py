# -*- coding: utf-8 -*-
"""
Migration du schéma d'une base SQLite sur les modèles SQLAlchemy actuels.

Utilisation:
    python update_db_schema.py [chemin_vers_base.db]
    (par défaut : base.db)

Ce script ajoute les tables et colonnes manquantes UNIQUEMENT, sans jamais
supprimer ni modifier les données existantes. Il est idempotent : relancer
plusieurs fois ne casse rien.
"""
import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.dialects import sqlite as sqlite_dialect

# S'assurer que le projet est importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import Base  # noqa: E402

# IMPORTANT : importer tous les modèles pour remplir Base.metadata,
# sinon create_all() ne créerait aucune table.
from core.models.user import User  # noqa: E402,F401
from core.models.activity_log import ActivityLog  # noqa: E402,F401
from core.models.sale_log import SaleLog  # noqa: E402,F401
from core.models.customer import Customer  # noqa: E402,F401
from core.models.stock_models import (  # noqa: E402,F401
    Product, Supplier, InventoryMovement,
    ExpenseCategory, Expense, PurchaseOrder,
    PurchaseOrderItem, StockAlert,
)
from core.models.sale_models import (  # noqa: E402,F401
    Sale, SaleItem, Payment, SaleReturn, SaleReturnItem,
    ProformaInvoice, ProformaInvoiceItem,
)
# Multi-magasins : table `stores` + colonnes store_id sur products /
# inventory_movements / sales (colonnes ajoutées par la boucle ALTER ci-dessous).
from core.models.store import Store  # noqa: E402,F401

DB_DEFAULT = "base.db"

# Défauts SQL pour les colonnes ajoutées (clé = (table, colonne)).
# Ces valeurs correspondent aux défauts Python des modèles, afin que les
# lignes déjà existantes reçoivent les bonnes valeurs.
COLUMN_SQL_DEFAULTS = {
    ("users", "must_change_password"): "DEFAULT 1",
    ("users", "last_ip"): "NULL",
    ("sales", "type_document"): "DEFAULT 'FACTURE'",
    ("sales", "origine_proforma_id"): "NULL",
    ("sales", "date_conversion"): "NULL",
    ("sales", "utilisateur_conversion"): "NULL",
    ("sales", "statut"): "DEFAULT 'BROUILLON'",
    ("sales", "date_expiration"): "NULL",
    ("sales", "version"): "DEFAULT 1",
}
# NOTE : les colonnes multi-magasins (products.store_id, inventory_movements.store_id,
# sales.store_id) utilisent le défaut générique "NULL" puis sont rattachées au
# magasin par défaut par ensure_default_store() en fin de migration.


def get_type_clause(col):
    """Renvoie le type SQLite d'une colonne SQLAlchemy."""
    try:
        return col.type.compile(dialect=sqlite_dialect.dialect())
    except Exception:
        return col.type.__class__.__name__.upper()


def existing_columns(conn, table):
    """Retourne la liste des noms de colonnes existants dans une table."""
    return [row[1] for row in conn.execute(text(
        'PRAGMA table_info("{}")'.format(table.replace('"', '""'))
    ))]


def align_schema(db_path):
    if not os.path.exists(db_path):
        print(f"⚠️  Fichier {db_path} introuvable.")
        return False

    print(f"🔧 Migration du schéma vers : {db_path}")

    # Engine dédié à base.db (ne touche pas korgo_pro.db)
    engine = create_engine(
        "sqlite:///" + os.path.abspath(db_path).replace("\\", "/"),
        echo=False,
        connect_args={"check_same_thread": False},
    )

    # 1) Créer les TABLES manquantes (create_all() est idempotent)
    Base.metadata.create_all(bind=engine)
    print("   ✓ Tables créées / vérifiées "
          "(activity_logs, sale_logs, proforma_invoices, proforma_invoice_items, ...)")

    # 2) ALTER TABLE : ajouter les colonnes manquantes
    changes = 0
    with engine.connect() as conn:
        for table_name, table in Base.metadata.tables.items():
            existing = existing_columns(conn, table_name)
            missing = [c for c in table.columns if c.name not in existing]
            if not missing:
                continue

            for col in missing:
                sql_default = COLUMN_SQL_DEFAULTS.get((table_name, col.name), "NULL")
                type_clause = get_type_clause(col)
                ddl = 'ALTER TABLE "{}" ADD COLUMN "{}" {} {}'.format(
                    table_name.replace('"', '""'),
                    col.name.replace('"', '""'),
                    type_clause,
                    sql_default,
                )
                print(f"   + {table_name}.{col.name}  ({type_clause} {sql_default})")
                conn.execute(text(ddl))
                changes += 1

        conn.commit()

    # 3) Multi-magasins : créer/rattacher un magasin par défaut.
    #    (idempotent : ne fait rien si un magasin existe déjà)
    try:
        from sqlalchemy.orm import sessionmaker
        from core.store_manager import ensure_default_store
        SessionFactory = sessionmaker(bind=engine)
        with SessionFactory() as session:
            store = ensure_default_store(session)
        print(f"   ✓ Magasin par défaut : {store.name} ({store.code})")
    except Exception as exc:
        print(f"   ⚠️  Initialisation des magasins ignorée : {exc}")

    engine.dispose()
    print(f"   ✓ {changes} colonne(s) ajoutée(s) avec succès.")
    print("✅ Schéma mis à jour. Données inchangées.")
    return True


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else DB_DEFAULT
    ok = align_schema(path)
    sys.exit(0 if ok else 1)