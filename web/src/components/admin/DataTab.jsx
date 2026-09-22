import { useRef, useState } from 'react';
import { exportDatabase, importDatabase, resetDB, storageStats, formatBytes } from '../../api/db';
import { listCacheKeys } from '../../api/systemApi';
import { toast, Modal } from '../ui';
import Icon from '../Icon';

export default function DataTab() {
  const fileRef = useRef(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const [stats, setStats] = useState(() => storageStats());
  const cacheKeys = listCacheKeys();

  const refresh = () => setStats(storageStats());

  const handleExport = () => {
    exportDatabase();
    toast('Sauvegarde téléchargée.');
  };

  const handleImport = (file) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        importDatabase(String(e.target.result || ''));
        toast('Données importées avec succès.');
        refresh();
      } catch (err) {
        toast(err.message || 'Import échoué.', 'danger');
      }
    };
    reader.readAsText(file);
  };

  return (
    <div>
      <h3 className="admin-section-title">Gestion des données</h3>
      <p className="text-muted">
        Sauvegardez, restaurez ou nettoyez les données locales de l'application.
      </p>

      <div className="grid grid-2">
        <div className="admin-block">
          <h4 className="admin-block-title"><Icon name="export" size={18} style={{ verticalAlign: '-2px' }} /> Export / Sauvegarde</h4>
          <p className="text-muted">Téléchargez une copie complète de la base locale au format JSON.</p>
          <button className="btn btn-primary" onClick={handleExport}>Exporter la base</button>
        </div>

        <div className="admin-block">
          <h4 className="admin-block-title"><Icon name="import" size={18} style={{ verticalAlign: '-2px' }} /> Import / Restauration</h4>
          <p className="text-muted">Restaurez une sauvegarde précédemment exportée.</p>
          <input
            ref={fileRef}
            type="file"
            accept="application/json, .json"
            style={{ display: 'none' }}
            onChange={(e) => { handleImport(e.target.files[0]); e.target.value = ''; }}
          />
          <button className="btn" onClick={() => fileRef.current?.click()}>Importer un fichier</button>
        </div>

        <div className="admin-block">
          <h4 className="admin-block-title"> Stockage local</h4>
          <div className="flex justify-between"><span className="text-muted">Taille totale</span><b>{formatBytes(stats.total)}</b></div>
          {stats.keys.map((k) => (
            <div className="flex justify-between" key={k.key}>
              <span className="text-muted" style={{ fontSize: 13 }}>{k.key}</span>
              <span style={{ fontSize: 13 }}>{formatBytes(k.size)}</span>
            </div>
          ))}
          <div className="text-muted" style={{ fontSize: 12 }}>Clés : {cacheKeys.join(', ') || 'aucune'}</div>
        </div>

        <div className="admin-block" style={{ borderColor: '#fecaca' }}>
          <h4 className="admin-block-title" style={{ color: 'var(--danger)' }}><Icon name="broom" size={18} style={{ verticalAlign: '-2px' }} /> Zone de danger</h4>
          <p className="text-muted">
            Réinitialise entièrement la base de démonstration. Cette action est irréversible.
          </p>
          <button className="btn btn-danger" onClick={() => setConfirmReset(true)}>Réinitialiser la base</button>
          <button
            className="btn"
            style={{ marginLeft: 8 }}
            onClick={() => { try { localStorage.clear(); toast('Cache vidé.'); } catch (e) { toast('Vidage impossible.', 'danger'); } }}
          >
            Vider le cache
          </button>
        </div>
      </div>

      {confirmReset && (
        <Modal title="Confirmation" onClose={() => setConfirmReset(false)} width={420}>
          <p>
            Réinitialiser la base ? Toutes les données locales de démonstration seront
            remplacées par les valeurs par défaut.
          </p>
          <div className="form-actions">
            <button className="btn" onClick={() => setConfirmReset(false)}>Annuler</button>
            <button
              className="btn btn-danger"
              onClick={() => {
                resetDB();
                setConfirmReset(false);
                toast('Base réinitialisée.');
                // Recharge après un court délai pour repartir sur une base propre.
                setTimeout(() => window.location.reload(), 500);
              }}
            >
              Réinitialiser
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}