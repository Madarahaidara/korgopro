import { useState } from 'react';
import { Navigate, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import BrandLogo from '../components/BrandLogo';
import Icon from '../components/Icon';

const navigation = [
  { to: '/dashboard', label: 'Tableau de bord', icon: 'dashboard', permission: 'view_dashboard' },
  { to: '/sales', label: 'Vente', icon: 'sale', permission: 'create_sales' },
  { to: '/customers', label: 'Clients', icon: 'user', permission: 'manage_customers' },
  { to: '/invoices', label: 'Registre factures', icon: 'receipt', permission: 'view_invoice_register' },
  { to: '/reports', label: 'Rapport des ventes', icon: 'dashboard', permission: 'view_reports' },
  { to: '/proforma', label: 'Documents pro forma', icon: 'document', permission: 'manage_proformas' },
  { to: '/stock', label: 'Stock', icon: 'stock', permission: ['view_stock', 'manage_stock'] },
  { to: '/suppliers', label: 'Fournisseurs', icon: 'building', permission: 'manage_stock' },
  { to: '/purchases', label: 'Achats', icon: 'receipt', permission: 'manage_stock' },
  { to: '/treasury', label: 'Trésorerie', icon: 'treasury', permission: ['view_treasury', 'manage_treasury'] },
  { to: '/stores', label: 'Magasins', icon: 'building', permission: 'manage_stores' },
  { to: '/admin', label: 'Administration', icon: 'admin', permission: 'access_admin' },
  { to: '/settings', label: 'Paramètres', icon: 'settings', permission: 'manage_settings' },
];

function canOpenNavigationItem(item, permissions) {
  const required = Array.isArray(item.permission) ? item.permission : [item.permission];
  return required.some((permission) => permissions.includes(permission));
}

export default function MainWindow() {
  const {
    user, logout, loading, contextLoading, businessError,
    organizations, selectedOrganization, organizationId, selectOrganization,
    stores, storeId, selectStore,
  } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [logoutError, setLogoutError] = useState('');
  const [selectionError, setSelectionError] = useState('');

  const handleLogout = async () => {
    setLogoutError('');
    try {
      await logout();
      navigate('/login', { replace: true });
    } catch (error) {
      setLogoutError(error.message || 'Impossible de fermer la session.');
    }
  };

  if (loading) {
    return <main className="erp-standalone" role="status">Restauration de la session…</main>;
  }
  if (!user) return <Navigate to="/login" replace />;
  if (contextLoading && !selectedOrganization) {
    return <main className="erp-standalone" role="status">Chargement de l’entreprise…</main>;
  }
  if (!selectedOrganization) {
    return <main className="erp-standalone" role="alert">
      {businessError || 'Aucune entreprise active n’est disponible pour ce compte.'}
    </main>;
  }

  const permissions = selectedOrganization.permissions || [];
  const visibleNavigation = navigation.filter((item) => canOpenNavigationItem(item, permissions));
  const activePage = navigation.find((item) => item.to === location.pathname);
  const fallbackRoute = visibleNavigation[0]?.to;
  if (activePage && !canOpenNavigationItem(activePage, permissions)) {
    if (fallbackRoute) return <Navigate to={fallbackRoute} replace />;
    return <main className="erp-standalone" role="alert">
      Aucun écran n’est autorisé pour ce compte dans cette entreprise. Contactez un administrateur.
      {logoutError && <p role="alert">{logoutError}</p>}
      <button type="button" onClick={handleLogout}>Quitter la session</button>
    </main>;
  }

  const handleOrganizationChange = (event) => {
    setSelectionError('');
    try {
      selectOrganization(event.target.value);
    } catch (error) {
      setSelectionError(error.message);
    }
  };
  const handleStoreChange = (event) => {
    setSelectionError('');
    try {
      selectStore(event.target.value);
    } catch (error) {
      setSelectionError(error.message);
    }
  };

  return (
    <div className="erp-shell">
      <aside className="erp-sidebar">
        <div className="erp-brand">
          <BrandLogo className="erp-brand-mark" />
          <span><strong>Korgo Pro</strong><small>Gestion commerciale</small></span>
        </div>
        <div className="erp-tenant">
          <span className="erp-tenant-icon"><Icon name="building" size={18} /></span>
          <span>
            <small>ENTREPRISE ACTIVE</small>
            {organizations.length > 1 ? (
              <select className="erp-control" aria-label="Entreprise active" value={organizationId} onChange={handleOrganizationChange}>
                {organizations.map((organization) => <option key={organization.id} value={organization.id}>{organization.name}</option>)}
              </select>
            ) : <strong>{selectedOrganization.name}</strong>}
          </span>
        </div>
        <nav className="erp-navigation" aria-label="Navigation principale">
          <span className="erp-nav-label">ESPACE DE TRAVAIL</span>
          {visibleNavigation.map((item) => (
            <NavLink key={item.to} to={item.to} className={({ isActive }) => `erp-nav-link${isActive ? ' is-active' : ''}`}>
              <span className="erp-nav-icon"><Icon name={item.icon} size={19} /></span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="erp-sidebar-footer">
          <span className="erp-status-dot" />
          <span>Session Supabase authentifiée</span>
        </div>
      </aside>
      <div className="erp-main">
        <header className="erp-topbar">
          <span className="erp-topbar-context">Korgo Pro <span>/</span> {selectedOrganization.name}</span>
          <div className="erp-user-menu">
            {stores.length > 1 && (
              <select className="erp-control" aria-label="Magasin actif" value={storeId ?? ''} onChange={handleStoreChange}>
                {stores.map((store) => <option key={store.id} value={store.id}>{store.name}</option>)}
              </select>
            )}
            {logoutError && <span role="alert">{logoutError}</span>}
            <button type="button" className="erp-lock-button" onClick={() => navigate('/lock')}>Verrouiller</button>
            <span className="erp-avatar">{(user?.username || 'U')[0].toUpperCase()}</span>
            <span className="erp-user-copy"><strong>{user?.username}</strong><small>{selectedOrganization.role}</small></span>
            <button type="button" className="erp-logout-button" onClick={handleLogout}>Quitter</button>
          </div>
        </header>
        <main className="erp-content">
          {(businessError || selectionError) && (
            <div className="erp-message erp-message-error" role="alert">{businessError || selectionError}</div>
          )}
          {contextLoading
            ? <div className="erp-standalone" role="status">Chargement des magasins…</div>
            : <Outlet />}
        </main>
      </div>
    </div>
  );
}
