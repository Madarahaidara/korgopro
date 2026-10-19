// ============================================================================
// Service des paramètres entreprise.
// Reprend l'utilitaire settings_manager.py de la version desktop.
//
// Source de vérité partagée : la table Supabase `app_settings` (voir
// settingsRemote.js), avec repli localStorage. `getSettings()` reste synchrone
// (lecture du cache mémoire) pour ne pas changer les composants ; la synchro
// distante se fait à l'hydratation (`hydrateSettings`) et à la sauvegarde.
// ============================================================================
import { db } from './db';
import { fetchRemoteSettings, pushRemoteSettings } from './settingsRemote';

/** Retourne les paramètres d'entreprise (cache mémoire synchrone). */
export function getSettings() {
  return { ...db.data.settings };
}

/**
 * Met à jour les paramètres d'entreprise : cache mémoire d'abord (réactivité),
 * puis poussée vers Supabase en arrière-plan (best-effort, non bloquante).
 */
export function saveSettings(patch) {
  db.data.settings = { ...db.data.settings, ...patch };
  db.persist(); // cache hors-ligne (localStorage)
  // Écriture distante : fire-and-forget, le merge serveur préserve les clés
  // de l'autre plateforme. Un échec n'affiché pas d'erreur bloquante ici ;
  // le bandeau de synchro Supabase remonte les problèmes de table/RLS.
  pushRemoteSettings(db.data.settings).catch(() => {});
  return getSettings();
}

/**
 * Charge les paramètres distants (Supabase) et les fusionne dans le cache.
 * À appeler au login, juste après `hydrate()`. En mode local, ne fait rien.
 */
export async function hydrateSettings() {
  const remote = await fetchRemoteSettings();
  if (remote && Object.keys(remote).length) {
    // Le distant fait référence : il écrase le cache local pour ces clés.
    db.data.settings = { ...db.data.settings, ...remote };
    db.persist();
  }
  return getSettings();
}

/** Informations utiles pour une facture (IFU, RCCM, etc.). */
export function getBillingInfo() {
  const s = db.data.settings;
  return {
    ...s,
    ifu: s.ifu || '',
    rccm: s.rccm || '',
    bp: s.bp || '',
  };
}

/** Journal d'activité (audit trail). */
export function listActivityLogs(limit = 50) {
  const logs = db.data.activityLogs || [];
  return logs.slice().reverse().slice(0, limit);
}

/** Ajoute un log d'activité. */
export function logActivity(user, action) {
  db.data.activityLogs = db.data.activityLogs || [];
  db.data.activityLogs.push({
    id: Math.max(0, ...db.data.activityLogs.map((l) => l.id)) + 1,
    user: user ? user.username : 'system',
    action,
    timestamp: new Date().toISOString(),
  });
  db.persist();
}