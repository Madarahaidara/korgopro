"""Applique les étapes de la migration 0002_multi_magasins sans Alembic
(contournement : le mot de passe DB contient des % incompatibles avec
l'interpolation de configparser utilisé par alembic.ini)."""
from core.database import engine
import sqlalchemy as sa
from core.database import Base
import core.models.store  # noqa: F401
import core.models.stock_models  # noqa: F401
import core.models.sale_models  # noqa: F401

with engine.begin() as bind:
    Base.metadata.create_all(bind=bind)
    insp = sa.inspect(bind)
    for table in ("products", "inventory_movements", "sales"):
        if table not in insp.get_table_names():
            print(f"{table}: table absente, ignorée")
            continue
        cols = {c["name"] for c in insp.get_columns(table)}
        if "store_id" not in cols:
            bind.execute(sa.text(
                f"ALTER TABLE {table} ADD COLUMN store_id INTEGER"))
            print(f"{table}: colonne store_id AJOUTÉE")
        else:
            print(f"{table}: store_id déjà présente")
    # Magasin par défaut si la table stores est vide
    if "stores" in insp.get_table_names():
        n = bind.execute(sa.text("SELECT count(*) FROM stores")).scalar()
        if not n:
            bind.execute(sa.text(
                "INSERT INTO stores (code, name, active, is_default) "
                "VALUES ('MAG-0001', 'Magasin principal', true, true)"))
            print("stores: magasin principal inséré")
        else:
            print(f"stores: {n} magasin(s) déjà présent(s)")
    # Rattacher les données historiques au magasin par défaut
    default = bind.execute(sa.text(
        "SELECT id FROM stores ORDER BY is_default DESC, id LIMIT 1")).scalar()
    if default:
        for table in ("products", "inventory_movements", "sales"):
            r = bind.execute(sa.text(
                f"UPDATE {table} SET store_id={default} WHERE store_id IS NULL"))
            print(f"{table}: {r.rowcount} ligne(s) rattachée(s) au magasin {default}")
print("MIGRATION TERMINÉE")
