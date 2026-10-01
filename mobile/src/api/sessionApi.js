// ============================================================================
// Session unique : un SEUL appareil connecte par compte Korgo Pro.
//
// Miroir de web/src/api/sessionApi.js (meme SQL : supabase_single_session.sql).
// L'identite et l'identifiant de session sont lus par le serveur dans le JWT
// (`session_id`) : le client n'envoie rien de sensible.
//
//   * a la connexion  -> `app_register_session` (refuse si un autre appareil est
//     deja connecte ; `force: true` reprend la main) ;
//   * toutes les 60 s -> `app_session_heartbeat` (battement de coeur ; si la
//     session a ete reprise ailleurs, `active: false` = deconnexion) ;
//   * a la sortie      -> `app_end_session` (liberation immediate du verrou).
//
// ROBUSTESSE : reseau coupe ou RPC non installees en base -> fail-open, on ne
// bloque jamais la connexion et on ne deconnecte jamais l'utilisateur.
// ============================================================================
import { Platform } from 'react-native';
import { supabase } from './supabase';

export const PLATFORM = 'mobile';

/** Battement de coeur : 60 s (le serveur expire une session a 15 min). */
export const HEARTBEAT_MS = 60000;

let warnedUnavailable = false;

/** Refus « compte deja connecte ailleurs » (message + appareil concurrent). */
export class SessionConflictError extends Error {
  constructor(payload) {
    super(payload?.message || "Ce compte est d\u00e9j\u00e0 connect\u00e9 sur un autre appareil.");
    this.name = 'SessionConflictError';
    this.code = payload?.code || 'SESSION_ACTIVE';
    this.other = payload?.other || null;
  }
}

/** Nom lisible de l'appareil : systeme + version d'Android / iOS. */
export function deviceLabel() {
  const os = Platform.OS === 'android'
    ? 'Android'
    : Platform.OS === 'ios' ? 'iOS' : (Platform.OS || 'appareil');
  const version = Platform.Version ? ` ${Platform.Version}` : '';
  return `${os}${version}`.trim();
}

/** Une seule fois : evite de remplir la console a chaque echec reseau. */
function warnUnavailable(error) {
  if (warnedUnavailable) return;
  warnedUnavailable = true;
  console.warn('[session] verrou multi-appareils indisponible :', error?.message || error);
}

/** Appel RPC tolerant : un echec reseau / RPC absente ne casse rien. */
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
 * Ouvre la session de l'utilisateur connecte.
 * Leve `SessionConflictError` si un autre appareil detient deja le compte.
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
 * Battement de coeur : `active === false` signifie que la session a ete reprise
 * ailleurs -> l'application doit se deconnecter.
 */
export async function heartbeatSession() {
  const res = await call('app_session_heartbeat', {
    p_platform: PLATFORM,
    p_device: deviceLabel(),
  });
  return res || { ok: true, active: true, unavailable: true };
}

/** Deconnexion : libere immediatement le verrou (au mieux). */
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

/** Etat de la session (ecran Compte / diagnostic). */
export async function sessionStatus() {
  return call('app_session_status', {});
}

/** Message court decrivant l'appareil qui bloque la connexion. */
export function describeOtherSession(other) {
  if (!other) return 'un autre appareil';
  const since = Number(other.since_minutes || 0);
  const idle = Number(other.idle_minutes || 0);
  const parts = [other.platform_label || 'un autre appareil'];
  if (other.device) parts.push(other.device);
  const detail = since < 1
    ? '\u00e0 l\u2019instant'
    : `depuis ${since} min (derniere activite il y a ${idle} min)`;
  return `${parts.join(' \u00b7 ')} \u2014 ${detail}`;
}
