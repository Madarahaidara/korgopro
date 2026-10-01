// ============================================================================
// Diagnostic système (mobile). Miroir de web/src/api/systemApi.js.
// ============================================================================
import { config, isConfigured } from '../config';
import { mobileContext } from './rpc';
import { getRequestCount, ping } from './supabase';

export const BOOT_TIME = Date.now();

export function getHostInfo() {
  return 'mobile-app (React Native / Expo)';
}

export function getBrowserInfo() {
  return 'React Native (Expo Go / APK)';
}

export function getUptime() {
  return Date.now() - BOOT_TIME;
}

export function getBootTimeISO() {
  return new Date(BOOT_TIME).toISOString();
}

/**
 * Contexte vu par le serveur (RPC `app_mobile_context`) : rôle réel et
 * permissions réellement accordées. Ré-exporté ici pour que les écrans lisent
 * le diagnostic via la couche api/* sans jamais importer le transport (rpc.js).
 */
export { mobileContext };

/** Santé Supabase : ping PostgREST + contexte serveur (rôle/permissions). */
export async function checkHealth() {
  if (!isConfigured()) {
    return {
      status: 'LOCAL',
      latency: 0,
      served_by: 'config-manquante (mobile/.env)',
      message: 'Supabase non configuré : renseignez mobile/.env.',
      mode: 'local',
    };
  }
  const start = Date.now();
  const result = await ping();
  let context = null;
  try {
    context = await mobileContext();
  } catch (e) {
    context = { error: e.message };
  }
  return {
    status: result.ok ? 'UP' : 'DOWN',
    latency: result.latency ?? Date.now() - start,
    served_by: `Supabase · ${config.supabaseUrl}`,
    message: result.message,
    mode: 'supabase',
    requests: getRequestCount(),
    context,
  };
}

export const simulateHealthCheck = checkHealth;

export function isRemoteMode() {
  return isConfigured();
}
