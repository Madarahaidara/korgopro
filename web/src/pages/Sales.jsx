import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { listSales } from '../api/salesApi';
import { formatMoney, formatDate } from '../api/db';
import { Badge, Modal } from '../components/ui';
import NewSaleModal from '../components/NewSaleModal';

export default function Sales() {
  const { user } = useAuth();
  const [sales, setSales] = useState(() => listSales());
  const [showNew, setShowNew] = useState(false);
  const [selected, setSelected] = useState(null);
  const [query, setQuery] = useState('');

  const searched = sales.filter((s) => {
    const q = query.toLowerCase();
    return (
      s.number.toLowerCase().includes(q) ||
      (s.customer && s.customer.full_name.toLowerCase().includes(q))
    );
  });

  const refresh = () => setSales(listSales());

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-title">Ventes</div>
          <div className="page-subtitle">Enregistrez vos factures et suivez les paiements.</div>
        </div>
        <div className="flex">
          <input
            className="input"
            placeholder="Rechercher…"
            style={{ width: 220 }}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button className="btn btn-primary" onClick={() => setShowNew(true)}>+ Nouvelle vente</button>
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflowX: 'auto', overflowY: 'hidden' }}>
        <table className="table">
          <thead>
            <tr>
              <th>N° Facture</th>
              <th>Date</th>
              <th>Client</th>
              <th>Caissier</th>
              <th className="text-right">Total</th>
              <th>Statut</th>
              <th>Paiement</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {searched.map((s) => (
              <tr key={s.id} style={{ cursor: 'pointer' }} onClick={() => setSelected(s)}>
                <td><b>{s.number}</b></td>
                <td>{formatDate(s.sale_date)}</td>
                <td>{s.customer?.full_name || <span className="text-muted">—</span>}</td>
                <td>{s.cashier?.username || '—'}</td>
                <td className="text-right"><b>{formatMoney(s.total_amount, s.currency)}</b></td>
                <td><Badge status={s.statut} /></td>
                <td><Badge status={s.payment_status} /></td>
                <td>
                  <button className="btn btn-sm" onClick={(e) => { e.stopPropagation(); setSelected(s); }}>
                    Détails
                  </button>
                </td>
              </tr>
            ))}
            {searched.length === 0 && (
              <tr><td colSpan={8}><div className="empty">Aucune vente enregistrée.</div></td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showNew && (
        <NewSaleModal
          user={user}
          onSave={() => { refresh(); setShowNew(false); }}
          onClose={() => setShowNew(false)}
        />
      )}

      {selected && <SaleDetail sale={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function SaleDetail({ sale, onClose }) {
  return (
    <Modal title={`Vente ${sale.number}`} onClose={onClose} width={640}>
      <div className="grid grid-2 mb-12">
        <div><div className="text-muted">Client</div><b>{sale.customer?.full_name || 'Comptoir'}</b></div>
        <div><div className="text-muted">Date</div><b>{formatDate(sale.sale_date)}</b></div>
        <div><div className="text-muted">Caissier</div><b>{sale.cashier?.username}</b></div>
        <div><div className="text-muted">Mode de paiement</div><b>{sale.payment_method}</b></div>
      </div>

      {sale.items.length > 0 && (
        <table className="table mb-12">
          <thead>
            <tr><th>Produit</th><th>Qté</th><th className="text-right">PU</th><th className="text-right">Total</th></tr>
          </thead>
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
        <TotalsLine label="Sous-total" value={formatMoney(sale.subtotal, sale.currency)} />
        <TotalsLine label="Remise" value={`-${formatMoney(sale.discount_amount, sale.currency)}`} />
        <TotalsLine label="Taxe" value={formatMoney(sale.tax_amount, sale.currency)} />
        <TotalsLine label="Total" bold value={formatMoney(sale.total_amount, sale.currency)} />
      </div>
    </Modal>
  );
}

function TotalsLine({ label, value, bold }) {
  return (
    <div className="flex justify-between mt-8" style={{ fontWeight: bold ? 800 : 500 }}>
      <span>{label}</span><span>{value}</span>
    </div>
  );
}
