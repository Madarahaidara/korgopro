import { useEffect, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useStores } from '../context/StoreContext';
import { updateStore, deleteStore } from '../api/storesApi';
import { toast } from './ui';
import StoreModal from './StoreModal';
import SyncBanner from './SyncBanner';
import Icon from './Icon';

const NAV = [
  { to: '/', label: 'Dashboard', icon: 'dashboard', perm: 'dashboard' },
  { to: '/ventes', label: 'Vente', icon: 'sale', perm: 'sales' },
  { to: '/factures', label: 'Registre factures', icon: 'receipt', perm: 'invoices' },
  { to: '/proformas', label: 'Document', icon: 'document', perm: 'proformas' },
  { to: '/stock', label: 'Stock', icon: 'stock', perm: 'stock' },
  { to: '/tresorerie', label: 'Trésorerie', icon: 'treasury', perm: 'treasury' },
  { to: '/clients', label: 'Clients', icon: 'user', perm: 'customers' },
  { to: '/administration', label: 'Admin', icon: 'admin', perm: 'admin' },
  { to: '/parametres', label: 'Paramètres', icon: 'settings', perm: 'settings' },
];

export default function Layout({ children }) {
  const { user, logout, settings, can } = useAuth();
  const { stores, activeId, activeStore, selectStore, refreshStores, createStore } = useStores();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [showStoreModal, setShowStoreModal] = useState(false);
  const [editingStore, setEditingStore] = useState(null);

  const canManageStores = can('admin') || user?.role === 'GESTIONNAIRE';

  const handleLogout = async () => {
    try {
      await logout();
    } catch (error) {
      toast(error.message, 'error');
    } finally {
      navigate('/login');
    }
  };

  // Ferme le tiroir à la navigation.
  useEffect(() => {
    setOpen(false);
  }, []);

  const items = NAV.filter((n) => can(n.perm));

  return (
    <div className="layout">
      <div
        className={`sidebar-backdrop ${open ? 'show' : ''}`}
        onClick={() => setOpen(false)}
      />
      <aside className={`sidebar ${open ? 'mobile-open' : ''}`}>
        <div className="brand">
          <div className="brand-logo">K</div>
          <div>
            <div className="brand-name">{settings.company_name || 'Korgo Pro'}</div>
            <div className="brand-sub">Gestion web</div>
          </div>
        </div>
        <nav className="nav" onClick={() => setOpen(false)}>
          {items.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              end={n.to === '/'}
            >
              <span className="nav-icon"><Icon name={n.icon} size={20} /></span>
              <span>{n.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="topbar-left">
            <button className="burger" onClick={() => setOpen((v) => !v)} aria-label="Menu">
              <span /><span /><span />
            </button>
            <div className="topbar-title">
              {settings.company_name || 'Korgo Pro'}
              <span className="topbar-sub">· {settings.address || ''}</span>
            </div>
          </div>
          <div className="topbar-user">
            <select
              className="select"
              style={{ maxWidth: 190 }}
              value={activeId ?? ''}
              onChange={(e) => selectStore(e.target.value)}
              aria-label="Magasin actif"
            >
              {stores.filter((s) => s.active !== false).map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
            {canManageStores && (
              <>
                <button
                  className="btn btn-sm"
                  onClick={() => { setEditingStore(null); setShowStoreModal(true); }}
                  title="Créer un nouveau magasin"
                >
                  + Magasin
                </button>
                {activeStore && (
                  <>
                    <button
                      className="btn btn-sm"
                      onClick={() => { setEditingStore(activeStore); setShowStoreModal(true); }}
                      title="Modifier le magasin actif"
                    >
                      <Icon name="edit" size={16} style={{ verticalAlign: '-2px' }} />
                    </button>
                    <button
                      className="btn btn-sm btn-danger"
                      onClick={() => {
                        if (!window.confirm(`Supprimer le magasin « ${activeStore.name} » ?`)) return;
                        try {
                          deleteStore(activeStore.id);
                          refreshStores();
                          toast('Magasin supprimé.');
                        } catch (err) {
                          toast(err.message, 'danger');
                        }
                      }}
                      title="Supprimer le magasin actif"
                    >
                      <Icon name="delete" size={16} style={{ verticalAlign: '-2px' }} />
                    </button>
                  </>
                )}
              </>
            )}
            <div className="avatar">{user?.username?.[0]?.toUpperCase() || 'K'}</div>
            <div className="user-meta">
              <div className="user-name">{user?.username}</div>
              <div className="user-role">{user?.role}</div>
            </div>
            <button className="btn-logout" onClick={handleLogout}>Déconnexion</button>
          </div>
        </header>
        <main className="content">
          <SyncBanner />
          {children}
        </main>
      </div>

      {showStoreModal && (
        <StoreModal
          store={editingStore}
          onClose={() => setShowStoreModal(false)}
          onSave={(form) => {
            try {
              if (editingStore) {
                updateStore(editingStore.id, form);
                toast('Magasin mis à jour.');
              } else {
                const created = createStore(form);
                selectStore(created.id);
                toast(`Magasin « ${created.name} » créé (${created.code}).`);
              }
              refreshStores();
              setShowStoreModal(false);
            } catch (err) {
              toast(err.message || 'Erreur lors de l\'enregistrement du magasin.', 'danger');
            }
          }}
        />
      )}
    </div>
  );
}