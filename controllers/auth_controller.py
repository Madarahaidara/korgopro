from core.models.user import User
from core.database import SessionLocal
from core.security import verify_password, migrate_old_hash, _is_bcrypt_hash
from datetime import datetime


class AuthController:
    def authenticate(self, username: str, password: str):
        """Authentifier un utilisateur"""
        try:
            with SessionLocal() as session:
                user = session.query(User).filter(User.username == username).first()
                
                if not user or not user.active:
                    return None

                # Vérifier le mot de passe
                if verify_password(password, user.password_hash):
                    # Mettre à jour la date de dernière connexion
                    user.last_login = datetime.utcnow()
                    
                    # Migration automatique SHA256 → bcrypt si nécessaire
                    if not _is_bcrypt_hash(user.password_hash):
                        user.password_hash = migrate_old_hash(password, user.password_hash)
                        print(f"[INFO] Mot de passe de '{user.username}' migre SHA256 vers bcrypt")
                    
                    session.commit()

                    return {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "role": user.role,
                        "active": user.active,
                        "last_login": user.last_login
                    }
                else:
                    return None

        except Exception as e:
            print(f"Erreur d'authentification: {e}")
            return None

    def verify_password(self, username: str, password: str) -> bool:
        """Vérifie si le mot de passe fourni correspond à l'utilisateur"""
        try:
            with SessionLocal() as session:
                user = session.query(User).filter(User.username == username).first()
                if not user:
                    return False
                return verify_password(password, user.password_hash)
        except Exception as e:
            print(f"Erreur lors de la vérification du mot de passe: {e}")
            return False
    
    def get_user_by_id(self, user_id: int):
        """Récupérer un utilisateur par son ID"""
        try:
            with SessionLocal() as session:
                user = session.query(User).filter(User.id == user_id).first()
                if user:
                    return {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "role": user.role,
                        "active": user.active,
                        "created_at": user.created_at,
                        "last_login": user.last_login
                    }
                return None
        except Exception as e:
            print(f"Erreur lors de la récupération de l'utilisateur: {e}")
            return None
