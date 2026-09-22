import { useState } from 'react';
import { getSettings, saveSettings } from '../api/settingsApi';
import { toast } from '../components/ui';
import Icon from '../components/Icon';

export default function Settings() {
  const [settings, setSettings] = useState(() => getSettings());
  const set = (k) => (e) => setSettings({ ...settings, [k]: e.target.value });

  const save = () => {
    saveSettings(settings);
    toast('Paramètres enregistrés.');
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-title">Paramètres</div>
          <div className="page-subtitle">Configurez votre entreprise et vos factures.</div>
        </div>
        <button className="btn btn-primary" onClick={save}>Enregistrer</button>
      </div>

      <div className="grid grid-2">
        <div className="card">
          <div className="card-title"><Icon name="building" size={16} style={{ verticalAlign: '-2px' }} /> Informations de l'entreprise</div>
          <div className="field">
            <label>Nom de l'entreprise</label>
            <input className="input" value={settings.company_name || ''} onChange={set('company_name')} />
          </div>
          <div className="field">
            <label>Adresse</label>
            <input className="input" value={settings.address || ''} onChange={set('address')} />
          </div>
          <div className="field">
            <label>Téléphone</label>
            <input className="input" value={settings.phone || ''} onChange={set('phone')} />
          </div>
          <div className="field">
            <label>Email</label>
            <input className="input" value={settings.email || ''} onChange={set('email')} />
          </div>
        </div>

        <div className="card">
          <div className="card-title"><Icon name="receipt" size={16} style={{ verticalAlign: '-2px' }} /> Facturation</div>
          <div className="field">
            <label>Devise</label>
            <input className="input" value={settings.currency || ''} onChange={set('currency')} />
          </div>
          <div className="field">
            <label>Taux de TVA (%)</label>
            <input className="input" type="number" min="0" max="100" value={settings.tax_rate ?? 0} onChange={set('tax_rate')} />
          </div>
          <div className="field">
            <label>Préfixe facture</label>
            <input className="input" value={settings.invoice_prefix || ''} onChange={set('invoice_prefix')} />
          </div>
          <div className="field">
            <label>Préfixe proforma</label>
            <input className="input" value={settings.proforma_prefix || ''} onChange={set('proforma_prefix')} />
          </div>
          <div className="field">
            <label>Pied de facture</label>
            <textarea className="textarea" value={settings.invoice_footer || ''} onChange={set('invoice_footer')} />
          </div>
        </div>
      </div>
    </div>
  );
}