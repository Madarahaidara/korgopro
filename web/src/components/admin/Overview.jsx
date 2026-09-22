import { db, storageStats, formatBytes, formatDate } from '../../api/db';
import { countRecords, BOOT_TIME, formatDuration, getHostInfo, storageUsedPercent } from '../../api/systemApi';
import { listActivityLogs } from '../../api/settingsApi';
import { getSettings } from '../../api/settingsApi';
import { Stat } from '../ui';
import Icon from '../Icon';

// Cartes de statistiques par collection.
const COLLECTIONS = [
  ['users', 'Utilisateurs'],
  ['customers', 'Clients'],
  ['products', 'Produits'],
  ['suppliers', 'Fournisseurs'],
  ['sales', 'Ventes'],
  ['proformas', 'Proformas'],
  ['treasuryAccounts', 'Comptes'],
  ['treasuryMovements', 'Mouvements'],
  ['inventoryMovements', 'Mouvements stock'],
];

export default function Overview() {
  const stats = storageStats();
  const total = countRecords(db.data);
  const activity = listActivityLogs(5);
  const settings = getSettings();
  const host = getHostInfo();

  return (
    <div>
      <h3 className="admin-section-title">Vue d'ensemble du système</h3>
      <p className="text-muted">Résumé global de l'état de l'application et des données.</p>

      <div className="grid grid-4">
        <Stat icon={<Icon name="hardDrive" size={22} />} label="Enregistrements" value={total} color="#2F4255" />
        <Stat icon="" label="Hôte" value={host} color="#3A6B9F" />
        <Stat icon={<Icon name="hardDrive" size={22} />} label="Espace utilisé" value={formatBytes(stats.total)} color="#10b981" />
        <Stat icon={<Icon name="clock" size={22} />} label="Session active" value={formatDuration(Date.now() - BOOT_TIME)} color="#8b5cf6" />
      </div>

      <div className="grid grid-2">
        <div className="admin-block">
          <h4 className="admin-block-title"><Icon name="stock" size={18} style={{ verticalAlign: '-2px' }} /> Données par module</h4>
          <table className="table">
            <thead>
              <tr><th>Module</th><th className="text-right">Enregistrements</th></tr>
            </thead>
            <tbody>
              {COLLECTIONS.map(([key, label]) => {
                const n = Array.isArray(db.data[key]) ? db.data[key].length : 0;
                return (
                  <tr key={key}>
                    <td>{label}</td>
                    <td className="text-right">{n}</td>
                  </tr>
                );
              })}
              <tr>
                <td><b>Total</b></td>
                <td className="text-right"><b>{total}</b></td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="admin-block">
          <h4 className="admin-block-title"><Icon name="hardDrive" size={18} style={{ verticalAlign: '-2px' }} /> Stockage local</h4>
          <div className="storage-total">
            <div style={{ fontSize: 26, fontWeight: 800, color: 'var(--primary)' }}>
              {formatBytes(stats.total)}
            </div>
            <div className="text-muted">
              {storageUsedPercent(stats.total)}% du quota local ( 5 Mo)
            </div>
          </div>
          <div className="storage-list">
            {stats.keys.map((k) => (
              <div className="flex justify-between" key={k.key} style={{ padding: '5px 0' }}>
                <span className="text-muted" style={{ fontSize: 13 }}>{k.key}</span>
                <b style={{ fontSize: 13 }}>{formatBytes(k.size)}</b>
              </div>
            ))}
            {stats.keys.length === 0 && <div className="text-muted">Aucune clé locale.</div>}
          </div>
        </div>
      </div>

      <div className="admin-block">
        <h4 className="admin-block-title"><Icon name="refresh" size={18} style={{ verticalAlign: '-2px' }} /> Activité récente</h4>
        {activity.length === 0 ? (
          <div className="empty" style={{ padding: 24 }}>Aucun événement enregistré.</div>
        ) : (
          <table className="table">
            <thead>
              <tr><th>Horodatage</th><th>Utilisateur</th><th>Action</th></tr>
            </thead>
            <tbody>
              {activity.map((l) => (
                <tr key={l.id}>
                  <td>{new Date(l.timestamp).toLocaleString('fr-FR')}</td>
                  <td><b>{l.user}</b></td>
                  <td>{l.action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="admin-block">
        <h4 className="admin-block-title"><Icon name="building" size={18} style={{ verticalAlign: '-2px' }} /> Société</h4>
        <div className="grid grid-2">
          <InfoItem label="Entreprise" value={settings.company_name || '—'} />
          <InfoItem label="Adresse" value={settings.address || '—'} />
          <InfoItem label="Devise" value={settings.currency || '—'} />
          <InfoItem label="TVA (%)" value={String(settings.tax_rate ?? '')} />
          <InfoItem label="Mise à jour" value={formatDate(new Date().toISOString())} />
        </div>
      </div>
    </div>
  );
}

function InfoItem({ label, value }) {
  return (
    <div className="field">
      <div className="text-muted" style={{ fontSize: 12, fontWeight: 700 }}>{label}</div>
      <b>{value}</b>
    </div>
  );
}