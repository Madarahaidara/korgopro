// ============================================================================
// Contexte d'authentification.
// Gère la session de l'utilisateur courant et les permissions par rôle.
// ============================================================================
import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { login, getUserById } from '../api/authApi';
import { getSettings } from '../api/settingsApi';
import { supabase } from '../api/supabase';
import { db, hydrate } from '../api/db';
import {
  HEARTBEAT_MS,
  endSession,
  heartbeatSession,
  registerSession,
} from '../api/sessionApi';

const AuthContext = createContext(null);
const SESSION_KEY = 'korgo_pro_session';
// Message « session reprise ailleurs » : survit au rechargement de la page.
const NOTICE_KEY = 'korgo_pro_session_notice';

const ROLE_PERMISSIONS = {
  ADMIN: ['dashboard', 'sales', 'stock', 'treasury', 'proformas', 'invoices', 'customers', 'admin', 'settings'],
  GESTIONNAIRE: ['dashboard', 'sales', 'stock', 'treasury', 'proformas', 'invoices', 'customers'],
  SUPERVISEUR: ['dashboard', 'sales', 'stock', 'treasury', 'proformas', 'invoices', 'customers'],
  ASSISTANT: ['dashboard', 'sales', 'stock'],
  CAISSIER: ['dashboard', 'sales', 'stock'],
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    if (supabase) return null;
    try {
      const raw = sessionStorage.getItem(SESSION_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  });
  const [settings, setSettings] = useState(() => getSettings());
  // En mode Supabase, la session est persistée dans localStorage par le SDK :
  // au démarrage on doit la restaurer avant d'afficher Login (évite le flash).
  const [restoring, setRestoring] = useState(() => !!supabase);
  // Message affiché sur l'écran de connexion après une fermeture de session
  // imposée (« ce compte est utilisé ailleurs »).
  const [sessionNotice, setSessionNotice] = useState(() => {
    try {
      return sessionStorage.getItem(NOTICE_KEY) || null;
    } catch (e) {
      return null;
    }
  });

  /** Ferme la session en conservant la raison (affichée sur l'écran Login). */
  const closeForConflict = useCallback(async (conflict) => {
    const message = conflict?.message
      || 'Votre session a été fermée : ce compte est utilisé sur un autre appareil.';
    try {
      sessionStorage.setItem(NOTICE_KEY, message);
    } catch (e) {
      /* stockage indisponible : le message reste affiché en mémoire */
    }
    setSessionNotice(message);
    setUser(null);
    db.clearRemote();
    if (supabase) {
      await supabase.auth.signOut({ scope: 'local' }).catch(() => {});
    }
  }, []);

  const clearSessionNotice = useCallback(() => {
    try {
      sessionStorage.removeItem(NOTICE_KEY);
    } catch (e) {
      /* rien à faire */
    }
    setSessionNotice(null);
  }, []);

  useEffect(() => {
    if (user) {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(user));
    } else {
      sessionStorage.removeItem(SESSION_KEY);
    }
  }, [user]);

  // Restauration de session au refresh : token Supabase présent dans
  // localStorage -> on recharge le profil actif puis les données distantes.
  useEffect(() => {
    if (!supabase) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const { data } = await supabase.auth.getSession();
        const email = data?.session?.user?.email;
        if (!email) return;
        const profile = await supabase.from('users')
          .select('id,username,email,role,active,must_change_password,last_login')
          .eq('email', email).eq('active', true).maybeSingle();
        if (profile.error || !profile.data) {
          throw new Error('Profil actif inaccessible.');
        }
        // Session unique : la session restaurée a-t-elle encore le droit
        // d'ouvrir l'application ? (l'utilisateur a pu se connecter ailleurs
        // pendant son absence, ou depuis un autre poste).
        try {
          await registerSession();
        } catch (conflict) {
          if (conflict?.code === 'SESSION_ACTIVE') {
            if (!cancelled) await closeForConflict(conflict);
            return;
          }
          throw conflict;
        }
        if (cancelled) return;
        setUser(profile.data);
        setSettings(getSettings());
        const result = await hydrate();
        if (!result.ok) {
          await supabase.auth.signOut({ scope: 'local' });
          if (!cancelled) setUser(null);
        }
      } catch (e) {
        await supabase.auth.signOut({ scope: 'local' }).catch(() => {});
        if (!cancelled) setUser(null);
      } finally {
        if (!cancelled) setRestoring(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const loginUser = async (username, password, options = {}) => {
    const authenticated = await login(username, password, options);
    if (authenticated && supabase) {
      const result = await hydrate();
      if (!result.ok) {
        await supabase.auth.signOut({ scope: 'local' });
        throw new Error(result.message);
      }
    }
    if (authenticated) {
      clearSessionNotice();
      setUser(authenticated);
      setSettings(getSettings());
      return authenticated;
    }
    return null;
  };

  // Session unique : un battement de coeur toutes les 60 s. Si le serveur
  // répond `active: false`, c'est qu'un autre appareil a repris le compte ->
  // on ferme la session ici. Un réseau coupé ne déconnecte personne.
  useEffect(() => {
    if (!user || !supabase) return undefined;
    let stopped = false;
    let timer = null;

    const beat = async () => {
      if (stopped || typeof document === 'undefined' || document.hidden) return;
      try {
        const res = await heartbeatSession();
        if (!stopped && res && res.active === false) {
          await closeForConflict(res);
        }
      } catch (e) {
        /* fail-open : une erreur réseau ne ferme pas la session */
      }
    };

    const schedule = () => {
      timer = setTimeout(async () => {
        await beat();
        if (!stopped) schedule();
      }, HEARTBEAT_MS);
    };

    beat();
    schedule();

    // Onglet remis au premier plan / retour du réseau : on vérifie aussitôt.
    const onVisible = () => { if (!document.hidden) beat(); };
    const onOnline = () => beat();
    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('online', onOnline);
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('online', onOnline);
    };
  }, [user, closeForConflict]);

  const logout = async () => {
    setUser(null);
    if (supabase) {
      db.clearRemote();
      // Libère le verrou : un autre poste pourra se connecter sans attendre.
      await endSession().catch(() => {});
      const { error } = await supabase.auth.signOut({ scope: 'local' });
      if (error) throw error;
    }
  };

  const refreshUser = () => {
    if (user) {
      const fresh = getUserById(user.id);
      if (fresh) setUser(fresh);
    }
  };

  const can = (permission) => {
    if (!user) return false;
    const perms = ROLE_PERMISSIONS[user.role] || [];
    return perms.includes(permission);
  };

  const isAdmin = () => user && user.role === 'ADMIN';

  return (
    <AuthContext.Provider
      value={{
        user,
        settings,
        restoring,
        loginUser,
        logout,
        can,
        isAdmin,
        refreshUser,
        // Session unique : message affiché sur l'écran de connexion quand la
        // session a été fermée parce que le compte a été repris ailleurs.
        sessionNotice,
        clearSessionNotice,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth doit être utilisé dans un AuthProvider.');
  }
  return ctx;
}