// ============================================================================
// Contexte de gestion multi-magasins.
// Fournit la liste des magasins et le magasin actif à toute l'application.
// ============================================================================
import { createContext, useContext, useState, useCallback } from 'react';
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

export function StoreProvider({ children }) {
  const [stores, setStores] = useState(() => listStores(true));
  const [activeId, setActiveId] = useState(() => getActiveStoreId());

  const refreshStores = useCallback(() => {
    setStores(listStores(true));
  }, []);

  const selectStore = useCallback((id) => {
    setActiveStoreId(id);
    setActiveId(Number(id));
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