// ============================================================================
// Session unique : un SEUL appareil connecte par compte Korgo Pro.
//
// La regle vit dans la base (`supabase_single_session.sql`) ; ce module en est
// le client : il ouvre la session a la connexion, envoie un battement de
// coeur toutes les 60 s et libere le verrou a la deconnexion.
//
// Contrat des reponses (jsonb) :
//   * `{ok:true, tracked:true, ...}`   -> session ouverte de ce compte ;
//   * `{ok:false, code:'SESSION_ACTIVE', message, other:{...}, can_force:true}`
//                                     -> un autre appareil est deja connecte ;
//   * `{ok:true, active:false, code:'SESSION_ACTIVE'|'SESSION_CLOSED'}` (battement)
//                                     -> notre session a ete reprise : il faut
//                                        se deconnecter.
//
// ROBUSTESSE : si les RPC ne sont pas installees en base, ou si le reseau
// echoue, on NE DECONNECTE JAMAIS l'utilisateur et on ne bloque pas la
// connexion (fail-open) : le verrou est une protection, pas une panne.
// ============================================================================
import { supabase } from './supabase';

export const PLATFORM = 'web';

/** Battement de coeur : 60 s (le serveur considere la session morte a 15 min). */
export const HEARTBEAT_MS = 60000;

let warnedUnavailable = false;

/** Refus « compte deja connecte ailleurs » (message + appareil concurrent). */
export class SessionConflictError extends Error {
  constructor(payload) {
    super(payload?.message || 'Ce compte est déjà connecté sur un autre appareil.');
    this.name = 'SessionConflictError';
    this.code = payload?.code || 'SESSION_ACTIVE';
    this.other = payload?.other || null;
  }
}

/** Nom lisible de l'appareil : navigateur + systeme. */
export function deviceLabel() {
  if (typeof navigator === 'undefined') return 'Navigateur';
  const ua = navigator.userAgent || '';
  const os = /Windows/i.test(ua) ? 'Windows'
    : /Android/i.test(ua) ? 'Android'
    : /iPhone|iPad|iPod/i.test(ua) ? 'iPhone/iPad'
    : /Mac OS X/i.test(ua) ? 'macOS'
    : /Linux/i.test(ua) ? 'Linux'
    : 'Navigateur';
  const browser = /Edg\//i.test(ua) ? 'Edge'
    : /OPR\//i.test(ua) ? 'Opera'
    : /Firefox\//i.test(ua) ? 'Firefox'
    : /Chrome\//i.test(ua) ? 'Chrome'
    : /Safari\//i.test(ua) ? 'Safari'
    : 'Navigateur';
  return `${browser} · ${os}`;
}

/** Une seule fois : evite de remplir la console a chaque echec reseau. */
function warnUnavailable(error) {
  if (warnedUnavailable) return;
  warnedUnavailable = true;
  // eslint-disable-next-line no-console
  console.warn(
    '[session] verrou multi-appareils indisponible :', error?.message || error
  );
}

/** Appel RPC tolérant : un échec reseau / RPC absente ne casse rien. */
async function call(name, params) {
  if (!supabase) return null;
  const { data, error } = await supabase.rpc(name, params);
  if (error) {
    warnUnavailable(error);
    return null;
  }
  return data;
}

/**
 * Ouvre la session de l'utilisateur connecté.
 * Lève `SessionConflictError` si un autre appareil détient déjà le compte.
 */
export async function registerSession({ force = false } = {}) {
  const res = await call('app_register_session', {
    p_platform: PLATFORM,
    p_device: deviceLabel(),
    p_force: !!force,
  });
  if (!res) return { ok: true, tracked: false, unavailable: true };
  if (res.ok === false && res.code === 'SESSION_ACTIVE') {
    throw new SessionConflictError(res);
  }
  return res;
}

/**
 * Battement de coeur : `active === false` signifie que la session a été reprise
 * par un autre appareil et que l'application doit se déconnecter.
 */
export async function heartbeatSession() {
  const res = await call('app_session_heartbeat', {
    p_platform: PLATFORM,
    p_device: deviceLabel(),
  });
  // Indisponible / réseau coupé : on ne déconnecte personne.
  return res || { ok: true, active: true, unavailable: true };
}

/** Déconnexion : libère immédiatement le verrou (au mieux). */
export async function endSession() {
  if (!supabase) return null;
  try {
    const { data, error } = await supabase.rpc('app_end_session', {});
    if (error) warnUnavailable(error);
    return data || null;
  } catch (error) {
    warnUnavailable(error);
    return null;
  }
}

/** État de la session (écran Compte / diagnostic). */
export async function sessionStatus() {
  return call('app_session_status', {});
}

/** Message court décrivant l'appareil qui bloque la connexion. */
export function describeOtherSession(other) {
  if (!other) return 'un autre appareil';
  const since = Number(other.since_minutes || 0);
  const idle = Number(other.idle_minutes || 0);
  const parts = [other.platform_label || 'un autre appareil'];
  if (other.device) parts.push(other.device);
  const detail = since < 1
    ? 'à l’instant'
    : `depuis ${since} min (dernière activité il y a ${idle} min)`;
  return `${parts.join(' · ')} — ${detail}`;
}
