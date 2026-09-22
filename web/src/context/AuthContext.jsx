// ============================================================================
// Contexte d'authentification.
// Gère la session de l'utilisateur courant et les permissions par rôle.
// ============================================================================
import { createContext, useContext, useEffect, useState } from 'react';
import { login, getUserById } from '../api/authApi';
import { getSettings } from '../api/settingsApi';
import { supabase } from '../api/supabase';
import { db, hydrate } from '../api/db';

const AuthContext = createContext(null);
const SESSION_KEY = 'korgo_pro_session';

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

  const loginUser = async (username, password) => {
    const authenticated = await login(username, password);
    if (authenticated && supabase) {
      const result = await hydrate();
      if (!result.ok) {
        await supabase.auth.signOut({ scope: 'local' });
        throw new Error(result.message);
      }
    }
    if (authenticated) {
      setUser(authenticated);
      setSettings(getSettings());
      return authenticated;
    }
    return null;
  };

  const logout = async () => {
    setUser(null);
    if (supabase) {
      db.clearRemote();
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
      value={{ user, settings, restoring, loginUser, logout, can, isAdmin, refreshUser }}
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