# init_db.py
from core.database import engine, Base, init_database
from core.models.user import User
from core.models.activity_log import ActivityLog
from sqlalchemy import text

def add_missing_columns():
    """Ajouter les colonnes manquantes à la table users"""
    try:
        with engine.connect() as conn:
            # Vérifier si la colonne last_ip existe
            result = conn.execute(text("PRAGMA table_info(users)"))
            columns = [row[1] for row in result]
            
            if 'last_ip' not in columns:
                print("Ajout de la colonne last_ip...")
                conn.execute(text("ALTER TABLE users ADD COLUMN last_ip VARCHAR(45)"))
                conn.commit()
            
            if 'must_change_password' not in columns:
                print("Ajout de la colonne must_change_password...")
                conn.execute(text("ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT 1"))
                conn.commit()
            
            print("Colonnes ajoutées avec succès!")
    except Exception as e:
        print(f"Erreur lors de l'ajout des colonnes: {e}")

if __name__ == "__main__":
    print("Initialisation de la base de données...")
    
    # Créer toutes les tables
    init_database()
    
    # Ajouter les colonnes manquantes
    add_missing_columns()
    
    print("Base de données initialisée avec succès!")