import bcrypt
import hashlib


def _is_bcrypt_hash(hashed: str) -> bool:
    """Vérifie si un hash est au format bcrypt ($2b$ ou $2a$)"""
    return hashed.startswith(('$2b$', '$2a$', '$2y$'))


def hash_password(password: str) -> str:
    """Hasher un mot de passe avec bcrypt (recommandé)"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """
    Vérifier un mot de passe hashé.
    
    - Si le hash est bcrypt : vérification directe (recommandé)
    - Si le hash est SHA256 (ancien format) : vérifié MAIS un appel à 
      migrate_old_hash() doit être fait après vérification réussie
      pour migrer vers bcrypt.
    
    Retourne:
        (bool) True si le mot de passe correspond, False sinon
    """
    try:
        # Si c'est du bcrypt, vérification directe
        if _is_bcrypt_hash(hashed):
            return bcrypt.checkpw(password.encode(), hashed.encode())
        
        # Fallback SHA256 pour compatibilité anciens mots de passe
        # (À migrer vers bcrypt dès que possible via migrate_old_hash)
        sha256_hash = hashlib.sha256(password.encode()).hexdigest()
        return sha256_hash == hashed
        
    except (ValueError, Exception):
        return False


def migrate_old_hash(password: str, old_hash: str) -> str:
    """
    Migre un ancien hash SHA256 vers bcrypt.
    À appeler APRÈS une vérification réussie avec verify_password().
    
    Args:
        password: le mot de passe en clair (déjà vérifié)
        old_hash: l'ancien hash (bcrypt ou SHA256)
    
    Returns:
        str: le nouveau hash bcrypt
    """
    # Si déjà bcrypt, on garde tel quel
    if _is_bcrypt_hash(old_hash):
        return old_hash
    
    # Migrer SHA256 → bcrypt
    return hash_password(password)