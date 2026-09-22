// ============================================================================
// Service d'état système (page Administration).
//
// Deux modes possibles pour l'application web :
//   - MODE SUPABASE : les données vivent dans la base PostgreSQL/Supabase
//     partagée avec l'application desktop ; le diagnostic interroge
//     réellement l'API PostgREST (latence, projet, rôle) ;
//   - MODE LOCAL : repli sur le localStorage du navigateur.
// ============================================================================
import {
  ping,
  isSupabaseConfigured,
  supabaseProjectRef,
  getRequestCount,
} from './supabase';

export const BOOT_TIME = Date.now(); // Date de chargement de l'application (session).

/** Nom de l'hôte / origine actuelle. */
export function getHostInfo() {
  let host = 'inconnu';
  try {
    host = window.location.host || navigator.userAgent;
  } catch (e) {
    /* ignore */
  }
  return host;
}

/** User-Agent (navigateur). */
export function getBrowserInfo() {
  return navigator.userAgent || 'inconnu';
}

/** Temps écoulé depuis le chargement de l'application. */
export function getUptime() {
  return Date.now() - BOOT_TIME;
}

/** Heure d'amorçage ISO. */
export function getBootTimeISO() {
  return new Date(BOOT_TIME).toISOString();
}

/**
 * Interroge réellement Supabase (latence + accessibilité) si configuré.
 * En mode local, retourne immédiatement un statut LOCAL.
 * Retourne { status, latency, served_by, message, mode }.
 */
export async function checkHealth() {
  if (!isSupabaseConfigured()) {
    return {
      status: 'LOCAL',
      latency: 0,
      served_by: 'frontend-local (localStorage)',
      message: 'Supabase non configuré : données dans le navigateur',
      mode: 'local',
    };
  }
  const start = performance.now();
  const result = await ping();
  return {
    status: result.ok ? 'UP' : 'DOWN',
    latency: result.latency || Math.round(performance.now() - start),
    served_by: `Supabase · ${supabaseProjectRef() || 'projet'}`,
    message: result.message,
    mode: 'supabase',
  };
}

/**
 * Conservé pour compatibilité : ancien nom de checkHealth().
 * @deprecated utiliser checkHealth()
 */
export const simulateHealthCheck = checkHealth;

/** Vrai si l'application lit/écrit la base Supabase. */
export function isRemoteMode() {
  return isSupabaseConfigured();
}

/** Nombre total d'appels réseau Supabase depuis le démarrage. */
export function networkRequests() {
  return getRequestCount();
}

/** Référence du projet Supabase configuré (vide en mode local). */
export function projectRef() {
  return supabaseProjectRef();
}

/** Nombre total d'enregistrements présents dans la base locale. */
export function countRecords(dbData) {
  const collections = [
    'users', 'customers', 'products', 'suppliers',
    'sales', 'proformas', 'treasuryAccounts', 'treasuryMovements',
    'expenses', 'inventoryMovements', 'activityLogs',
  ];
  return collections.reduce((sum, key) => {
    const arr = dbData[key];
    return sum + (Array.isArray(arr) ? arr.length : 0);
  }, 0);
}

/** Formate une durée (ms) en texte lisible. */
export function formatDuration(ms) {
  if (ms < 1000) return `${ms} ms`;
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  const rest = s % 60;
  if (m < 60) return `${m} min ${rest} s`;
  const h = Math.floor(m / 60);
  return `${h} h ${m % 60} min`;
}

/** Niveau d'utilisation estimé du quota localStorage (5 Mo en général). */
export function storageUsedPercent(bytes) {
  const quota = 5 * 1024 * 1024; // 5 Mo
  return Math.min(100, Math.round((bytes / quota) * 1000) / 10);
}

/** Liste les entrées non vides du cache (retourne des clés). */
export function listCacheKeys() {
  const keys = [];
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.startsWith('korgo_')) keys.push(k);
    }
  } catch (e) {
    /* ignore */
  }
  return keys;
}