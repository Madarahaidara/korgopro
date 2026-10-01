// ============================================================================
// Contexte multi-magasins (mobile) — miroir de web/src/context/StoreContext.
//
// API alignée sur le web : { stores, activeId, activeStore, refreshStores,
// selectStore, createStore, updateStore, deleteStore, toggleStoreActive }.
// Lecture via storesApi (Supabase) ; écritures réservées admin (stubs).
// ============================================================================
import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { listStores as listStoresApi } from '../api/storesApi';
import { useAuth } from './AuthContext';

const StoreContext = createContext(null);
const ACTIVE_STORE_KEY = 'korgo_pro_mobile_active_store';

export function StoreProvider({ children }) {
  const { user } = useAuth();
  const [stores, setStores] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Chargement des magasins : à la connexion (et non avant, car RLS interdit
  // toute lecture au rôle anonyme).
  useEffect(() => {
    if (!user) {
      setStores([]);
      setActiveId(null);
      return undefined;
    }
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const rows = await listStoresApi(true);
        if (cancelled) return;
        setStores(rows);
        const stored = Number(await AsyncStorage.getItem(ACTIVE_STORE_KEY));
        const valid = rows.some((s) => s.id === stored);
        const nextId = valid ? stored : rows[0]?.id ?? null;
        setActiveId(nextId);
      } catch (e) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user]);

  const selectStore = useCallback((id) => {
    const value = id == null ? null : Number(id);
    setActiveId(value);
    if (value == null) {
      AsyncStorage.removeItem(ACTIVE_STORE_KEY).catch(() => {});
    } else {
      AsyncStorage.setItem(ACTIVE_STORE_KEY, String(value)).catch(() => {});
    }
  }, []);

  const refreshStores = useCallback(async () => {
    try {
      const rows = await listStoresApi(true);
      setStores(rows);
      return rows;
    } catch (e) {
      setError(e.message);
      return [];
    }
  }, []);

  const blocked = useCallback(async (label) => {
    throw new Error(`${label} : réservé admin (RLS). Utilisez desktop/web.`);
  }, []);

  const value = useMemo(
    () => ({
      stores,
      activeId,
      activeStore: stores.find((s) => s.id === activeId) || null,
      loading,
      error,
      selectStore,
      refreshStores,
      createStore: () => blocked('createStore'),
      updateStore: () => blocked('updateStore'),
      deleteStore: () => blocked('deleteStore'),
      toggleStoreActive: () => blocked('toggleStoreActive'),
    }),
    [stores, activeId, loading, error, selectStore, refreshStores, blocked]
  );

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStores() {
  const ctx = useContext(StoreContext);
  if (!ctx) throw new Error('useStores doit être utilisé dans un StoreProvider.');
  return ctx;
}

