#!/usr/bin/env python3
"""
Script pour réinitialiser la base de données avec un utilisateur admin par défaut.
- Supprime la base de données existante
- Recrée toutes les tables
- Crée l'utilisateur admin (admin / admin123)
"""

import os
import sys
from datetime import datetime

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import Base, engine, SessionLocal
from core.models.user import User
from core.security import hash_password


def reset_database():
    """Réinitialiser la base de données avec l'utilisateur admin par défaut"""
    print("=" * 60)
    print("🔄 RÉINITIALISATION DE LA BASE DE DONNÉES")
    print("=" * 60)

    # 1. Supprimer le fichier de base de données
    db_file = "korgo_pro.db"
    if os.path.exists(db_file):
        os.remove(db_file)
        print(f"🗑️  Fichier {db_file} supprimé")
    else:
        print(f"ℹ️  Fichier {db_file} introuvable (rien à supprimer)")

    # 2. Créer toutes les tables
    print("🔧 Création des tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tables créées avec succès!")

    # 3. Créer l'utilisateur admin par défaut
    print("👤 Création de l'utilisateur admin...")
    db = SessionLocal()
    try:
        admin_user = User(
            username="admin",
            password_hash=hash_password("admin123"),
            email="admin@korgo.com",
            role="ADMIN",
            active=True,
            must_change_password=False,
            created_at=datetime.now()
        )
        db.add(admin_user)
        db.commit()
        print("✅ Utilisateur admin créé avec succès!")
    except Exception as e:
        db.rollback()
        print(f"❌ Erreur lors de la création de l'utilisateur admin: {e}")
        raise
    finally:
        db.close()

    # 4. Afficher les informations de connexion
    print("\n" + "=" * 60)
    print("🔐 INFORMATIONS DE CONNEXION")
    print("=" * 60)
    print("👑 ADMINISTRATEUR:")
    print(f"   Username: admin")
    print(f"   Password: admin123")
    print(f"   Email: admin@korgo.com")
    print(f"   Role: ADMIN")
    print("=" * 60)
    print("🎉 Base de données réinitialisée avec succès!")
    print("💡 Utilisez 'admin' / 'admin123' pour vous connecter")


if __name__ == "__main__":
    reset_database()