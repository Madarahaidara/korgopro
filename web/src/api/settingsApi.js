// ============================================================================
// Service des paramètres entreprise.
// Reprend l'utilitaire settings_manager.py de la version desktop.
// ============================================================================
import { db } from './db';

/** Retourne les paramètres d'entreprise. */
export function getSettings() {
  return { ...db.data.settings };
}

/** Met à jour les paramètres d'entreprise. */
export function saveSettings(patch) {
  db.data.settings = { ...db.data.settings, ...patch };
  db.persist();
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