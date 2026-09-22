#!/usr/bin/env python3
"""
Outil de restauration de base de données pour Korgo Pro.
Fonctionne avec SQLite et PostgreSQL/Supabase.
"""

import sys
import os
import json
import sqlite3
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.database import engine, SessionLocal
from core.database_manager import DatabaseManager
from sqlalchemy import inspect, text


def export_sqlite_to_json(sqlite_path, output_json=None):
    """Exporter une base SQLite vers un fichier JSON portable."""
    if not os.path.exists(sqlite_path):
        print(f"Erreur: Fichier {sqlite_path} introuvable")
        return False
    
    if output_json is None:
        base = os.path.splitext(os.path.basename(sqlite_path))[0]
        output_json = f"{base}_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    print(f"\nExport de {sqlite_path} -> {output_json}")
    print(f"Taille: {os.path.getsize(sqlite_path)/1024:.1f} Ko")
    
    try:
        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row
        
        # Lister les tables
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Tables: {len(tables)}")
        
        payload = {"tables": {}}
        total = 0
        
        for table in tables:
            cursor = conn.execute(f"SELECT * FROM [{table}]")
            rows = [dict(row) for row in cursor.fetchall()]
            payload["tables"][table] = rows
            count = len(rows)
            total += count
            print(f"  {table}: {count} lignes")
        
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
        
        size = os.path.getsize(output_json)
        print(f"\nOK: Export reussi!")
        print(f"  Fichier: {size/1024:.1f} Ko -> {output_json}")
        print(f"  Tables: {len(tables)}, Lignes: {total}")
        
        conn.close()
        return output_json
        
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()
        return None


def restore_backup(backup_path):
    """Importer un backup (JSON portable ou base SQLite .db) vers la base active."""
    if not os.path.exists(backup_path):
        print(f"Erreur: Fichier {backup_path} introuvable")
        return False

    print(f"\nImport de {backup_path}")
    print(f"Taille: {os.path.getsize(backup_path)/1024:.1f} Ko")

    dm = DatabaseManager()

    # Lecture unifiée : gere aussi bien un export JSON qu'un fichier SQLite .db
    try:
        payload = dm._read_restore_payload(backup_path)
    except Exception as e:
        print(f"Erreur: {e}")
        return False

    tables = payload.get("tables", {})
    total = sum(len(rows) for rows in tables.values())

    print(f"Tables: {len(tables)}, Lignes: {total}")

    for table, rows in sorted(tables.items()):
        print(f"  {table}: {len(rows)} lignes")

    # Confirmation
    print(f"\nATTENTION: Cette operation va:")
    print("  - Remplacer les donnees des tables presentes dans le backup")
    print("  - Conserver les autres tables de la base")
    print("  - Cette action est IRREVERSIBLE")

    response = input("\nContinuer? (oui/non): ").strip().lower()
    if response not in ["oui", "yes", "o", "y"]:
        print("Annule")
        return False

    # Restauration via DatabaseManager
    try:
        result = dm.restore_database(backup_path)

        if result.get("success"):
            print(f"\nOK: {result.get('message', 'Restauration reussie')}")
            return True
        else:
            print(f"\nErreur: {result.get('message', 'Erreur inconnue')}")
            return False

    except Exception as e:
        print(f"Erreur inattendue: {e}")
        import traceback
        traceback.print_exc()
        return False


def export_and_restore(sqlite_path):
    """Export SQLite -> JSON, puis import JSON -> PostgreSQL (processus complet)."""
    # Étape 1: Export
    print("=" * 60)
    print("ETAPE 1: Export SQLite vers JSON")
    print("=" * 60)
    
    json_path = export_sqlite_to_json(sqlite_path)
    if json_path is None:
        print("\nEchec a l'etape 1")
        return False
    
    # Étape 2: Import
    print("\n" + "=" * 60)
    print("ETAPE 2: Import JSON vers PostgreSQL/Supabase")
    print("=" * 60)
    
    return restore_backup(json_path)


def diagnose():
    """Affiche l'etat de la base active et les fichiers de backup disponibles."""
    print("=" * 60)
    print("DIAGNOSTIC BASE DE DONNEES KORGO PRO")
    print("=" * 60)

    # 1) Base active
    url = str(engine.url)
    safe_url = url
    if "@" in url:
        # Masquer le mot de passe
        head, tail = url.split("@", 1)
        if ":" in head:
            scheme, creds = head.split("://", 1) if "://" in head else ("", head)
            user = creds.split(":")[0]
            safe_url = f"{scheme}://{user}:***@{tail}" if scheme else f"{user}:***@{tail}"
    print(f"\n[1] Base active : {engine.dialect.name}")
    print(f"    URL        : {safe_url}")

    try:
        insp = inspect(engine)
        tables = insp.get_table_names()
        print(f"    Tables     : {len(tables)}")
        with engine.connect() as conn:
            total = 0
            for t in sorted(tables):
                n = conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
                total += n or 0
            print(f"    Lignes     : {total}")
    except Exception as e:
        print(f"    Erreur de connexion : {e}")

    # 2) Fichiers de backup presents dans le dossier courant
    print("\n[2] Fichiers de backup detectes :")
    found = False
    for pattern, label in ((".json", "export JSON"), (".db", "base SQLite")):
        for name in sorted(os.listdir(PROJECT_ROOT)):
            if not name.endswith(pattern):
                continue
            path = os.path.join(PROJECT_ROOT, name)
            if not os.path.isfile(path):
                continue
            size = os.path.getsize(path) / 1024
            kind = "SQLite" if DatabaseManager._is_sqlite_file(path) else label
            print(f"    - {name} ({size:.1f} Ko, {kind})")
            found = True
    if not found:
        print("    (aucun)")

    print("\n[3] Commandes utiles :")
    print("    python restore_tool.py restore-json <fichier.json|fichier.db>")
    print("    python restore_tool.py export-sqlite <fichier.db>")
    print("    python restore_tool.py export-and-restore <fichier.db>")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nCommandes:")
        print("  diagnose                      - Voir l'etat actuel")
        print("  export-sqlite <fichier.db>    - Exporter SQLite vers JSON")
        print("  restore-json <fichier>        - Importer JSON ou .db vers la base")
        print("  export-and-restore <fichier.db> - Auto: export + import")
        sys.exit(1)
    
    cmd = sys.argv[1].lower()
    
    if cmd == "diagnose":
        diagnose()
    
    elif cmd == "export-sqlite":
        sqlite_path = sys.argv[2] if len(sys.argv) > 2 else input("Fichier SQLite: ")
        output = sys.argv[3] if len(sys.argv) > 3 else None
        result = export_sqlite_to_json(sqlite_path, output)
        if result:
            print(f"\nFichier JSON cree: {result}")
        sys.exit(0 if result else 1)
    
    elif cmd == "restore-json":
        json_path = sys.argv[2] if len(sys.argv) > 2 else input("Fichier (JSON ou .db): ")
        success = restore_backup(json_path)
        sys.exit(0 if success else 1)
    
    elif cmd == "export-and-restore":
        sqlite_path = sys.argv[2] if len(sys.argv) > 2 else input("Fichier SQLite: ")
        success = export_and_restore(sqlite_path)
        sys.exit(0 if success else 1)
    
    else:
        print(f"Commande inconnue: {cmd}")
        print("Utilisez 'diagnose' pour voir les commandes disponibles.")
        sys.exit(1)

