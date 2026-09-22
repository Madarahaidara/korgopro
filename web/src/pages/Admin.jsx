import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import ServerStatus from '../components/admin/ServerStatus';
import Overview from '../components/admin/Overview';
import UsersTab from '../components/admin/UsersTab';
import ActivityTab from '../components/admin/ActivityTab';
import DataTab from '../components/admin/DataTab';
import Icon from '../components/Icon';

const TABS = [
  { id: 'overview', label: 'Vue d\'ensemble'},
  { id: 'server', label: 'Serveur'},
  { id: 'users', label: ' Utilisateurs'},
  { id: 'activity', label: 'Journal'},
  { id: 'data', label: 'Données'},
];

export default function Admin() {
  const { user } = useAuth();
  const [tab, setTab] = useState('overview');

  if (user?.role !== 'ADMIN') {
    return (
      <div className="page">
        <div className="card empty">
          <div style={{ fontSize: 34 }}><Icon name="admin" size={40} /></div>
          <h3 style={{ margin: '12px 0 6px' }}>Accès réservé</h3>
          <p>La page d'administration est réservée aux administrateurs.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-title">Administration</div>
          <div className="page-subtitle">Pilotez le système, les serveurs et les données.</div>
        </div>
      </div>

      <div className="admin-tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`admin-tab ${tab === t.id ? 'active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="card admin-panel">
        {tab === 'overview' && <Overview />}
        {tab === 'server' && <ServerStatus />}
        {tab === 'users' && <UsersTab currentUser={user} onNavigate={() => setTab('activity')} />}
        {tab === 'activity' && <ActivityTab />}
        {tab === 'data' && <DataTab />}
      </div>
    </div>
  );
}