# ============================================================================
# fix_sequences.py
#
# Après une migration SQLite -> PostgreSQL, les séquences d'auto-incrément
# (SERIAL) ne sont pas avancées : les lignes migrées gardent leurs ids
# explicites (1, 2, ...) mais la séquence reste à 1. Le prochain INSERT
# tente donc un id déjà utilisé -> UniqueViolation.
#
# Ce script resynchronise chaque séquence sur max(id)+1 pour toutes les
# tables du schéma applicatif.
#
# Usage :
#   python fix_sequences.py
# ============================================================================

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

try:  # pragma: no cover
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except Exception:
    pass

from sqlalchemy import text
from core.database import Base, engine

# IMPORTANT : importer les modèles pour peupler Base.metadata,
# sinon la boucle ne voit aucune table.
from core.models import customer, user, activity_log, sale_log  # noqa: F401,E402
from core.models import sale_models  # noqa: F401,E402
from core.models import stock_models  # noqa: F401,E402
from core.models import treasury_models  # noqa: F401,E402

def main():
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            id_col = table.c.get("id")
            if id_col is None:
                continue
            # pg_get_serial_sequence renvoie le nom de séquence pour une colonne
            # SERIAL/IDENTITY, sinon NULL
            seq = conn.execute(
                text("SELECT pg_get_serial_sequence(:t, 'id')"), {"t": table.name}
            ).scalar()
            if not seq:
                print(f"   - {table.name}: pas de séquence (skippé)")
                continue
            max_id = conn.execute(
                text(f'SELECT COALESCE(MAX("{table.name}".id), 0) FROM "{table.name}"')
            ).scalar()
            if max_id:
                conn.execute(
                    text("SELECT setval(:seq, :v, true)"), {"seq": seq, "v": max_id}
                )
                print(f"   - {table.name}: séquence -> {max_id}")
            else:
                # Table vide : poser la séquence à 1 sans "last_value" (setval false)
                conn.execute(text("SELECT setval(:seq, 1, false)"), {"seq": seq})
                print(f"   - {table.name}: vide, séquence -> 1")

    print("\nSéquences resynchronisées. Insérer maintenant fonctionne.")

if __name__ == "__main__":
    main()