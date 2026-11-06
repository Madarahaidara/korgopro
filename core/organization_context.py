"""Resolve the tenant for desktop operations that are scoped by store."""


def organization_id_for_store(session, store_id=None):
    """Return the organization owning a store, failing closed if unresolved.

    The desktop currently selects a store as its active operational context.
    Deriving the tenant from that store keeps every row written by the
    operation in the same organization and avoids silently inserting NULL.
    """
    from core.models.store import Store

    if store_id is None:
        from core.store_manager import current_store_id_for
        store_id = current_store_id_for(session)
    if store_id is None:
        raise ValueError("Aucun magasin actif ne permet d'identifier l'entreprise.")

    store = session.query(Store).filter(Store.id == int(store_id)).one_or_none()
    if store is None:
        raise ValueError(f"Magasin {store_id} introuvable.")
    if store.organization_id is None:
        raise ValueError(
            f"Le magasin {store.code} n'est rattaché à aucune entreprise."
        )
    return store.organization_id
