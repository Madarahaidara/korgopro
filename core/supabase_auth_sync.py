# ============================================================================
# COMPATIBILITE — la logique vit desormais dans `core.supabase_auth`.
#
# Historiquement ce module gerait public.users (bcrypt local) ET miroitait
# vers auth.users. Depuis la refonte, Supabase Auth est la SOURCE DE VERITE
# UNIQUE : ce fichier ne fait plus que reexporter l'API de `core.supabase_auth`
# pour ne pas casser les appels existants.
#
# Nouveau code : importez directement `core.supabase_auth`.
# ============================================================================
from core.supabase_auth import (  # noqa: F401
    delete_auth_user,
    get_auth_id,
    hash_password,
    list_auth_users,
    password_matches_auth_hash,
    provision_auth_user,
    resolve_email,
    set_auth_active,
    supabase_available,
    update_auth_email,
    update_auth_password,
    verify_credentials,
)

__all__ = [
    "delete_auth_user",
    "get_auth_id",
    "hash_password",
    "list_auth_users",
    "password_matches_auth_hash",
    "provision_auth_user",
    "resolve_email",
    "set_auth_active",
    "supabase_available",
    "update_auth_email",
    "update_auth_password",
    "verify_credentials",
]