import { useState } from 'react';
import { listUsers, saveUser, toggleUserActive } from '../../api/authApi';
import { formatDate } from '../../api/db';
import { Badge, Modal, toast } from '../ui';
import UserForm from '../UserForm';

const ROLES = ['CAISSIER', 'ASSISTANT', 'GERANT', 'SUPERVISEUR', 'ADMIN'];

export default function UsersTab({ currentUser }) {
  const [users, setUsers] = useState(() => listUsers());
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const refresh = () => setUsers(listUsers());

  /** Active / désactive un compte via les RPC admin Supabase (async). */
  const toggleActive = async (target) => {
    setBusyId(target.id);
    try {
      await toggleUserActive(target.id);
      refresh();
      toast('Statut modifié.');
    } catch (err) {
      toast(err?.message || 'Opération refusée par Supabase.', 'danger');
    } finally {
      setBusyId(null);
      setConfirm(null);
    }
  };

  return (
    <div>
      <div className="flex justify-between mb-12">
        <div>
          <h3 className="admin-section-title">Gestion des utilisateurs</h3>
          <p className="text-muted">Créez des comptes, attribuez des rôles et contrôlez leur statut.</p>
        </div>
        <button className="btn btn-primary" onClick={() => { setEditing(null); setShowForm(true); }}>+ Utilisateur</button>
      </div>

      <div className="card" style={{ padding: 0, overflowX: 'auto', overflowY: 'hidden' }}>
        <table className="table">
          <thead>
            <tr>
              <th>Utilisateur</th>
              <th>Email</th>
              <th>Rôle</th>
              <th>Statut</th>
              <th>Dernière connexion</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>
                  <div className="flex">
                    <div className="avatar">{u.username[0]?.toUpperCase()}</div>
                    <b>{u.username}</b>
                    {u.id === currentUser.id && <Badge status="VOUS" />}
                  </div>
                </td>
                <td>{u.email || '—'}</td>
                <td><Badge status={u.role} /></td>
                <td>{u.active ? <Badge status="ACTIF" /> : <Badge status="INACTIF" />}</td>
                <td>{u.last_login ? formatDate(u.last_login) : 'Jamais'}</td>
                <td>
                  <div className="flex">
                    <button className="btn btn-sm" onClick={() => { setEditing(u); setShowForm(true); }}>Éditer</button>
                    <button
                      className="btn btn-sm"
                      disabled={u.id === currentUser.id}
                      onClick={() => setConfirm(u)}
                    >
                      {u.active ? 'Désactiver' : 'Activer'}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showForm && (
        <UserForm
          user={editing}
          roles={ROLES}
          onSave={() => { refresh(); setShowForm(false); toast('Utilisateur enregistré.'); }}
          onClose={() => setShowForm(false)}
        />
      )}

      {confirm && (
        <Modal title="Confirmation" onClose={() => setConfirm(null)} width={400}>
          <p>{confirm.active ? 'Désactiver' : 'Activer'} l'utilisateur <b>{confirm.username}</b> ?</p>
          <div className="form-actions">
            <button className="btn" onClick={() => setConfirm(null)}>Annuler</button>
            <button
              className="btn btn-primary"
              disabled={busyId === confirm.id}
              onClick={() => toggleActive(confirm)}
            >
              {busyId === confirm.id ? 'Traitement…' : 'Confirmer'}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}