// ============================================================================
// Contexte de gestion multi-magasins.
// Fournit la liste des magasins et le magasin actif à toute l'application.
//
// POINT CRITIQUE : les magasins réels n'arrivent qu'APRÈS la connexion
// (`hydrate()` télécharge la base Supabase). Si l'interface se contentait de
// l'état calculé au premier rendu, elle resterait figée sur le magasin de
// secours fabriqué localement (id 1, « Magasin principal ») alors que les
// services filtrent, eux, sur le magasin réellement mémorisé : la liste des
// produits apparaîtrait vide et le sélecteur ne proposerait plus aucun magasin
// valide (impossible de revenir sur le magasin principal).
//
// La liste et le magasin actif sont donc RECALCULÉS à chaque changement d'état
// de synchronisation (onSyncStatus), et le magasin actif est toujours lu via
// `getActiveStoreId()` : l'interface ne peut pas diverger du filtrage.
// ============================================================================
import { createContext, useContext, useState, useCallback, useMemo, useSyncExternalStore } from 'react';
import { onSyncStatus, syncState } from '../api/db';
import {
  listStores,
  getActiveStoreId,
  setActiveStoreId,
  createStore,
  updateStore,
  deleteStore,
  toggleStoreActive,
  getActiveStore,
} from '../api/storesApi';

const StoreContext = createContext(null);

/** Empreinte des données de synchronisation (doit être une chaîne stable). */
function syncVersion() {
  return [
    syncState.mode,
    syncState.hydrated ? '1' : '0',
    syncState.pending,
    syncState.lastSyncAt || '',
    syncState.lastError || '',
  ].join('|');
}

export function StoreProvider({ children }) {
  // Se réabonne aux événements de synchronisation : à chaque hydratation ou
  // écriture, React re-rend le provider et relit la liste des magasins.
  const dataVersion = useSyncExternalStore(onSyncStatus, syncVersion, syncVersion);
  const [revision, setRevision] = useState(0);

  // `revision` force le recalcul après une action locale (sélection, création).
  const stores = useMemo(() => listStores(true), [dataVersion, revision]);
  const activeId = useMemo(() => getActiveStoreId(), [dataVersion, revision]);

  const refreshStores = useCallback(() => {
    setRevision((v) => v + 1);
  }, []);

  const selectStore = useCallback((id) => {
    setActiveStoreId(id);
    setRevision((v) => v + 1);
  }, []);

  const activeStore = (stores || []).find((s) => s.id === activeId) || getActiveStore();

  return (
    <StoreContext.Provider
      value={{
        stores,
        activeId,
        activeStore,
        refreshStores,
        selectStore,
        createStore,
        updateStore,
        deleteStore,
        toggleStoreActive,
      }}
    >
      {children}
    </StoreContext.Provider>
  );
}

export function useStores() {
  const ctx = useContext(StoreContext);
  if (!ctx) {
    throw new Error('useStores doit être utilisé dans un StoreProvider.');
  }
  return ctx;
}