import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import { useStores } from './context/StoreContext';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Sales from './pages/Sales';
import Stock from './pages/Stock';
import Treasury from './pages/Treasury';
import Proformas from './pages/Proformas';
import Invoices from './pages/Invoices';
import Customers from './pages/Customers';
import Admin from './pages/Admin';
import Settings from './pages/Settings';
import Icon from './components/Icon';

function Protected({ children, perm }) {
  const { user, can, restoring } = useAuth();
  if (restoring) {
    // Session en cours de restauration : écran de chargement (pas de redirection).
    return (
      <div className="boot-splash">
        <div className="boot-logo">K</div>
        <div className="boot-title">KORGO PRO</div>
        <div className="boot-message">Restauration de la session…</div>
        <div className="boot-bar"><span /></div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (perm && !can(perm)) {
    return (
      <div className="page">
        <div className="card empty">
          <div style={{ fontSize: 34 }}><Icon name="lock" size={40} /></div>
          <h3 style={{ margin: '12px 0 6px' }}>Accès refusé</h3>
          <p>Votre rôle ne vous permet pas d'accéder à ce module.</p>
        </div>
      </div>
    );
  }
  return <Layout>{children}</Layout>;
}

export default function App() {
  const { activeId } = useStores();
  const guarded = (perm, Comp) => (
    <Protected perm={perm} key={activeId}>
      <Comp />
    </Protected>
  );
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={guarded('dashboard', Dashboard)} />
      <Route path="/ventes" element={guarded('sales', Sales)} />
      <Route path="/stock" element={guarded('stock', Stock)} />
      <Route path="/tresorerie" element={guarded('treasury', Treasury)} />
      <Route path="/proformas" element={guarded('proformas', Proformas)} />
      <Route path="/factures" element={guarded('invoices', Invoices)} />
      <Route path="/clients" element={guarded('customers', Customers)} />
      <Route path="/administration" element={guarded('admin', Admin)} />
      <Route path="/parametres" element={guarded('settings', Settings)} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}