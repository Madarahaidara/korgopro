"""Diagnostic LECTURE SEULE : portee magasin (desktop vs web).

Verifie les hypotheses d'indisponibilite de la liste des produits cote web :
  1. list des magasins (id, code, nom, actif, is_default) ;
  2. repartition des produits / ventes / mouvements par store_id ;
  3. colonnes NULL cote produits (name, code, category...) qui font planter le
     filtrage JavaScript ;
  4. ce que voit reellement un utilisateur Supabase Auth (SET ROLE
     authenticated) sur products / stores.

Aucune ecriture n'est conservee : toutes les transactions sont annulees.
Usage : python _diag_web_store_sync.py
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

load_dotenv(".env")
engine = create_engine(os.environ["DATABASE_URL"], connect_args={"sslmode": "require"})

TEXT_COLS = ["code", "name", "category", "description", "location", "barcode", "unit"]


def main():
    with engine.connect() as c:
        print("=== 1. Magasins ===")
        for r in c.execute(text(
                "SELECT id, code, name, active, is_default FROM stores ORDER BY id")):
            print(f"  id={r[0]} code={r[1]:<10} nom={r[2]:<20} actif={r[3]} defaut={r[4]}")

        print("\n=== 2. Repartition par store_id ===")
        for table in ["products", "sales", "inventory_movements",
                      "proforma_invoices"]:
            # Toutes les tables n'ont pas de colonne store_id
            # (proforma_invoices, par exemple) : on le verifie avant de filtrer.
            has_col = c.execute(text(
                "SELECT 1 FROM information_schema.columns WHERE table_schema='public' "
                "AND table_name=:n AND column_name='store_id'"), {"n": table}).fetchone()
            if not has_col:
                print(f"  {table:<22} (pas de colonne store_id)")
                continue
            rows = c.execute(text(
                f"SELECT store_id, count(*) FROM {table} GROUP BY store_id "
                "ORDER BY store_id")).fetchall()
            print(f"  {table:<22} {rows}")

        print("\n=== 3. Colonnes NULL cote products ===")
        cols = [r[0] for r in c.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='products' "
            "ORDER BY ordinal_position"))]
        print("  colonnes:", ", ".join(cols))
        counts = ", ".join(
            f"sum(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END) AS {col}"
            for col in cols)
        row = c.execute(text(f"SELECT count(*) AS total, {counts} FROM products")).mappings().first()
        for k, v in row.items():
            flag = "  <-- NULL" if k != "total" and v else ""
            print(f"    {k:<22} {v}{flag}")

        print("\n=== 4. NULL sur les colonnes texte utilisees par le filtrage JS ===")
        for col in TEXT_COLS:
            if col not in cols:
                continue
            n = c.execute(text(f"SELECT count(*) FROM products WHERE {col} IS NULL")).scalar()
            print(f"    products.{col:<14} NULL={n}")

        print("\n=== 5. Lectures reelles d'un utilisateur Auth (annule) ===")
        for uid, email in c.execute(text(
                "SELECT id, email FROM auth.users ORDER BY created_at")).fetchall():
            conn = engine.connect()
            conn.execute(text("SET LOCAL role authenticated"))
            conn.execute(text("SELECT set_config('request.jwt.claims', :j, true)"),
                         {"j": '{"sub":"%s","email":"%s"}' % (uid, email)})
            rows = conn.execute(text(
                "SELECT store_id, count(*) FROM products GROUP BY store_id "
                "ORDER BY store_id")).fetchall()
            nstores = conn.execute(text("SELECT count(*) FROM stores")).scalar()
            print(f"  {email:<32} stores={nstores} products_par_store={rows}")
            conn.rollback()
            conn.close()


if __name__ == "__main__":
    main()
