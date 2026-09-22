import { useState } from 'react';
import { listSales } from '../api/salesApi';
import { formatMoney, formatDate } from '../api/db';
import { Badge, Modal } from '../components/ui';

const FILTERS = ['TOUTES', 'EMISE', 'PARTIELLEMENT_PAYEE', 'PAYEE', 'ANNULEE'];

export default function Invoices() {
  const [sales, setSales] = useState(() => listSales());
  const [filter, setFilter] = useState('TOUTES');
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(null);

  const filtered = sales.filter((s) => {
    const okFilter = filter === 'TOUTES' || (s.statut || 'EMISE') === filter;
    const okQuery =
      !query ||
      s.number.toLowerCase().includes(query.toLowerCase()) ||
      (s.customer && s.customer.full_name.toLowerCase().includes(query.toLowerCase()));
    return okFilter && okQuery;
  });

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-title">Facturation</div>
          <div className="page-subtitle">Consultez et suivez toutes vos factures.</div>
        </div>
        <div className="flex">
          <select className="select" style={{ width: 200 }} value={filter} onChange={(e) => setFilter(e.target.value)}>
            {FILTERS.map((f) => <option key={f} value={f}>{f.replace('_', ' ')}</option>)}
          </select>
          <input className="input" placeholder="Rechercher…" style={{ width: 200 }} value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflowX: 'auto', overflowY: 'hidden' }}>
        <table className="table">
          <thead>
            <tr>
              <th>N° Facture</th>
              <th>Date</th>
              <th>Client</th>
              <th className="text-right">Sous-total</th>
              <th className="text-right">Taxe</th>
              <th className="text-right">Total</th>
              <th>Paiement</th>
              <th>Statut</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((s) => (
              <tr key={s.id} style={{ cursor: 'pointer' }} onClick={() => setSelected(s)}>
                <td><b>{s.number}</b></td>
                <td>{formatDate(s.sale_date)}</td>
                <td>{s.customer?.full_name || 'Comptoir'}</td>
                <td className="text-right">{formatMoney(s.subtotal, s.currency)}</td>
                <td className="text-right">{formatMoney(s.tax_amount, s.currency)}</td>
                <td className="text-right"><b>{formatMoney(s.total_amount, s.currency)}</b></td>
                <td><Badge status={s.payment_method} /></td>
                <td><Badge status={s.statut} /></td>
                <td>
                  <button className="btn btn-sm" onClick={(e) => { e.stopPropagation(); setSelected(s); }}>Aperçu</button>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && <tr><td colSpan={9}><div className="empty">Aucune facture.</div></td></tr>}
          </tbody>
        </table>
      </div>

      {selected && <InvoicePreview sale={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function InvoicePreview({ sale, onClose }) {
  return (
    <Modal title={`Aperçu — ${sale.number}`} onClose={onClose} width={680}>
      <div className="invoice-sheet">
        <div className="justify-between mb-12">
          <div>
            <div style={{ fontSize: 18, fontWeight: 800 }}>FACTURE</div>
            <div className="text-muted">N° {sale.number}</div>
          </div>
          <div className="text-right">
            <div className="text-muted">Date</div>
            <b>{formatDate(sale.sale_date)}</b>
          </div>
        </div>
        <div className="card mb-12" style={{ background: '#fafbfc' }}>
          <div className="text-muted" style={{ fontSize: 12, fontWeight: 700 }}>CLIENT</div>
          <b>{sale.customer?.full_name || 'Client comptoir'}</b>
          {sale.customer?.company && <div>{sale.customer.company}</div>}
          {sale.customer?.phone && <div className="text-muted">{sale.customer.phone}</div>}
        </div>

        {sale.items.length > 0 && (
          <table className="table mb-12">
            <thead><tr><th>Description</th><th>Qté</th><th className="text-right">PU</th><th className="text-right">Montant</th></tr></thead>
            <tbody>
              {sale.items.map((it) => (
                <tr key={it.id}>
                  <td>{it.product?.name || 'Produit'}</td>
                  <td>{it.quantity}</td>
                  <td className="text-right">{formatMoney(it.unit_price, sale.currency)}</td>
                  <td className="text-right">{formatMoney(it.line_total, sale.currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <div style={{ marginLeft: 'auto', maxWidth: 320, width: '100%' }}>
          <Line label="Sous-total" value={formatMoney(sale.subtotal, sale.currency)} />
          <Line label="Remise" value={`-${formatMoney(sale.discount_amount, sale.currency)}`} />
          <Line label="Taxe" value={formatMoney(sale.tax_amount, sale.currency)} />
          <Line label="Total" value={formatMoney(sale.total_amount, sale.currency)} bold />
        </div>
      </div>
    </Modal>
  );
}

function Line({ label, value, bold }) {
  return (
    <div className="flex justify-between mt-8" style={{ fontWeight: bold ? 800 : 500 }}>
      <span>{label}</span><span>{value}</span>
    </div>
  );
}
