import { useState } from 'react';
import { listCustomers, saveCustomer, deleteCustomer } from '../api/catalogApi';
import { formatMoney } from '../api/db';
import { Badge, Modal, toast } from '../components/ui';
import CustomerForm from '../components/CustomerForm';

export default function Customers() {
  const [customers, setCustomers] = useState(() => listCustomers());
  const [query, setQuery] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);

  const searched = customers.filter((c) => {
    const q = query.toLowerCase();
    return c.full_name.toLowerCase().includes(q) || c.code.toLowerCase().includes(q) || (c.company || '').toLowerCase().includes(q);
  });

  const refresh = () => setCustomers(listCustomers());

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-title">Clients</div>
          <div className="page-subtitle">Gérez votre portefeuille clients.</div>
        </div>
        <div className="flex">
          <input className="input" placeholder="Rechercher…" style={{ width: 200 }} value={query} onChange={(e) => setQuery(e.target.value)} />
          <button className="btn btn-primary" onClick={() => { setEditing(null); setShowForm(true); }}>+ Client</button>
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflowX: 'auto', overflowY: 'hidden' }}>
        <table className="table">
          <thead>
            <tr>
              <th>Code</th>
              <th>Nom</th>
              <th>Société</th>
              <th>Contact</th>
              <th>Type</th>
              <th className="text-right">Découvert</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {searched.map((c) => (
              <tr key={c.id}>
                <td className="text-muted">{c.code}</td>
                <td><b>{c.full_name}</b></td>
                <td>{c.company || '—'}</td>
                <td>{c.phone || c.email || '—'}</td>
                <td><Badge status={c.customer_type} /></td>
                <td className="text-right">{formatMoney(c.credit_limit)}</td>
                <td>
                  <div className="flex">
                    <button className="btn btn-sm" onClick={() => { setEditing(c); setShowForm(true); }}>Éditer</button>
                    <button className="btn btn-sm btn-danger" onClick={() => setConfirmDelete(c)}>Suppr.</button>
                  </div>
                </td>
              </tr>
            ))}
            {searched.length === 0 && <tr><td colSpan={7}><div className="empty">Aucun client.</div></td></tr>}
          </tbody>
        </table>
      </div>

      {showForm && (
        <CustomerForm
          customer={editing}
          onSave={() => { refresh(); setShowForm(false); toast('Client enregistré.'); }}
          onClose={() => setShowForm(false)}
        />
      )}

      {confirmDelete && (
        <Modal title="Confirmation" onClose={() => setConfirmDelete(null)} width={400}>
          <p>Supprimer le client <b>{confirmDelete.full_name}</b> ?</p>
          <div className="form-actions">
            <button className="btn" onClick={() => setConfirmDelete(null)}>Annuler</button>
            <button
              className="btn btn-danger"
              onClick={() => { deleteCustomer(confirmDelete.id); setConfirmDelete(null); refresh(); toast('Client supprimé.'); }}
            >
              Supprimer
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}