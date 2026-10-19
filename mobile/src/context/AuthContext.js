// ============================================================================
// Contexte d'authentification (mobile) — miroir de web/src/context/AuthContext.
//
// API alignée sur le web : { user, settings, restoring, loginUser, logout,
// can, isAdmin, refreshUser } + extras mobile { role, roleLabel, permissions,
// signIn, signOut, error, clearError }.
// Permissions : matrice canonique core/permissions.py (19 clés) + pont
// `canModule()` vers le vocabulaire module du web (dashboard/sales/...).
// ============================================================================
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { AppState } from 'react-native';
import * as authApi from '../api/authApi';
import {
  clearRemoteSettingsCache,
  getSettings as loadSettings,
  hydrateSettings,
} from '../api/settingsApi';
import { HEARTBEAT_MS, heartbeatSession } from '../api/sessionApi';
import { can as canPermission, permissionsOf, roleLabel } from '../lib/permissions';

const AuthContext = createContext(null);

/**
 * Message affiché après une fermeture de session imposée : le compte a été
 * repris sur un autre appareil (verrou « une seule session par compte »).
 */
const TAKEN_OVER_MESSAGE =
  'Votre session a été fermée : ce compte est utilisé sur un autre appareil.';

/** Pont vocabulaire fin (mobile) -> modules (web Layout/NAV). */
const MODULE_TO_FINE = {
  dashboard: ['view_dashboard'],
  sales: ['view_sales', 'create_sales'],
  stock: ['view_stock'],
  treasury: ['view_treasury'],
  proformas: ['manage_proformas'],
  invoices: ['view_invoice_register'],
  customers: ['manage_customers'],
  admin: ['access_admin'],
  settings: ['manage_settings'],
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [settings, setSettings] = useState(() => loadSettings());
  const [restoring, setRestoring] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const profile = await authApi.restoreSession();
        if (!cancelled) setUser(profile);
        // Paramètres entreprise partagés (table app_settings) : aller-retour
        // best-effort — le rendu initial affiche déjà les valeurs de repli.
        await hydrateSettings();
        if (!cancelled) setSettings(loadSettings());
      } catch (e) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setRestoring(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const loginUser = useCallback(async (identifiant, password, options = {}) => {
    setError(null);
    setSettings(clearRemoteSettingsCache());
    const profile = await authApi.login(identifiant, password, options);
    setUser(profile);
    // Paramètres entreprise partagés (table app_settings) : le distant fait
    // référence, il écrase les valeurs de repli ; best-effort comme le web.
    await hydrateSettings();
    setSettings(loadSettings());
    return profile;
  }, []);

  // Session unique : un battement de coeur toutes les 60 s. Si le serveur répond
  // `active: false`, c'est qu'un autre appareil a repris le compte -> on ferme
  // la session ici. Réseau coupé ou RPC absentes : fail-open, on ne ferme rien.
  useEffect(() => {
    if (!user) return undefined;
    let stopped = false;
    let timer = null;

    const closeIfTakenOver = async () => {
      if (stopped) return;
      try {
        const res = await heartbeatSession();
        if (!stopped && res && res.active === false) {
          setError(res.message || TAKEN_OVER_MESSAGE);
          setUser(null);
          setSettings(clearRemoteSettingsCache());
          await authApi.logout().catch(() => {});
        }
      } catch (e) {
        /* fail-open : une erreur réseau ne ferme pas la session */
      }
    };

    const schedule = () => {
      timer = setTimeout(async () => {
        await closeIfTakenOver();
        if (!stopped) schedule();
      }, HEARTBEAT_MS);
    };

    closeIfTakenOver();
    schedule();

    // Retour au premier plan (l'app Android était en arrière-plan : plus de
    // battement) -> on vérifie immédiatement si la session tient encore.
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') closeIfTakenOver();
    });

    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      if (subscription?.remove) subscription.remove();
    };
  }, [user]);

  // Paramètres entreprise partagés : re-hydratation périodique (même cadence
  // que le heartbeat) + au retour au premier plan. Sans ça, un changement
  // effectué depuis desktop/web n'apparaît sur le mobile qu'au prochain
  // redémarrage de l'app (hydrateSettings() n'était appelé qu'au login et à la
  // restauration de session). Best-effort : un échec réseau/RLS laisse les
  // valeurs en cache intactes (fetchRemoteSettings() retourne null).
  useEffect(() => {
    if (!user) return undefined;
    let stopped = false;

    const refresh = async () => {
      if (stopped) return;
      // Ne lève jamais (best-effort) : valeurs repli + console.warn côté remote.
      const fresh = await hydrateSettings();
      if (stopped) return;
      // Seul un vrai changement déclenche un re-rendu (même référence sinon).
      setSettings((prev) => (
        JSON.stringify(prev) === JSON.stringify(fresh) ? prev : fresh
      ));
    };

    const timer = setInterval(refresh, HEARTBEAT_MS);
    // Retour au premier plan (app Android revenue d'arriere-plan) : on
    // re-recupere les parametres aussitot, comme pour le verrou de session.
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') refresh();
    });

    return () => {
      stopped = true;
      clearInterval(timer);
      if (subscription?.remove) subscription.remove();
    };
  }, [user]);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      setUser(null);
      setSettings(clearRemoteSettingsCache());
    }
  }, []);

  const value = useMemo(() => {
    const role = user?.role || null;
    const fine = permissionsOf(role);
    const can = (permission) => {
      if (!user) return false;
      if (MODULE_TO_FINE[permission]) {
        return MODULE_TO_FINE[permission].some((p) => fine.includes(p));
      }
      return canPermission(user.role, permission);
    };
    return {
      user,
      settings,
      restoring,
      loginUser,
      logout,
      can,
      isAdmin: () => !!user && String(user.role || '').toUpperCase() === 'ADMIN',
      refreshUser: () => {},
      role,
      roleLabel: role ? roleLabel(role) : '',
      permissions: fine,
      canModule: (module) => can(module),
      error,
      clearError: () => setError(null),
      signIn: loginUser,
      signOut: logout,
    };
  }, [user, settings, restoring, error, loginUser, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth doit être utilisé dans un AuthProvider.');
  return ctx;
}
