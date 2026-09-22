import { useEffect, useState } from 'react';
import { getHostInfo, getBrowserInfo, getUptime, getBootTimeISO, simulateHealthCheck, formatDuration, countRecords } from '../../api/systemApi';
import { db, storageStats, formatBytes } from '../../api/db';
import { Stat } from '../ui';
import { listUsers } from '../../api/authApi';
import Icon from '../Icon';

export default function ServerStatus() {
  const [health, setHealth] = useState({ status: 'CHECKING' });
  const [, setTick] = useState(0);
  const host = getHostInfo();

  // Simule une vérification de santé au montage.
  useEffect(() => {
    let mounted = true;
    simulateHealthCheck().then((h) => {
      if (mounted) setHealth(h);
    });
    return () => { mounted = false; };
  }, []);

  // Rafraîchit l'uptime toutes les secondes.
  useEffect(() => {
    const t = setInterval(() => setTick((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, []);

  const users = listUsers();
  const stats = storageStats();

  const online = health.status === 'UP';

  return (
    <div>
      <h3 className="admin-section-title">État du serveur</h3>
      <p className="text-muted">
        Korgo Pro Web tourne actuellement en mode <b>frontend local</b> : les données
        sont stockées dans votre navigateur. Les indicateurs ci-dessous reflètent
        cette architecture et préparent un futur déploiement avec backend.
      </p>

      <div className={`server-pill ${online ? 'ok' : health.status === 'CHECKING' ? 'checking' : 'down'}`}>
        <span className="server-dot" />
        {online ? 'Serveur opérationnel' : health.status === 'CHECKING' ? 'Vérification…' : 'Hors ligne'}
      </div>

      <div className="grid grid-4" style={{ marginTop: 16 }}>
        <Stat icon={<Icon name="checkCircle" size={22} />} label="Statut API" value={online ? 'UP' : '—'} color="#10b981" />
        <Stat icon={<Icon name="zap" size={22} />} label="Latence" value={health.latency != null ? `${health.latency} ms` : '…'} color="#f59e0b" />
        <Stat icon={<Icon name="clock" size={22} />} label="Uptime" value={formatDuration(getUptime())} color="#2F4255" />
        <Stat icon={<Icon name="monitor" size={22} />} label="Mode" value="Frontend" color="#8b5cf6" />
      </div>

      <div className="admin-block">
        <h4 className="admin-block-title"><Icon name="globe" size={18} style={{ verticalAlign: '-2px' }} /> Détails de la connexion</h4>
        <table className="table">
          <tbody>
            <InfoRow label="Hôte" value={host} />
            <InfoRow label="Origine" value={typeof window !== 'undefined' ? window.location.origin : '—'} />
            <InfoRow label="Navigateur" value={getBrowserInfo()} />
            <InfoRow label="Démarrage de session" value={new Date(getBootTimeISO()).toLocaleString('fr-FR')} />
            <InfoRow label="Sert par" value={health.served_by || '—'} />
            <InfoRow label="Version API" value="0.1.0" />
          </tbody>
        </table>
      </div>

      <div className="admin-block">
        <h4 className="admin-block-title"><Icon name="chart" size={18} style={{ verticalAlign: '-2px' }} /> Charge des données</h4>
        <div className="grid grid-3">
          <InfoBox label="Enregistrements" value={countRecords(db.data)} />
          <InfoBox label="Utilisateurs" value={users.length} />
          <InfoBox label="Espace local" value={formatBytes(stats.total)} />
        </div>
        <div className="text-muted mt-8" style={{ fontSize: 12 }}>
          En mode backend, ces valeurs proviendraient des relevés serveur (CPU, RAM, connexions).
        </div>
      </div>
    </div>
  );
}

function InfoRow({ label, value }) {
  return (
    <tr>
      <td style={{ width: 200 }}><b>{label}</b></td>
      <td style={{ wordBreak: 'break-all' }}>{value}</td>
    </tr>
  );
}

function InfoBox({ label, value }) {
  return (
    <div className="card" style={{ textAlign: 'center', padding: 16 }}>
      <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--primary)' }}>{value}</div>
      <div className="text-muted">{label}</div>
    </div>
  );
}