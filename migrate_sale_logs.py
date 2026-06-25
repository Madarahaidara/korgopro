# migrate_sale_logs.py
from pathlib import Path
import sys

# Ajouter la racine du projet aux imports pour les scripts utilitaires
PROJECT_ROOT = Path(__file__).resolve().parents[0]
sys.path.insert(0, str(PROJECT_ROOT))

from core.database import engine, Base
from sqlalchemy import inspect, text

def create_sale_logs_table():
    """Créer la table sale_logs si elle n'existe pas"""
    try:
        inspector = inspect(engine)
        
        if 'sale_logs' not in inspector.get_table_names():
            print("📝 Création de la table sale_logs...")
            
            # Importer le modèle
            from core.models.sale_log import SaleLog
            
            # Créer la table
            Base.metadata.create_all(bind=engine, tables=[SaleLog.__table__])
            print("✅ Table sale_logs créée avec succès!")
        else:
            print("ℹ️ La table sale_logs existe déjà.")
            
    except Exception as e:
        print(f"❌ Erreur lors de la création de sale_logs: {e}")

def add_missing_columns_to_users():
    """Ajouter les colonnes manquantes à la table users"""
    try:
        inspector = inspect(engine)
        
        if 'users' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('users')]
            
            with engine.connect() as conn:
                if 'last_ip' not in columns:
                    print("📝 Ajout de la colonne last_ip à users...")
                    conn.execute(text("ALTER TABLE users ADD COLUMN last_ip VARCHAR(45)"))
                    conn.commit()
                    print("✅ Colonne last_ip ajoutée")
                else:
                    print("ℹ️ La colonne last_ip existe déjà")
                
                if 'must_change_password' not in columns:
                    print("📝 Ajout de la colonne must_change_password à users...")
                    conn.execute(text("ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT 1"))
                    conn.commit()
                    print("✅ Colonne must_change_password ajoutée")
                else:
                    print("ℹ️ La colonne must_change_password existe déjà")
    except Exception as e:
        print(f"⚠️ Erreur lors de l'ajout des colonnes à users: {e}")

def check_all_tables():
    """Vérifier que toutes les tables nécessaires existent"""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    print("\n📋 Tables existantes dans la base de données:")
    required_tables = ['users', 'activity_logs', 'sale_logs', 'products', 'suppliers', 'customers', 'sales']
    
    for table in required_tables:
        if table in tables:
            print(f"  ✅ {table}")
        else:
            print(f"  ❌ {table} (MANQUANTE)")

def main():
    print("=" * 60)
    print("🗄️ MIGRATION DE LA BASE DE DONNÉES")
    print("=" * 60)
    
    # Créer la table sale_logs
    create_sale_logs_table()
    
    # Ajouter les colonnes manquantes à users
    add_missing_columns_to_users()
    
    # Vérifier toutes les tables
    check_all_tables()
    
    print("\n" + "=" * 60)
    print("✅ Migration terminée avec succès!")
    print("=" * 60)

if __name__ == "__main__":
    main()