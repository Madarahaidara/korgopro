# ============================================================================
# migrate_sqlite_to_postgres.py
#
# Outil de migration des données : copie le contenu de la base SQLite locale
# (korgo_pro.db) vers la base PostgreSQL / Supabase active.
#
# Usage :
#   python migrate_sqlite_to_postgres.py
#   python migrate_sqlite_to_postgres.py --source korgo_pro.db
#   python migrate_sqlite_to_postgres.py --url "postgresql+psycopg2://..."
#   python migrate_sqlite_to_postgres.py --dry-run   # n'écrit rien sur la cible
#
# Prérequis :
#   - Le schéma PostgreSQL est créé automatiquement (Base.metadata.create_all).
#     En production, préférez `alembic upgrade head` contre la base cible.
#   - La migration est IDEMPOTENTE : les lignes déjà présentes (même id) sont
#     ignorées (on_conflict_do_nothing).
# ============================================================================

import argparse
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)


def main():
    parser = argparse.ArgumentParser(description="Migrer SQLite -> PostgreSQL / Supabase")
    parser.add_argument("--source", default="korgo_pro.db", help="Chemin du fichier SQLite source")
    parser.add_argument("--url", default=None, help="URL PostgreSQL cible (sinon variable DATABASE_URL)")
    parser.add_argument("--dry-run", action="store_true", help="Affiche le plan sans écrire")
    args = parser.parse_args()

    try:  # pragma: no cover
        from dotenv import load_dotenv
        load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
    except Exception:
        pass

    from sqlalchemy import create_engine, MetaData, text
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    # Modèles ORM (source de vérité du schéma)
    from core.database import Base
    from core.models import customer, user, activity_log, sale_log  # noqa: F401
    from core.models import sale_models  # noqa: F401
    from core.models import stock_models  # noqa: F401
    from core.models import treasury_models  # noqa: F401

    src_file = args.source
    if not os.path.exists(src_file):
        print(f"[ERREUR] Fichier SQLite introuvable : {src_file}")
        sys.exit(1)

    target_url = args.url or os.environ.get("DATABASE_URL", "")
    if not target_url:
        print(
            "[ERREUR] Aucune URL cible. Passez --url ou définissez DATABASE_URL "
            "(voir .env.example)."
        )
        sys.exit(1)
    if target_url.startswith("sqlite"):
        print("[ERREUR] La cible doit être PostgreSQL/Supabase, pas SQLite.")
        sys.exit(1)

    sqlite_url = "sqlite:///" + src_file.replace("\\", "/")
    src_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    dst_engine = create_engine(target_url, connect_args={"sslmode": "require"})

    # 1) Créer le schéma sur la cible (idempotent)
    print("[1/3] Création / vérification du schéma PostgreSQL...")
    if not args.dry_run:
        Base.metadata.create_all(bind=dst_engine)

    # 2) Lire les tables du modèle dans l'ordre des dépendances FK
    tables = Base.metadata.sorted_tables
    print(f"[2/3] Analyse de {len(tables)} tables.")

    # 3) Copier les données
    total = 0

    def _count_rows(sconn, table):
        """Compte les lignes d'une table source (aucune écriture)."""
        src_meta = MetaData()
        src_meta.reflect(bind=src_engine, only=[table.name])
        if table.name not in src_meta.tables:
            print(f"   - (skippé) table source absente : {table.name}")
            return 0
        src_table = src_meta.tables[table.name]
        rows = [dict(r._mapping) for r in sconn.execute(src_table.select())]
        print(f"   - {table.name}: {len(rows)} ligne(s) (dry-run)")
        return len(rows)

    if args.dry_run:
        # Aucune connexion vers la cible : on ne fait que dénombrer la source.
        with src_engine.connect() as sconn:
            for table in tables:
                total += _count_rows(sconn, table)
    else:
        with src_engine.connect() as sconn, dst_engine.begin() as dconn:
            # Désactiver la vérification des FK le temps de la copie : les
            # contraintes créées par SQLAlchemy ne sont pas DEFERRABLE (donc
            # SET CONSTRAINTS ALL DEFERRED est sans effet) et le schéma contient
            # un cycle (proforma_invoices <-> sales) qui empêche un tri fiable.
            if dconn.dialect.name == "postgresql":
                dconn.execute(text("SET session_replication_role = replica"))

            for table in tables:
                # Refléter la table source pour lire les colonnes réellement présentes
                src_meta = MetaData()
                src_meta.reflect(bind=src_engine, only=[table.name])
                if table.name not in src_meta.tables:
                    print(f"   - (skippé) table source absente : {table.name}")
                    continue
                src_table = src_meta.tables[table.name]

                rows = [dict(r._mapping) for r in sconn.execute(src_table.select())]
                if not rows:
                    print(f"   - {table.name}: 0 ligne")
                    continue

                # Ne garder que les colonnes existant aussi dans le modèle
                model_cols = {c.name for c in table.columns}
                clean = [{k: v for k, v in r.items() if k in model_cols} for r in rows]

                stmt = pg_insert(table).on_conflict_do_nothing()
                # Batch par blocs pour éviter un paquet trop gros
                BATCH = 500
                for i in range(0, len(clean), BATCH):
                    dconn.execute(stmt, clean[i:i + BATCH])
                print(f"   - {table.name}: {len(clean)} ligne(s)")
                total += len(clean)

            if dconn.dialect.name == "postgresql":
                dconn.execute(text("SET session_replication_role = default"))

    print(f"\nTerminé. {total} ligne(s) migrée(s) vers PostgreSQL.")

    # Synchroniser les séquences d'auto-incrément (sinon INSERT -> UniqueViolation)
    if not args.dry_run:
        print("[+] Resynchronisation des séquences...")
        with dst_engine.begin() as dconn:
            for table in tables:
                if "id" not in table.c:
                    continue
                seq = dconn.execute(
                    text("SELECT pg_get_serial_sequence(:t, 'id')"), {"t": table.name}
                ).scalar()
                if not seq:
                    continue
                max_id = dconn.execute(
                    text(f'SELECT COALESCE(MAX("{table.name}".id), 0) FROM "{table.name}"')
                ).scalar()
                if max_id:
                    dconn.execute(text("SELECT setval(:seq, :v, true)"), {"seq": seq, "v": max_id})
                else:
                    dconn.execute(text("SELECT setval(:seq, 1, false)"), {"seq": seq})
        print("[+] Séquences OK (id suivants: max_id+1).")

    if total and not args.dry_run:
        print("Pensez à vérifier que DATABASE_URL pointe bien vers Supabase dans votre .env.")


if __name__ == "__main__":
    main()