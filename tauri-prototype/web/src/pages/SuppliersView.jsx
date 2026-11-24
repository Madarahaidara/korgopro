import { useCallback, useMemo, useState } from 'react';
import { listSuppliers, saveSupplier, setSupplierActive } from '../api/businessApi';
import { useBusinessData } from '../api/useBusinessData';
import { ActionButton, DataTable, Field, InlineMessage, MetricCard, Modal, PageHeader, Panel, StatusBadge } from '../components/erp';
import { useAuth } from '../context/AuthContext';

const emptyDraft = {
  code: '', name: '', contact_person: '', email: '', phone: '', address: '',
  city: '', country: '', website: '', payment_terms: '', notes: '',
};

function nextCode(suppliers) {
  const max = suppliers.reduce((value, supplier) => {
    const match = String(supplier.code || '').match(/^SUP-(\d+)$/i);
    return match ? Math.max(value, Number(match[1])) : value;
  }, 0);
  return `SUP-${String(max + 1).padStart(4, '0')}`;
}

export default function SuppliersView() {
  const { organizationId } = useAuth();
  const load = useCallback(() => listSuppliers(organizationId, true), [organizationId]);
  const { data, loading, error: loadError, refresh } = useBusinessData(load);
  const suppliers = data || [];
  const [query, setQuery] = useState('');
  const [editing, setEditing] = useState(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [draft, setDraft] = useState(emptyDraft);
  const [saving, setSaving] = useState(false);
  const [busySupplier, setBusySupplier] = useState(null);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const filtered = useMemo(() => suppliers.filter((supplier) => (
    `${supplier.code} ${supplier.name} ${supplier.contact_person || ''} ${supplier.email || ''} ${supplier.phone || ''}`
      .toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())
  )), [query, suppliers]);
  const activeCount = suppliers.filter((supplier) => supplier.active).length;

  const openCreate = () => {
    setEditing(null);
    setDraft({ ...emptyDraft, code: nextCode(suppliers) });
    setEditorOpen(true);
    setError('');
    setNotice('');
  };

  const openEdit = (supplier) => {
    setEditing(supplier);
    setDraft(Object.fromEntries(Object.keys(emptyDraft).map((key) => [key, supplier[key] || ''])));
    setEditorOpen(true);
    setError('');
    setNotice('');
  };

  const save = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const result = await saveSupplier(organizationId, { ...draft, id: editing?.id });
      setEditorOpen(false);
      setEditing(null);
      setNotice(result.message || 'Fiche fournisseur enregistrée.');
      await refresh().catch(() => {});
    } catch (failure) {
      setError(failure.message || 'La fiche fournisseur n’a pas pu être enregistrée.');
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (supplier) => {
    setBusySupplier(supplier.id);
    setError('');
    setNotice('');
    try {
      await setSupplierActive(organizationId, supplier.id, !supplier.active);
      setNotice(supplier.active ? 'Fournisseur désactivé; ses références historiques sont conservées.' : 'Fournisseur réactivé.');
      await refresh().catch(() => {});
    } catch (failure) {
      setError(failure.message || 'Le statut du fournisseur n’a pas pu être modifié.');
    } finally {
      setBusySupplier(null);
    }
  };

  if (loading && !data) return <div className="erp-standalone" role="status">Chargement des fournisseurs…</div>;
  if (!data) return <InlineMessage tone="error">{loadError || 'Impossible de charger les fournisseurs.'}</InlineMessage>;

  return (
    <div className="erp-page">
      <PageHeader title="Fournisseurs" subtitle="Gérez les contacts et conditions de paiement de vos fournisseurs." action={<ActionButton onClick={openCreate}>+ Nouveau fournisseur</ActionButton>} />
      {loadError && <InlineMessage tone="error">{loadError}</InlineMessage>}
      {notice && <InlineMessage tone="success">{notice}</InlineMessage>}
      {error && <InlineMessage tone="error">{error}</InlineMessage>}
      <div className="erp-metrics-grid">
        <MetricCard label="Fournisseurs" value={suppliers.length} detail="Répertoire de l’entreprise" icon="▤" />
        <MetricCard label="Actifs" value={activeCount} detail="Disponibles pour le catalogue" icon="✓" tone="green" />
        <MetricCard label="Désactivés" value={suppliers.length - activeCount} detail="Historique conservé" icon="Ⅱ" tone="amber" />
      </div>
      <Panel title="Répertoire fournisseurs" description="Les fiches restent liées à l’entreprise active.">
        <div className="erp-list-toolbar">
          <input className="erp-control" placeholder="Rechercher un code, une société ou un contact…" value={query} onChange={(event) => setQuery(event.target.value)} />
          <span className="erp-toolbar-count">{filtered.length} résultat(s)</span>
        </div>
        <DataTable columns={[
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Fournisseur' },
          { key: 'contact_person', label: 'Contact', render: (value) => value || '—' },
          { key: 'phone', label: 'Téléphone', render: (value) => value || '—' },
          { key: 'email', label: 'Courriel', render: (value) => value || '—' },
          { key: 'city', label: 'Ville', render: (value) => value || '—' },
          { key: 'active', label: 'État', render: (value) => <StatusBadge>{value ? 'Actif' : 'Inactif'}</StatusBadge> },
          { key: 'actions', label: 'Actions', render: (_, supplier) => <div className="erp-row-actions">
            <button className="erp-table-action" type="button" onClick={() => openEdit(supplier)}>Modifier</button>
            <button className="erp-table-action" type="button" disabled={busySupplier === supplier.id} onClick={() => toggleActive(supplier)}>{supplier.active ? 'Désactiver' : 'Réactiver'}</button>
          </div> },
        ]} rows={filtered} emptyMessage="Aucun fournisseur ne correspond à la recherche." />
      </Panel>
      {editorOpen && <Modal
        title={editing ? `Modifier ${editing.name}` : 'Nouveau fournisseur'}
        onClose={() => { if (!saving) { setEditorOpen(false); setEditing(null); } }}
        footer={<>
          <ActionButton variant="secondary" onClick={() => { setEditorOpen(false); setEditing(null); }} disabled={saving}>Annuler</ActionButton>
          <ActionButton onClick={() => document.getElementById('supplier-form').requestSubmit()} disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</ActionButton>
        </>}
      >
        <form id="supplier-form" className="erp-form-grid" onSubmit={save}>
          <Field label="Code fournisseur" value={draft.code} onChange={(code) => setDraft({ ...draft, code: code.toUpperCase() })} required maxLength="50" pattern="[A-Za-z0-9][A-Za-z0-9_-]*" />
          <Field label="Nom / société" value={draft.name} onChange={(name) => setDraft({ ...draft, name })} required maxLength="200" />
          <Field label="Personne à contacter" value={draft.contact_person} onChange={(contact_person) => setDraft({ ...draft, contact_person })} maxLength="100" />
          <Field label="Courriel" type="email" value={draft.email} onChange={(email) => setDraft({ ...draft, email })} maxLength="100" />
          <Field label="Téléphone" type="tel" value={draft.phone} onChange={(phone) => setDraft({ ...draft, phone })} maxLength="50" />
          <Field label="Conditions de paiement" value={draft.payment_terms} onChange={(payment_terms) => setDraft({ ...draft, payment_terms })} maxLength="100" placeholder="Ex. 30 jours" />
          <Field label="Ville" value={draft.city} onChange={(city) => setDraft({ ...draft, city })} maxLength="100" />
          <Field label="Pays" value={draft.country} onChange={(country) => setDraft({ ...draft, country })} maxLength="100" />
          <Field label="Site web" type="url" value={draft.website} onChange={(website) => setDraft({ ...draft, website })} maxLength="200" />
          <div className="erp-field-span"><Field label="Adresse" value={draft.address} onChange={(address) => setDraft({ ...draft, address })} maxLength="2000" /></div>
          <div className="erp-field-span"><Field label="Notes" value={draft.notes} onChange={(notes) => setDraft({ ...draft, notes })} /></div>
          {error && <div className="erp-field-span"><InlineMessage tone="error">{error}</InlineMessage></div>}
        </form>
      </Modal>}
    </div>
  );
}
