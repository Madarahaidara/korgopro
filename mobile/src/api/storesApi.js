// ============================================================================
// Magasins (mobile). Miroir de web/src/api/storesApi.js.
// Lecture Supabase directe (user_read_stores) ; persistance du magasin actif
// dans AsyncStorage (équivalent localStorage web).
// ============================================================================
import AsyncStorage from '@react-native-async-storage/async-storage';
import { listStores as listStoresRaw } from './dataApi';

export const ACTIVE_STORE_KEY = 'korgo_pro_mobile_active_store';

/** Tous les magasins triés par code. */
export async function listStores(includeInactive = false) {
  const rows = await listStoresRaw(true);
  return rows
    .filter((s) => includeInactive || s.active !== false)
    .slice()
    .sort((a, b) => String(a.code || '').localeCompare(String(b.code || '')));
}

export async function getActiveStoreId() {
  const stores = await listStores(true).catch(() => []);
  const stored = Number(await AsyncStorage.getItem(ACTIVE_STORE_KEY).catch(() => null));
  if (stores.some((s) => s.id === stored)) return stored;
  return stores[0]?.id ?? null;
}

export async function setActiveStoreId(id) {
  if (id == null) {
    await AsyncStorage.removeItem(ACTIVE_STORE_KEY).catch(() => {});
  } else {
    await AsyncStorage.setItem(ACTIVE_STORE_KEY, String(Number(id))).catch(() => {});
  }
}

export async function getActiveStore() {
  const id = await getActiveStoreId();
  const stores = await listStores(true).catch(() => []);
  return stores.find((s) => s.id === id) || null;
}

function blocked(label) {
  throw new Error(`${label} : réservé admin (RLS). Créez/modifiez les magasins depuis desktop/web.`);
}

export async function createStore() { blocked('createStore'); }
export async function updateStore() { blocked('updateStore'); }
export async function deleteStore() { blocked('deleteStore'); }
export async function toggleStoreActive() { blocked('toggleStoreActive'); }

export async function getStoreSummary(storeId) {
  return { storeId: Number(storeId), productCount: null, stockValue: null, lowStock: null };
}
