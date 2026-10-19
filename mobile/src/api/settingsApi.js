// ============================================================================
// Paramètres entreprise (mobile). Miroir de web/src/api/settingsApi.js.
//
// Lecture seule : les valeurs modifiables le sont depuis desktop/web.
// Source de vérité partagée : la table Supabase `app_settings` (voir
// settingsRemote.js). `getSettings()` reste SYNCHRONE (cache mémoire) pour
// ne pas changer les composants ; l'aller-retour réseau se fait au login, à la
// restauration de session, puis en continu (toutes les 60 s) et au retour au
// premier plan via `hydrateSettings()` (AuthContext) — sans ce rafraîchissement,
// un changement fait depuis desktop/web n'apparaît qu'au redémarrage de l'app.
//
// Repli : sans Supabase (mobile/.env absent) ou si la table est injoignable,
// les valeurs viennent de mobile/.env (devise/TVA) + défauts, comme avant.
// ============================================================================
import { config, isConfigured } from '../config';
import { fetchRemoteSettings, pushRemoteSettings } from './settingsRemote';

const DEFAULTS = {
  company_name: 'Korgo Pro',
  currency: 'FCFA',
  tax_rate: 0,
  invoice_prefix: 'FAC',
  proforma_prefix: 'PRO',
  invoice_footer: 'Merci de votre confiance.',
};

/**
 * Dictionnaire distant façonné (settingsRemote.canonicalToMobile). `null`
 * tant que hydrateSettings() n'a pas abouti : les défauts/env servent
 * pendant ce laps (affichage immédiat au démarrage de l'app).
 */
let remoteCache = null;

/** Valeurs de repli : défauts puis env (devise/TVA caisse). */
function fallbackSettings() {
  return {
    ...DEFAULTS,
    currency: config.currency || DEFAULTS.currency,
    tax_rate: Number(config.taxRate) || 0,
  };
}

/** Paramètres effectifs (cache distant s'il existe, sinon env + défauts). */
export function getSettings() {
  return { ...fallbackSettings(), ...(remoteCache || {}) };
}

/** Oublie les paramètres reçus pendant la session précédente. */
export function clearRemoteSettingsCache() {
  remoteCache = null;
  return getSettings();
}

/**
 * Charge les paramètres distants (Supabase) — miroir de hydrateSettings()
 * du web. À appeler au login et à la restauration de session ; best-effort :
 * un échec réseau/RLS laisse les valeurs précédentes et ne lève rien.
 */
export async function hydrateSettings() {
  if (!isConfigured()) return getSettings();
  const remote = await fetchRemoteSettings();
  if (remote && Object.keys(remote).length) {
    // Préserve les clés distantes précédemment chargées si la réponse est partielle.
    remoteCache = { ...(remoteCache || {}), ...remote };
  }
  return getSettings();
}

export async function saveSettings(patch) {
  const remote = await pushRemoteSettings(patch);
  if (remote && typeof remote === 'object') {
    const refreshed = await fetchRemoteSettings();
    if (refreshed) remoteCache = { ...(remoteCache || {}), ...refreshed };
  }
  return getSettings();
  throw new Error('saveSettings : paramètres modifiables depuis desktop/web uniquement.');
}

export function getBillingInfo() {
  const s = getSettings();
  return { ...s, ifu: s.ifu || '', rccm: s.rccm || '', bp: s.bp || '' };
}

export async function listActivityLogs() {
  return [];
}

export async function logActivity() {
  // No-op mobile : journal réservé admin (RLS).
}
