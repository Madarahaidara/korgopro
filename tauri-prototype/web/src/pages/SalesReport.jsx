import { useCallback, useMemo, useState } from 'react';
import { listSales } from '../api/businessApi';
import { useBusinessData } from '../api/useBusinessData';
import { DataTable, InlineMessage, MetricCard, PageHeader, Panel, StatusBadge } from '../components/erp';
import { useAuth } from '../context/AuthContext';
import { formatMoney } from '../data/demoData';
import { downloadCsv } from '../utils/downloadCsv';

function firstDayOfMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`;
}

function today() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}

function localDate(value) {
  if (!value) return '';
  return new Date(value).toLocaleString('fr-FR');
}

export default function SalesReport() {
  const { organizationId, storeId, selectedStore, selectedOrganization, settings } = useAuth();
  const canExport = (selectedOrganization?.permissions || []).includes('export_data');
  const [from, setFrom] = useState(firstDayOfMonth);
  const [to, setTo] = useState(today);
  const [query, setQuery] = useState('');
  const load = useCallback(
    () => listSales(organizationId, storeId, null, selectedStore?.is_default),
    [organizationId, selectedStore?.is_default, storeId],
  );
  const { data, loading, error, refresh } = useBusinessData(load);
  const filtered = useMemo(() => (data || []).filter((sale) => {
    const date = new Date(sale.sale_date);
    if (!Number.isFinite(date.getTime())) return false;
    const start = from ? new Date(`${from}T00:00:00`) : null;
    const end = to ? new Date(`${to}T00:00:00`) : null;
    if (start && date < start) return false;
    if (end) {
      end.setDate(end.getDate() + 1);
      if (date >= end) return false;
    }
    const haystack = `${sale.id} ${sale.customer} ${sale.payment_method || ''} ${sale.status}`.toLocaleLowerCase();
    return haystack.includes(query.trim().toLocaleLowerCase());
  }), [data, from, query, to]);
  const completed = filtered.filter((sale) => sale.sale_status !== 'CANCELLED');
  const revenue = completed.reduce((sum, sale) => sum + (Number(sale.total_amount) || 0), 0);
  const collected = completed.reduce((sum, sale) => sum + (Number(sale.amount_paid) || 0), 0);
  const outstanding = completed.reduce((sum, sale) => sum + Math.max((Number(sale.total_amount) || 0) - (Number(sale.amount_paid) || 0), 0), 0);

  const exportReport = () => downloadCsv(
    `rapport-ventes-${selectedOrganization?.code || 'entreprise'}`,
    ['Facture', 'Date', 'Client', 'Mode de paiement', 'Statut', 'Total', 'EncaissÃ©', 'Reste dÃ»', 'Devise'],
    filtered.map((sale) => [sale.id, sale.sale_date, sale.customer, sale.payment_method, sale.status, sale.total_amount, sale.amount_paid, sale.due, sale.currency || settings.currency]),
  );

  if (loading && !data) return <div className="erp-standalone" role="status">Chargement du rapport de ventes…</div>;
  if (error && !data) return <InlineMessage tone="error">{error} <button type="button" onClick={() => refresh().catch(() => {})}>Réessayer</button></InlineMessage>;

  return (
    <div className="erp-page">
      <PageHeader
        title="Rapport des ventes"
        subtitle="Chiffre d’affaires, encaissements et soldes sur la période sélectionnée."
        action={canExport && <button type="button" className="erp-button erp-button-secondary" onClick={exportReport} disabled={!filtered.length}>Exporter CSV</button>}
      />
      {error && <InlineMessage tone="error">{error}</InlineMessage>}
      <Panel>
        <div className="erp-report-filters">
          <label className="erp-field"><span>Du</span><input className="erp-control" type="date" value={from} max={to || undefined} onChange={(event) => setFrom(event.target.value)} /></label>
          <label className="erp-field"><span>Au</span><input className="erp-control" type="date" value={to} min={from || undefined} onChange={(event) => setTo(event.target.value)} /></label>
          <label className="erp-field erp-report-search"><span>Recherche</span><input className="erp-control" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Facture, client, paiement…" /></label>
        </div>
      </Panel>
      <div className="erp-metrics-grid">
        <MetricCard label="Chiffre d’affaires" value={formatMoney(revenue, settings.currency)} detail={`${completed.length} vente(s) hors annulations`} icon="↗" tone="blue" />
        <MetricCard label="Montant encaissé" value={formatMoney(collected, settings.currency)} detail="Paiements enregistrés" icon="¤" tone="green" />
        <MetricCard label="Reste à encaisser" value={formatMoney(outstanding, settings.currency)} detail="Crédit et paiements partiels" icon="⌛" tone="amber" />
        <MetricCard label="Ventes annulées" value={filtered.length - completed.length} detail="Exclues du chiffre d’affaires" icon="↶" tone="red" />
      </div>
      <Panel title="Détail des factures" description={`${filtered.length} facture(s) sur la période`}>
        <DataTable
          columns={[
            { key: 'id', label: 'N° facture' },
            { key: 'sale_date', label: 'Date', render: localDate },
            { key: 'customer', label: 'Client' },
            { key: 'payment_method', label: 'Paiement', render: (value) => value || '—' },
            { key: 'total_amount', label: 'Total', render: (value) => formatMoney(value, settings.currency) },
            { key: 'amount_paid', label: 'Encaissé', render: (value) => formatMoney(value, settings.currency) },
            { key: 'due', label: 'Reste dû', render: (value) => formatMoney(value, settings.currency) },
            { key: 'status', label: 'Statut', render: (value) => <StatusBadge>{value}</StatusBadge> },
          ]}
          rows={filtered}
          emptyMessage="Aucune facture ne correspond à cette période et à cette recherche."
        />
      </Panel>
    </div>
  );
}
