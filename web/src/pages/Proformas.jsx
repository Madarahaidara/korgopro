import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { listProformas, setProformaStatus, convertProformaToSale, PROFORMA_STATUS } from '../api/proformaApi';
import { formatMoney, formatDate } from '../api/db';
import { Badge, Modal, toast } from '../components/ui';
import ProformaForm from '../components/ProformaForm';

export default function Proformas() {
  const { user } = useAuth();
  const [proformas, setProformas] = useState(() => listProformas());
  const [showNew, setShowNew] = useState(false);
  const [selected, setSelected] = useState(null);

  const refresh = () => setProformas(listProformas());

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-title">Proformas</div>
          <div className="page-subtitle">Créez des devis et suivez leur cycle de vie.</div>
        </div>
        <button className="btn btn-primary" onClick={() => setShowNew(true)}>+ Nouvelle proforma</button>
      </div>

      <div className="card" style={{ padding: 0, overflowX: 'auto', overflowY: 'hidden' }}>
        <table className="table">
          <thead>
            <tr>
              <th>N°</th>
              <th>Date</th>
              <th>Client</th>
              <th className="text-right">Total</th>
              <th>Statut</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {proformas.map((p) => (
              <tr key={p.id}>
                <td><b>{p.number}</b></td>
                <td>{formatDate(p.created_date)}</td>
                <td>{p.customer?.full_name || <span className="text-muted">—</span>}</td>
                <td className="text-right"><b>{formatMoney(p.total_amount, p.currency)}</b></td>
                <td><Badge status={p.status} /></td>
                <td>
                  <div className="flex">
                    <button className="btn btn-sm" onClick={() => setSelected(p)}>Détails</button>
                    <button
                      className="btn btn-sm btn-success"
                      onClick={() => {
                        const sale = convertProformaToSale(p.id, user.id, 'CASH');
                        refresh();
                        toast(`Proforma convertie en ${sale.number}.`);
                      }}
                      disabled={p.status === 'CONVERTIE'}
                    >
                      Convertir
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {proformas.length === 0 && <tr><td colSpan={6}><div className="empty">Aucune proforma.</div></td></tr>}
          </tbody>
        </table>
      </div>

      {showNew && (
        <ProformaForm
          user={user}
          onSave={() => { refresh(); setShowNew(false); toast('Proforma créée.'); }}
          onClose={() => setShowNew(false)}
        />
      )}

      {selected && (
        <ProformaDetail
          proforma={selected}
          onStatus={(status) => { setProformaStatus(selected.id, status); refresh(); setSelected(listProformas().find((x) => x.id === selected.id)); toast('Statut mis à jour.'); }}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}

function ProformaDetail({ proforma, onStatus, onClose }) {
  return (
    <Modal title={`Proforma ${proforma.number}`} onClose={onClose} width={640}>
      <div className="document-print-actions"><button className="btn btn-primary" onClick={() => window.print()}>Imprimer / Enregistrer en PDF</button></div>
      <div className="document-print-sheet">
      <div className="document-print-header">
        <div><div className="document-brand">KORGO</div><div className="text-muted">Document commercial</div></div>
        <div className="text-right text-muted">Émise le {formatDate(proforma.created_date)}<br />Valable jusqu’au {formatDate(proforma.valid_until)}</div>
      </div>
      <div className="document-print-title">FACTURE PROFORMA N° {proforma.number}</div>
      <div className="document-party mb-12">
        <div className="text-muted">Doit :</div>
        <b>{proforma.customer?.full_name || '—'}</b>
        {proforma.customer?.address && <div>{proforma.customer.address}</div>}
        <div className="text-muted">{[proforma.customer?.phone, proforma.customer?.email].filter(Boolean).join(' · ')}</div>
      </div>

      {proforma.items.length > 0 && (
        <table className="table mb-12">
          <thead><tr><th>Description</th><th>Qté</th><th className="text-right">PU</th><th className="text-right">Total</th></tr></thead>
          <tbody>
            {proforma.items.map((it) => (
              <tr key={it.id}>
                <td>{it.product?.name || it.description}</td>
                <td>{it.quantity}</td>
                <td className="text-right">{formatMoney(it.unit_price, proforma.currency)}</td>
                <td className="text-right">{formatMoney(it.line_total, proforma.currency)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div style={{ marginLeft: 'auto', maxWidth: 320, width: '100%' }}>
        <TotalsLine label="Sous-total" value={formatMoney(proforma.subtotal, proforma.currency)} />
        <TotalsLine label="Remise" value={`-${formatMoney(proforma.discount_amount, proforma.currency)}`} />
        <TotalsLine label="Taxe" value={formatMoney(proforma.tax_amount, proforma.currency)} />
        <TotalsLine label="TOTAL GENERAL" bold value={formatMoney(proforma.total_amount, proforma.currency)} />
      </div>
      {proforma.terms_and_conditions && <div className="document-terms"><b>Conditions</b><div>{proforma.terms_and_conditions}</div></div>}
      <div className="document-print-footer">Document généré par Korgo · Montants en {proforma.currency || 'FCFA'}</div>
      </div>

      <div className="mt-16">
        <div className="text-muted mb-12" style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase' }}>Changer le statut</div>
        <div className="flex" style={{ flexWrap: 'wrap' }}>
          {PROFORMA_STATUS.map((s) => (
            <button key={s} className="btn btn-sm" onClick={() => onStatus(s)}>{s}</button>
          ))}
        </div>
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
