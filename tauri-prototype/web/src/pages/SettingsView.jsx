import { useCallback, useEffect, useState } from 'react';
import { loadSettings, saveSettings } from '../api/businessApi';
import { useBusinessData } from '../api/useBusinessData';
import { ActionButton, Field, InlineMessage, PageHeader, Panel, Tabs } from '../components/erp';
import { useAuth } from '../context/AuthContext';

const settingTabs = ['Entreprise', 'Général', 'Facturation'];

export default function SettingsView() {
  const { organizationId, refreshBusinessContext } = useAuth();
  const load = useCallback(() => loadSettings(organizationId), [organizationId]);
  const { data: loadedSettings, loading, error: loadError, refresh } = useBusinessData(load);
  const [tab, setTab] = useState(settingTabs[0]);
  const [settings, setSettings] = useState(null);
  const [savedSettings, setSavedSettings] = useState(null);
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (loadedSettings) {
      setSettings(loadedSettings);
      setSavedSettings(loadedSettings);
    }
  }, [loadedSettings]);

  const dirty = Boolean(settings && savedSettings && Object.keys(settings).some((key) => settings[key] !== savedSettings[key]));
  const update = (key, value) => setSettings((current) => ({ ...current, [key]: value }));

  const save = async () => {
    setSaving(true);
    setNotice('');
    try {
      await saveSettings(organizationId, settings);
      setSavedSettings(settings);
      await refreshBusinessContext();
      setNotice('Paramètres enregistrés dans Supabase.');
      await refresh().catch(() => {});
    } catch (failure) {
      setNotice(failure.message || 'Les paramètres n’ont pas pu être enregistrés.');
    } finally {
      setSaving(false);
    }
  };

  const cancel = () => {
    setSettings(savedSettings);
    setNotice('Modifications annulées.');
  };

  if (loading && !loadedSettings) return <div className="erp-standalone" role="status">Chargement des paramètres…</div>;
  if (!settings) return <InlineMessage tone="error">{loadError || 'Impossible de charger les paramètres.'}</InlineMessage>;

  return (
    <div className="erp-page">
      <PageHeader title="Paramètres" subtitle="Informations et préférences de l’entreprise active." />
      {loadError && <InlineMessage tone="error">{loadError}</InlineMessage>}
      {notice && <InlineMessage tone={notice.includes('enregistrés') ? 'success' : 'info'}>{notice}</InlineMessage>}
      <Panel className="erp-tab-panel">
        <Tabs items={settingTabs} value={tab} onChange={setTab} />
        {tab === 'Entreprise' && <div className="erp-settings-content">
          <div className="erp-panel-intro"><h3>Informations de l’entreprise</h3><p>Ces informations sont partagées par les applications autorisées de cette entreprise.</p></div>
          <div className="erp-form-grid">
            <Field label="Nom de l’entreprise" value={settings.companyName} onChange={(value) => update('companyName', value)} required />
            <Field label="Code entreprise" value={settings.companyCode} onChange={(value) => update('companyCode', value)} />
            <Field label="Adresse e-mail" type="email" value={settings.email} onChange={(value) => update('email', value)} />
            <Field label="Téléphone" value={settings.phone} onChange={(value) => update('phone', value)} />
            <div className="erp-field-span"><Field label="Adresse" value={settings.address} onChange={(value) => update('address', value)} /></div>
          </div>
        </div>}
        {tab === 'Général' && <div className="erp-settings-content">
          <div className="erp-panel-intro"><h3>Préférences générales</h3><p>Devise et préférences d’affichage de l’entreprise.</p></div>
          <div className="erp-form-grid">
            <Field label="Devise" value={settings.currency} onChange={(value) => update('currency', value)} options={['FCFA', 'EUR', 'USD']} />
            <Field label="Langue" value={settings.language} onChange={(value) => update('language', value)} options={['Français', 'English']} />
            <Field label="Thème" value={settings.theme} onChange={(value) => update('theme', value)} options={['Clair', 'Sombre', 'Système']} />
          </div>
        </div>}
        {tab === 'Facturation' && <div className="erp-settings-content">
          <div className="erp-panel-intro"><h3>Paramètres de facturation</h3><p>Préfixes des documents et taux de taxe de l’entreprise.</p></div>
          <div className="erp-form-grid">
            <Field label="Taux de taxe (%)" type="number" min="0" max="100" step="0.01" value={settings.taxRate} onChange={(value) => update('taxRate', value)} />
            <Field label="Préfixe de facture" value={settings.invoicePrefix} onChange={(value) => update('invoicePrefix', value)} />
            <Field label="Préfixe pro forma" value={settings.proformaPrefix} onChange={(value) => update('proformaPrefix', value)} />
            <div className="erp-field-span"><Field label="Pied de page des factures" value={settings.invoiceFooter} onChange={(value) => update('invoiceFooter', value)} /></div>
          </div>
        </div>}
        <div className="erp-settings-actions">
          <span className={dirty ? 'erp-dirty-indicator' : 'erp-clean-indicator'}><i />{dirty ? 'Modifications non enregistrées' : 'Aucune modification'}</span>
          <div>
            <ActionButton variant="secondary" onClick={cancel} disabled={!dirty || saving}>Annuler</ActionButton>
            <ActionButton onClick={save} disabled={!dirty || saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</ActionButton>
          </div>
        </div>
      </Panel>
    </div>
  );
}
