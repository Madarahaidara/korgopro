import { useCallback } from 'react';
import { formatMoney } from '../data/demoData';
import { DataTable, InlineMessage, MetricCard, PageHeader, Panel, StatusBadge } from '../components/erp';
import { loadDashboard } from '../api/businessApi';
import { useBusinessData } from '../api/useBusinessData';
import { useAuth } from '../context/AuthContext';

export default function Dashboard() {
  const { organizationId, storeId, selectedStore, settings } = useAuth();
  const load = useCallback(
    () => loadDashboard(organizationId, storeId, selectedStore?.is_default),
    [organizationId, selectedStore?.is_default, storeId],
  );
  const { data, loading, error, refresh } = useBusinessData(load);
  const currency = settings.currency;
  const chartMax = Math.max(...(data?.chart || []).map((point) => point.amount), 1);

  if (loading && !data) return <div className="erp-standalone" role="status">Chargement du tableau de bord…</div>;
  if (error && !data) return <InlineMessage tone="error">{error} <button type="button" onClick={() => refresh().catch(() => {})}>Réessayer</button></InlineMessage>;
  if (!data) return null;

  return (
    <div className="erp-page">
      <PageHeader
        title="Tableau de bord"
        subtitle="Vue d’ensemble des opérations enregistrées dans votre entreprise."
        action={<span className="erp-date-chip">{new Date().toLocaleDateString('fr-FR', { dateStyle: 'full' })}</span>}
      />
      {error && <InlineMessage tone="error">{error}</InlineMessage>}
      <div className="erp-metrics-grid">
        <MetricCard label="Ventes du jour" value={formatMoney(data.totalToday, currency)} detail={`${data.salesToday.length} vente(s) enregistrée(s)`} icon="↗" tone="blue" />
        <MetricCard label="Reste à encaisser" value={formatMoney(data.unpaid, currency)} detail="Factures non réglées" icon="▤" tone="amber" />
        <MetricCard label="Produits en stock bas" value={data.lowStock.length} detail="Sous le seuil défini" icon="⚠" tone="red" />
        <MetricCard label="Ventes de la semaine" value={formatMoney(data.totalWeek, currency)} detail="7 derniers jours" icon="▣" tone="green" />
      </div>

      <div className="erp-dashboard-grid">
        <Panel title="Activité des ventes" description="Chiffre d’affaires journalier · 7 derniers jours">
          <div className="erp-chart-summary"><strong>{formatMoney(data.totalWeek, currency)}</strong><span>Cette semaine</span></div>
          <div className="erp-bar-chart" role="img" aria-label="Ventes réelles des sept derniers jours">
            {data.chart.map((point) => (
              <div className="erp-bar-column" key={point.label} title={`${point.label} : ${formatMoney(point.amount, currency)}`}>
                <span className="erp-bar-value">{point.amount ? new Intl.NumberFormat('fr-FR', { notation: 'compact' }).format(point.amount) : '—'}</span>
                <div className="erp-bar-track"><span style={{ height: `${Math.max(point.amount / chartMax * 100, point.amount ? 5 : 0)}%` }} /></div>
                <small>{point.day}</small>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="Alertes de stock" description="Produits sous le seuil minimum" action={<span className="erp-counter">{data.lowStock.length}</span>}>
          <div className="erp-alert-list">
            {data.lowStock.slice(0, 6).map((product) => (
              <div className="erp-alert-row" key={product.id}>
                <span className="erp-product-avatar">▦</span>
                <span className="erp-alert-copy"><strong>{product.name}</strong><small>Réf. {product.code} · seuil {product.threshold}</small></span>
                <StatusBadge>Stock bas</StatusBadge>
              </div>
            ))}
            {!data.lowStock.length && <div className="erp-empty-card">Aucune alerte de stock pour ce magasin.</div>}
          </div>
        </Panel>
      </div>

      <Panel title="Dernières ventes" description="Ventes récentes de l’entreprise">
        <DataTable
          columns={[
            { key: 'id', label: 'N° Vente' },
            { key: 'date', label: 'Date' },
            { key: 'customer', label: 'Client' },
            { key: 'amount', label: 'Montant', render: (amount) => <strong>{formatMoney(amount, currency)}</strong> },
            { key: 'status', label: 'Statut', render: (status) => <StatusBadge>{status}</StatusBadge> },
          ]}
          rows={data.sales.slice(0, 8)}
        />
      </Panel>
    </div>
  );
}
