import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { isSupabaseConfigured, supabase } from '../api/supabase';
import { listStores, loadBusinessContext } from '../api/businessApi';

const AuthContext = createContext(null);

function chooseOrganization(organizations) {
  const savedId = window.localStorage.getItem('korgo:selected-organization');
  return organizations.find((organization) => organization.id === savedId)?.id
    || organizations[0]?.id
    || null;
}

async function loadAuthenticatedContext() {
  const context = await loadBusinessContext();
  return {
    user: context.profile,
    organizations: context.organizations,
  };
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [organizations, setOrganizations] = useState([]);
  const [organizationId, setOrganizationId] = useState(null);
  const [stores, setStores] = useState([]);
  const [storeId, setStoreId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [contextLoading, setContextLoading] = useState(false);
  const [authError, setAuthError] = useState('');
  const [businessError, setBusinessError] = useState('');

  const applyContext = useCallback(({ user: profile, organizations: availableOrganizations }) => {
    const nextOrganizations = Array.isArray(availableOrganizations) ? availableOrganizations : [];
    setUser(profile);
    setOrganizations(nextOrganizations);
    setOrganizationId(chooseOrganization(nextOrganizations));
    setStoreId(null);
    setBusinessError('');
  }, []);

  useEffect(() => {
    if (!supabase) {
      setLoading(false);
      return undefined;
    }

    let cancelled = false;
    const restoreSession = async () => {
      try {
        const { data, error } = await supabase.auth.getSession();
        if (error) throw error;
        if (data.session?.user) {
          const context = await loadAuthenticatedContext();
          if (!cancelled) applyContext(context);
        }
      } catch (error) {
        console.error('Restauration de session Supabase impossible:', error);
        if (!cancelled) {
          setAuthError(error.message || 'Impossible de restaurer la session Supabase.');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    restoreSession();
    const { data } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'SIGNED_OUT' || !session) {
        setUser(null);
        setOrganizations([]);
        setOrganizationId(null);
        setStores([]);
        setStoreId(null);
      }
    });

    return () => {
      cancelled = true;
      data.subscription.unsubscribe();
    };
  }, [applyContext]);

  useEffect(() => {
    if (!user || !organizationId) {
      setStores([]);
      setStoreId(null);
      setContextLoading(false);
      return undefined;
    }
    const organizationPermissions = organizations.find((organization) => organization.id === organizationId)?.permissions || [];
    const needsStores = ['view_dashboard', 'create_sales', 'view_stock', 'manage_stock', 'manage_stores']
      .some((permission) => organizationPermissions.includes(permission));
    if (!needsStores) {
      setStores([]);
      setStoreId(null);
      setContextLoading(false);
      setBusinessError('');
      return undefined;
    }
    let cancelled = false;
    setContextLoading(true);
    setBusinessError('');
    listStores(organizationId)
      .then((availableStores) => {
        if (cancelled) return;
        setStores(availableStores);
        const savedStoreId = window.localStorage.getItem(`korgo:selected-store:${organizationId}`);
        const selectedStore = availableStores.find((store) => String(store.id) === savedStoreId)
          || availableStores.find((store) => store.is_default)
          || availableStores[0]
          || null;
        setStoreId(selectedStore?.id ?? null);
      })
      .catch((error) => {
        if (cancelled) return;
        setStores([]);
        setStoreId(null);
        setBusinessError(error.message || 'Impossible de charger les magasins.');
      })
      .finally(() => {
        if (!cancelled) setContextLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user, organizations, organizationId]);

  const selectOrganization = useCallback((id) => {
    if (!organizations.some((organization) => organization.id === id)) {
      throw new Error('Cette entreprise ne fait pas partie de votre accès.');
    }
    window.localStorage.setItem('korgo:selected-organization', id);
    setContextLoading(true);
    setOrganizationId(id);
    setStoreId(null);
  }, [organizations]);

  const selectStore = useCallback((id) => {
    const selectedStore = stores.find((store) => String(store.id) === String(id));
    if (!selectedStore) throw new Error('Ce magasin ne fait pas partie de l’entreprise sélectionnée.');
    window.localStorage.setItem(`korgo:selected-store:${organizationId}`, String(id));
    setStoreId(selectedStore.id);
  }, [organizationId, stores]);

  const refreshStores = useCallback(async () => {
    if (!organizationId) return [];
    setContextLoading(true);
    setBusinessError('');
    try {
      const availableStores = await listStores(organizationId);
      setStores(availableStores);
      const savedStoreId = window.localStorage.getItem(`korgo:selected-store:${organizationId}`);
      const selectedStore = availableStores.find((store) => String(store.id) === savedStoreId)
        || availableStores.find((store) => store.is_default)
        || availableStores[0]
        || null;
      setStoreId(selectedStore?.id ?? null);
      return availableStores;
    } catch (error) {
      setStores([]);
      setStoreId(null);
      setBusinessError(error.message || 'Impossible de charger les magasins.');
      throw error;
    } finally {
      setContextLoading(false);
    }
  }, [organizationId]);

  const login = useCallback(async (identifier, password) => {
    if (!supabase || !isSupabaseConfigured) {
      return { ok: false, message: 'Configuration Supabase absente. Renseignez web/.env.' };
    }

    setLoading(true);
    setAuthError('');
    try {
      const loginIdentifier = String(identifier || '').trim();
      if (loginIdentifier.includes('@')) {
        const { error } = await supabase.auth.signInWithPassword({
          email: loginIdentifier.toLowerCase(),
          password,
        });
        if (error) {
          const status = Number(error.status);
          return {
            ok: false,
            message: error.name === 'AuthApiError' && (status === 400 || status === 401)
              ? 'Connexion Supabase refusée. Vérifiez votre identifiant et votre mot de passe.'
              : 'Service Supabase injoignable. Vérifiez votre connexion internet.',
          };
        }
      } else {
        const { data, error } = await supabase.functions.invoke('login-with-identifier', {
          body: { identifier: loginIdentifier, password },
        });
        if (error) {
          const status = error.context instanceof Response ? error.context.status : null;
          if (status === 401) {
            return {
              ok: false,
              message: 'Connexion Supabase refusée. Vérifiez votre identifiant et votre mot de passe.',
            };
          }
          console.error('Fonction Supabase de connexion indisponible:', error);
          return {
            ok: false,
            message: 'Service Supabase de connexion indisponible. Vérifiez que la fonction de connexion est déployée.',
          };
        }
        if (!data?.access_token || !data?.refresh_token) {
          throw new Error('La fonction Supabase a renvoyé une session de connexion invalide.');
        }
        const { error: sessionError } = await supabase.auth.setSession({
          access_token: data.access_token,
          refresh_token: data.refresh_token,
        });
        if (sessionError) throw sessionError;
      }

      const context = await loadAuthenticatedContext();
      applyContext(context);
      return { ok: true, user: context.user };
    } catch (error) {
      console.error('Connexion Supabase impossible:', error);
      const { error: signOutError } = await supabase.auth.signOut({ scope: 'local' });
      if (signOutError) {
        console.error('Fermeture de la session Supabase impossible:', signOutError);
      }
      setUser(null);
      setOrganizations([]);
      setOrganizationId(null);
      setStoreId(null);
      return {
        ok: false,
        message: error.message || 'Impossible de vérifier le profil Supabase.',
      };
    } finally {
      setLoading(false);
    }
  }, [applyContext]);

  const logout = useCallback(async () => {
    if (supabase) {
      const { error } = await supabase.auth.signOut({ scope: 'local' });
      if (error) throw new Error('La déconnexion Supabase a échoué.');
    }
    setUser(null);
    setOrganizations([]);
    setOrganizationId(null);
    setStores([]);
    setStoreId(null);
  }, []);

  const selectedOrganization = organizations.find((organization) => organization.id === organizationId) || null;
  const selectedStore = stores.find((store) => store.id === storeId) || null;

  useEffect(() => {
    const preference = selectedOrganization?.theme || 'Clair';
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const applyTheme = () => {
      const dark = preference === 'Sombre' || (preference === 'Système' && media.matches);
      document.documentElement.dataset.theme = dark ? 'Sombre' : 'Clair';
    };
    applyTheme();
    if (preference !== 'Système') return undefined;
    media.addEventListener('change', applyTheme);
    return () => media.removeEventListener('change', applyTheme);
  }, [selectedOrganization?.theme]);

  const refreshBusinessContext = useCallback(async () => {
    const context = await loadAuthenticatedContext();
    applyContext(context);
    return context;
  }, [applyContext]);

  return (
    <AuthContext.Provider
      value={{
        user,
        settings: { currency: selectedOrganization?.currency || 'FCFA' },
        isAdmin: selectedOrganization?.role === 'ADMIN',
        organizations,
        organizationId,
        selectedOrganization,
        selectOrganization,
        stores,
        storeId,
        selectedStore,
        selectStore,
        refreshStores,
        refreshBusinessContext,
        loading,
        contextLoading,
        authError,
        businessError,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
