import { useState } from 'react';
import { listActivityLogs } from '../../api/settingsApi';
import { Badge } from '../ui';

export default function ActivityTab() {
  const [logs] = useState(() => listActivityLogs(200));
  const [query, setQuery] = useState('');

  const filtered = logs.filter((l) => {
    const q = query.toLowerCase();
    return l.user.toLowerCase().includes(q) || l.action.toLowerCase().includes(q);
  });

  return (
    <div>
      <div className="flex justify-between mb-12">
        <div>
          <h3 className="admin-section-title">Journal d'activité</h3>
          <p className="text-muted">Traçabilité des actions réalisées sur le système.</p>
        </div>
        <input className="input" placeholder="Filtrer…" style={{ width: 220 }} value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>

      <div className="card" style={{ padding: 0, overflowX: 'auto', overflowY: 'hidden' }}>
        <table className="table">
          <thead>
            <tr>
              <th>Horodatage</th>
              <th>Utilisateur</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((l) => (
              <tr key={l.id}>
                <td>{new Date(l.timestamp).toLocaleString('fr-FR')}</td>
                <td>
                  <div className="flex">
                    <div className="avatar" style={{ width: 26, height: 26, fontSize: 12 }}>
                      {l.user[0]?.toUpperCase()}
                    </div>
                    <b>{l.user}</b>
                  </div>
                </td>
                <td>{l.action}</td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan={3}><div className="empty">Aucun événement trouvé.</div></td></tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="text-muted mt-8">Affichage des {filtered.length} derniers événements sur {logs.length}.</div>
    </div>
  );
}