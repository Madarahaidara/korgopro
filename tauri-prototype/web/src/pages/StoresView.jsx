import { useCallback, useState } from 'react';
import { listStores, saveStore, setStoreActive } from '../api/businessApi';
import { useBusinessData } from '../api/useBusinessData';
import {
  ActionButton, DataTable, Field, InlineMessage, MetricCard, Modal, PageHeader, Panel, StatusBadge,
} from '../components/erp';
import { useAuth } from '../context/AuthContext';

const emptyStore = { code: '', name: '', address: '', phone: '', manager_name: '', notes: '' };

export default function StoresView() {
  const { organizationId, refreshStores } = useAuth();
  const load = useCallback(() => listStores(organizationId, true), [organizationId]);
  const { data, loading, error: loadError, refresh } = useBusinessData(load);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingStore, setEditingStore] = useState(null);
  const [draft, setDraft] = useState(emptyStore);
  const [saving, setSaving] = useState(false);
  const [busyStore, setBusyStore] = useState(null);
  const [notice, setNotice] = useState('');
  const [noticeTone, setNoticeTone] = useState('success');

  const stores = data || [];
  const activeStores = stores.filter((store) => store.active);

  const openCreate = () => {
    setEditingStore(null);
    setDraft(emptyStore);
    setNotice('');
    setEditorOpen(true);
  };

  const openEdit = (store) => {
    setEditingStore(store);
    setDraft({
      code: store.code || '',
      name: store.name || '',
      address: store.address || '',
      phone: store.phone || '',
      manager_name: store.manager_name || '',
      notes: store.notes || '',
    });
    setNotice('');
    setEditorOpen(true);
  };

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setNotice('');
    try {
      const result = await saveStore(organizationId, { ...draft, id: editingStore?.id });
      setEditorOpen(false);
      setEditingStore(null);
      setNotice(result.message || 'Magasin enregistré.');
      setNoticeTone('success');
      await refresh().catch(() => {});
      await refreshStores().catch(() => {});
    } catch (failure) {
      setNotice(failure.message || 'Le magasin n’a pas pu être enregistré.');
      setNoticeTone('error');
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (store) => {
    const nextActive = !store.active;
    if (!nextActive && !window.confirm(`Désactiver le magasin ${store.name} ? Les magasins avec historique, stock ou rôle par défaut sont protégés.`)) return;
    setBusyStore(store.id);
    setNotice('');
    try {
      const result = await setStoreActive(organizationId, store.id, nextActive);
      setNotice(result.message || 'État du magasin mis à jour.');
      setNoticeTone('success');
      await refresh().catch(() => {});
      await refreshStores().catch(() => {});
    } catch (failure) {
      setNotice(failure.message || 'Impossible de modifier l’état du magasin.');
      setNoticeTone('error');
    } finally {
      setBusyStore(null);
    }
  };

  if (loading && !data) return <div className="erp-standalone" role="status">Chargement des magasins…</div>;
  if (!data) return <InlineMessage tone="error">{loadError || 'Impossible de charger les magasins.'}</InlineMessage>;

  return (
    <div className="erp-page">
      <PageHeader
        title="Gestion des magasins"
        subtitle="Gérez les points de vente et les stocks associés à l’entreprise active."
        action={<ActionButton onClick={openCreate}>Nouveau magasin</ActionButton>}
      />
      {loadError && <InlineMessage tone="error">{loadError}</InlineMessage>}
      {notice && <InlineMessage tone={noticeTone}>{notice}</InlineMessage>}
      <div className="erp-metrics-grid erp-metrics-3">
        <MetricCard label="Magasins" value={stores.length} detail="Tous les magasins" icon="⌂" />
        <MetricCard label="Actifs" value={activeStores.length} detail="Disponibles dans le sélecteur" icon="✓" tone="green" />
        <MetricCard label="Inactifs" value={stores.length - activeStores.length} detail="Historique conservé" icon="◷" tone="amber" />
      </div>
      <Panel title="Magasins de l’entreprise" description="Le magasin par défaut conserve l’association des anciennes données sans magasin.">
        <DataTable columns={[
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Nom' },
          { key: 'address', label: 'Adresse', render: (value) => value || '—' },
          { key: 'phone', label: 'Téléphone', render: (value) => value || '—' },
          { key: 'is_default', label: 'Rôle', render: (value) => value ? <StatusBadge>Par défaut</StatusBadge> : '—' },
          { key: 'active', label: 'Statut', render: (value) => <StatusBadge>{value ? 'Actif' : 'Inactif'}</StatusBadge> },
          { key: 'actions', label: 'Actions', render: (_, store) => <div className="erp-row-actions">
            <button className="erp-table-action" type="button" onClick={() => openEdit(store)}>Modifier</button>
            <button className="erp-table-action" type="button" disabled={busyStore === store.id || (store.active && store.is_default)} onClick={() => toggleActive(store)}>{busyStore === store.id ? 'Mise à jour…' : store.active ? 'Désactiver' : 'Réactiver'}</button>
          </div> },
        ]} rows={stores} />
      </Panel>

      {editorOpen && <Modal
        title={editingStore ? `Modifier ${editingStore.name}` : 'Nouveau magasin'}
        onClose={() => { if (!saving) setEditorOpen(false); }}
        footer={<>
          <ActionButton variant="secondary" onClick={() => setEditorOpen(false)} disabled={saving}>Annuler</ActionButton>
          <ActionButton onClick={() => document.getElementById('store-form').requestSubmit()} disabled={saving}>
            {saving ? 'Enregistrement…' : 'Enregistrer'}
          </ActionButton>
        </>}
      >
        <form id="store-form" className="erp-form-grid" onSubmit={submit}>
          <Field label="Code magasin" value={draft.code} onChange={(code) => setDraft({ ...draft, code: code.toUpperCase() })} maxLength="50" required />
          <Field label="Nom du magasin" value={draft.name} onChange={(name) => setDraft({ ...draft, name })} maxLength="200" required />
          <Field label="Téléphone" value={draft.phone} onChange={(phone) => setDraft({ ...draft, phone })} maxLength="50" />
          <Field label="Responsable" value={draft.manager_name} onChange={(manager_name) => setDraft({ ...draft, manager_name })} maxLength="150" />
          <div className="erp-field-span"><Field label="Adresse" value={draft.address} onChange={(address) => setDraft({ ...draft, address })} /></div>
          <div className="erp-field-span"><Field label="Notes" value={draft.notes} onChange={(notes) => setDraft({ ...draft, notes })} /></div>
          {editingStore?.is_default && <p className="erp-field-span erp-modal-copy">Ce magasin est le magasin par défaut. Cette association conserve l’accès aux anciennes données sans magasin rattaché.</p>}
        </form>
      </Modal>}
    </div>
  );
}
