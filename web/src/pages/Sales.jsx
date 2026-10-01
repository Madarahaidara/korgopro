import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { listSales, receivePayment } from '../api/salesApi';
import { formatMoney, formatDate } from '../api/db';
import { Badge, Modal, toast } from '../components/ui';
import NewSaleModal from '../components/NewSaleModal';

/** Ventes non soldées (crédits et paiements partiels), hors ventes annulées. */
const isUnpaid = (s) => s.sale_status !== 'CANCELLED' && s.due > 0.001;

export default function Sales() {
  const { user } = useAuth();
  const [sales, setSales] = useState(() => listSales());
  const [showNew, setShowNew] = useState(false);
  const [selected, setSelected] = useState(null);
  const [collecting, setCollecting] = useState(null);
  const [onlyCredit, setOnlyCredit] = useState(false);
  const [query, setQuery] = useState('');

  const searched = sales.filter((s) => {
    if (onlyCredit && !isUnpaid(s)) return false;
    const q = query.toLowerCase();
    return (
      s.number.toLowerCase().includes(q) ||
      (s.customer && s.customer.full_name.toLowerCase().includes(q))
    );
  });
  const outstanding = sales.filter(isUnpaid);
  const outstandingTotal = outstanding.reduce((sum, s) => sum + s.due, 0);

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
          <button
            className={`btn ${onlyCredit ? 'btn-primary' : ''}`}
            onClick={() => setOnlyCredit((v) => !v)}
            title="Afficher uniquement les ventes à encaisser"
          >
            {onlyCredit ? '✕ Tous les paiements' : `À encaisser (${outstanding.length})`}
          </button>
          <button className="btn btn-primary" onClick={() => setShowNew(true)}>+ Nouvelle vente</button>
        </div>
      </div>

      {outstanding.length > 0 && (
        <div className="card mb-12" style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          borderLeft: '4px solid #b45309',
        }}>
          <div>
            <div className="text-muted">Total à encaisser (crédits et soldes partiels)</div>
            <b style={{ fontSize: 20 }}>{formatMoney(outstandingTotal)}</b>
          </div>
          <button className="btn" onClick={() => setOnlyCredit(true)}>Voir les {outstanding.length} facture(s)</button>
        </div>
      )}

      <div className="card" style={{ padding: 0, overflowX: 'auto', overflowY: 'hidden' }}>
        <table className="table">
          <thead>
            <tr>
              <th>N° Facture</th>
              <th>Date</th>
              <th>Client</th>
              <th>Caissier</th>
              <th className="text-right">Total</th>
              <th className="text-right">Reste dû</th>
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
                <td className="text-right">
                  {s.due > 0
                    ? <b style={{ color: '#b45309' }}>{formatMoney(s.due, s.currency)}</b>
                    : <span className="text-muted">—</span>}
                </td>
                <td><Badge status={s.statut} /></td>
                <td><Badge status={s.payment_status} /></td>
                <td>
                  <div className="flex" style={{ gap: 4 }}>
                    {isUnpaid(s) && (
                      <button
                        className="btn btn-sm btn-success"
                        onClick={(e) => { e.stopPropagation(); setCollecting(s); }}
                      >
                        Encaisser
                      </button>
                    )}
                    <button className="btn btn-sm" onClick={(e) => { e.stopPropagation(); setSelected(s); }}>
                      Détails
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {searched.length === 0 && (
              <tr><td colSpan={9}>
                <div className="empty">
                  {onlyCredit ? 'Aucune vente à encaisser : tout est payé.' : 'Aucune vente enregistrée.'}
                </div>
              </td></tr>
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

      {selected && (
        <SaleDetail
          sale={selected}
          onClose={() => setSelected(null)}
          onCollect={() => setCollecting(selected)}
        />
      )}

      {collecting && (
        <ReceivePaymentModal
          sale={collecting}
          onSave={() => { refresh(); setCollecting(null); setSelected(null); }}
          onClose={() => setCollecting(null)}
        />
      )}
    </div>
  );
}

/**
 * Encaissement d'une facture impayée (crédit ou solde partiel) : le montant
 * saisi entre en caisse, diminue le reste dû et la dette du client.
 */
function ReceivePaymentModal({ sale, onSave, onClose }) {
  const [amount, setAmount] = useState(String(Math.round(sale.due)));
  const [method, setMethod] = useState('CASH');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);

  const value = Math.max(Number(amount) || 0, 0);
  const remaining = Math.max(sale.due - value, 0);

  const submit = () => {
    if (value <= 0) {
      toast('Indiquez le montant encaissé.', 'danger');
      return;
    }
    if (value > sale.due + 0.001) {
      toast(`Montant supérieur au reste dû (${formatMoney(sale.due, sale.currency)}).`, 'danger');
      return;
    }
    setSaving(true);
    try {
      const updated = receivePayment({
        sale_id: sale.id, amount: value, payment_method: method, notes,
      });
      toast(updated.due > 0
        ? `${formatMoney(value, sale.currency)} encaissés. Reste ${formatMoney(updated.due, sale.currency)} sur ${sale.number}.`
        : `Facture ${sale.number} soldée.`);
      onSave();
    } catch (err) {
      toast(err.message || 'Encaissement impossible.', 'danger');
      setSaving(false);
    }
  };

  return (
    <Modal title={`Encaisser ${sale.number}`} onClose={onClose} width={470}>
      <div className="grid grid-2 mb-12">
        <div><div className="text-muted">Client</div><b>{sale.customer?.full_name || 'Comptoir'}</b></div>
        <div><div className="text-muted">Total facture</div><b>{formatMoney(sale.total_amount, sale.currency)}</b></div>
        <div><div className="text-muted">Déjà payé</div><b>{formatMoney(sale.amount_paid, sale.currency)}</b></div>
        <div>
          <div className="text-muted">Reste dû</div>
          <b style={{ color: '#b45309' }}>{formatMoney(sale.due, sale.currency)}</b>
        </div>
      </div>

      <div className="form-grid">
        <div className="field">
          <label>Montant encaissé</label>
          <input className="input" type="number" min="0" step="any" autoFocus
            value={amount} onChange={(e) => setAmount(e.target.value)} />
        </div>
        <div className="field">
          <label>Moyen de paiement</label>
          <select className="select" value={method} onChange={(e) => setMethod(e.target.value)}>
            <option value="CASH">Espèces</option>
            <option value="MOBILE_MONEY">Mobile Money</option>
            <option value="CARD">Carte bancaire</option>
            <option value="BANK">Banque / virement</option>
          </select>
        </div>
      </div>

      <div className="field">
        <label>Référence / note (facultatif)</label>
        <input className="input" value={notes} onChange={(e) => setNotes(e.target.value)}
          placeholder="N° de transaction, remarque…" />
      </div>

      <div className="flex justify-between align-end mt-8">
        <button className="btn btn-sm" onClick={() => setAmount(String(Math.round(sale.due)))}>
          Solde intégral
        </button>
        <div className="text-right">
          <div className="text-muted">Après encaissement</div>
          <b style={{ fontSize: 18 }}>
            {remaining > 0 ? `Reste ${formatMoney(remaining, sale.currency)}` : 'Facture soldée'}
          </b>
        </div>
      </div>

      <div className="form-actions">
        <button className="btn" onClick={onClose}>Annuler</button>
        <button className="btn btn-success" onClick={submit} disabled={saving}>
          {saving ? 'Encaissement…' : `Encaisser ${formatMoney(value, sale.currency)}`}
        </button>
      </div>
    </Modal>
  );
}

function SaleDetail({ sale, onClose, onCollect }) {
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
        <TotalsLine label="Payé" value={formatMoney(sale.amount_paid, sale.currency)} />
        {sale.due > 0 && (
          <TotalsLine label="Reste dû" bold value={formatMoney(sale.due, sale.currency)} />
        )}
      </div>

      {sale.due > 0 && sale.sale_status !== 'CANCELLED' && (
        <div className="form-actions">
          <span className="text-muted" style={{ marginRight: 'auto' }}>
            Cette facture n&apos;est pas soldée.
          </span>
          <button className="btn btn-success" onClick={onCollect}>
            Encaisser {formatMoney(sale.due, sale.currency)}
          </button>
        </div>
      )}
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
