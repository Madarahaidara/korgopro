import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

const Login = lazy(() => import('./pages/Login'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const CustomersView = lazy(() => import('./pages/CustomersView'));
const Admin = lazy(() => import('./pages/Admin'));
const InvoiceRegister = lazy(() => import('./pages/InvoiceRegister'));
const LockScreen = lazy(() => import('./pages/LockScreen'));
const MainWindow = lazy(() => import('./pages/MainWindow'));
const ProformaInvoice = lazy(() => import('./pages/ProformaInvoice'));
const SaleView = lazy(() => import('./pages/SaleView'));
const SettingsView = lazy(() => import('./pages/SettingsView'));
const StockView = lazy(() => import('./pages/StockView'));
const TreasuryView = lazy(() => import('./pages/TreasuryView'));
const StoresView = lazy(() => import('./pages/StoresView'));
const SplashScreen = lazy(() => import('./pages/SplashScreen'));
const SalesReport = lazy(() => import('./pages/SalesReport'));
const SuppliersView = lazy(() => import('./pages/SuppliersView'));
const PurchaseOrdersView = lazy(() => import('./pages/PurchaseOrdersView'));

export default function App() {
  return (
    <Suspense fallback={<main className="erp-standalone" role="status">Chargement de l’écran…</main>}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/lock" element={<LockScreen />} />
        <Route path="/splash" element={<SplashScreen />} />
        <Route path="/main" element={<Navigate to="/dashboard" replace />} />
        <Route element={<MainWindow />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/sales" element={<SaleView />} />
          <Route path="/customers" element={<CustomersView />} />
          <Route path="/proforma" element={<ProformaInvoice />} />
          <Route path="/stock" element={<StockView />} />
          <Route path="/suppliers" element={<SuppliersView />} />
          <Route path="/purchases" element={<PurchaseOrdersView />} />
          <Route path="/invoices" element={<InvoiceRegister />} />
          <Route path="/reports" element={<SalesReport />} />
          <Route path="/treasury" element={<TreasuryView />} />
          <Route path="/stores" element={<StoresView />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="/settings" element={<SettingsView />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
