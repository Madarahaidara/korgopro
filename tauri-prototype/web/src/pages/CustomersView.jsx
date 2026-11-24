import { useCallback, useMemo, useState } from 'react';
import { listCustomers, saveCustomer, setCustomerActive } from '../api/businessApi';
import { useBusinessData } from '../api/useBusinessData';
import {
  ActionButton, DataTable, Field, InlineMessage, MetricCard, Modal, PageHeader, Panel, StatusBadge,
} from '../components/erp';
import { formatMoney } from '../data/demoData';
import { useAuth } from '../context/AuthContext';

const emptyDraft = {
  first_name: '', last_name: '', company: '', email: '', phone: '', mobile: '',
  address: '', city: '', country: '', customer_type: 'RETAIL', credit_limit: '0', notes: '',
};

const customerTypes = [
  { value: 'RETAIL', label: 'Particulier' },
  { value: 'WHOLESALE', label: 'Grossiste' },
  { value: 'CORPORATE', label: 'Entreprise' },
];

export default function CustomersView() {
  const { organizationId, settings } = useAuth();
  const load = useCallback(() => listCustomers(organizationId, true), [organizationId]);
  const { data, loading, error: loadError, refresh } = useBusinessData(load);
  const customers = data || [];
  const [query, setQuery] = useState('');
  const [editing, setEditing] = useState(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [draft, setDraft] = useState(emptyDraft);
  const [saving, setSaving] = useState(false);
  const [busyCustomer, setBusyCustomer] = useState(null);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const filtered = useMemo(() => customers.filter((customer) => (
    `${customer.name} ${customer.company || ''} ${customer.email || ''} ${customer.phone || ''}`
      .toLowerCase().includes(query.trim().toLowerCase())
  )), [customers, query]);
  const activeCount = customers.filter((customer) => customer.active).length;
  const outstanding = customers.reduce((sum, customer) => sum + (Number(customer.balance) || 0), 0);
  const creditLimit = customers.reduce((sum, customer) => sum + (Number(customer.credit_limit) || 0), 0);

  const openCreate = () => {
    setEditing(null);
    setEditorOpen(true);
    setDraft(emptyDraft);
    setError('');
    setNotice('');
  };

  const openEdit = (customer) => {
    setEditing(customer);
    setEditorOpen(true);
    setDraft({
      first_name: customer.first_name || '',
      last_name: customer.last_name || '',
      company: customer.company || '',
      email: customer.email || '',
      phone: customer.phone || '',
      mobile: customer.mobile || '',
      address: customer.address || '',
      city: customer.city || '',
      country: customer.country || '',
      customer_type: customer.customer_type || 'RETAIL',
      credit_limit: String(customer.credit_limit ?? 0),
      notes: customer.notes || '',
    });
    setError('');
    setNotice('');
  };

  const save = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const result = await saveCustomer(organizationId, { ...draft, id: editing?.id });
      setEditing(null);
      setEditorOpen(false);
      setNotice(result.message || 'Fiche client enregistrée.');
      await refresh().catch(() => {});
    } catch (failure) {
      setError(failure.message || 'La fiche client n’a pas pu être enregistrée.');
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (customer) => {
    setBusyCustomer(customer.id);
    setError('');
    setNotice('');
    try {
      await setCustomerActive(organizationId, customer.id, !customer.active);
      setNotice(customer.active ? 'Client désactivé. Son historique est conservé.' : 'Client réactivé.');
      await refresh().catch(() => {});
    } catch (failure) {
      setError(failure.message || 'Le statut du client n’a pas pu être modifié.');
    } finally {
      setBusyCustomer(null);
    }
  };

  if (loading && !data) return <div className="erp-standalone" role="status">Chargement des clients…</div>;
  if (!data) return <InlineMessage tone="error">{loadError || 'Impossible de charger les clients.'}</InlineMessage>;

  return (
    <div className="erp-page">
      <PageHeader
        title="Clients"
        subtitle="Gérez les fiches clients et consultez leurs soldes de crédit."
        action={<ActionButton onClick={openCreate}>＋ Nouveau client</ActionButton>}
      />
      {loadError && <InlineMessage tone="error">{loadError}</InlineMessage>}
      {notice && <InlineMessage tone="success">{notice}</InlineMessage>}
      {error && <InlineMessage tone="error">{error}</InlineMessage>}
      <div className="erp-metrics-grid">
        <MetricCard label="Clients" value={customers.length} detail={`${activeCount} actif(s)`} icon="♙" />
        <MetricCard label="Solde client dû" value={formatMoney(outstanding, settings.currency)} detail="Crédits en cours" icon="◷" tone="amber" />
        <MetricCard label="Limites de crédit" value={formatMoney(creditLimit, settings.currency)} detail="Cumul des limites attribuées" icon="◈" tone="blue" />
        <MetricCard label="Désactivés" value={customers.length - activeCount} detail="Historique conservé" icon="✓" tone="green" />
      </div>
      <Panel title="Répertoire clients" description="Les changements sont contrôlés par les permissions de l’entreprise active.">
        <div className="erp-list-toolbar">
          <input className="erp-control" placeholder="Rechercher un nom, une société ou un contact…" value={query} onChange={(event) => setQuery(event.target.value)} />
          <span className="erp-toolbar-count">{filtered.length} résultat(s)</span>
        </div>
        <DataTable columns={[
          { key: 'name', label: 'Client' },
          { key: 'company', label: 'Société', render: (value) => value || '—' },
          { key: 'contact', label: 'Contact', render: (_, customer) => <span>{customer.phone || customer.mobile || '—'}{customer.email && <small className="erp-customer-email">{customer.email}</small>}</span> },
          { key: 'balance', label: 'Solde dû', render: (value) => formatMoney(value, settings.currency) },
          { key: 'credit_limit', label: 'Limite', render: (value) => formatMoney(value, settings.currency) },
          { key: 'status', label: 'État', render: (_, customer) => <StatusBadge>{customer.active ? 'Actif' : 'Inactif'}</StatusBadge> },
          { key: 'actions', label: 'Actions', render: (_, customer) => <div className="erp-row-actions">
            <button className="erp-table-action" type="button" onClick={() => openEdit(customer)}>Modifier</button>
            <button className="erp-table-action" type="button" disabled={busyCustomer === customer.id} onClick={() => toggleActive(customer)}>{customer.active ? 'Désactiver' : 'Réactiver'}</button>
          </div> },
        ]} rows={filtered} />
      </Panel>
      {editorOpen && <Modal
        title={editing ? `Modifier ${editing.name}` : 'Nouveau client'}
        onClose={() => { if (!saving) { setEditing(null); setEditorOpen(false); } }}
        footer={<>
          <ActionButton variant="secondary" onClick={() => { setEditing(null); setEditorOpen(false); }} disabled={saving}>Annuler</ActionButton>
          <ActionButton onClick={() => document.getElementById('customer-form').requestSubmit()} disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</ActionButton>
        </>}
      >
        <form id="customer-form" className="erp-form-grid" onSubmit={save}>
          <Field label="Prénom" value={draft.first_name} onChange={(value) => setDraft({ ...draft, first_name: value })} required maxLength="100" />
          <Field label="Nom" value={draft.last_name} onChange={(value) => setDraft({ ...draft, last_name: value })} required maxLength="100" />
          <Field label="Société" value={draft.company} onChange={(value) => setDraft({ ...draft, company: value })} maxLength="200" />
          <Field label="Type de client" value={draft.customer_type} onChange={(value) => setDraft({ ...draft, customer_type: value })} options={customerTypes} />
          <Field label="Courriel" type="email" value={draft.email} onChange={(value) => setDraft({ ...draft, email: value })} maxLength="100" />
          <Field label="Téléphone" type="tel" value={draft.phone} onChange={(value) => setDraft({ ...draft, phone: value })} maxLength="50" />
          <Field label="Téléphone secondaire" type="tel" value={draft.mobile} onChange={(value) => setDraft({ ...draft, mobile: value })} maxLength="50" />
          <Field label={`Limite de crédit (${settings.currency})`} type="number" min="0" step="0.01" value={draft.credit_limit} onChange={(value) => setDraft({ ...draft, credit_limit: value })} />
          <div className="erp-field-span"><Field label="Adresse" value={draft.address} onChange={(value) => setDraft({ ...draft, address: value })} maxLength="1000" /></div>
          <Field label="Ville" value={draft.city} onChange={(value) => setDraft({ ...draft, city: value })} maxLength="100" />
          <Field label="Pays" value={draft.country} onChange={(value) => setDraft({ ...draft, country: value })} maxLength="100" />
          <div className="erp-field-span"><Field label="Notes" value={draft.notes} onChange={(value) => setDraft({ ...draft, notes: value })} /></div>
          {error && <div className="erp-field-span"><InlineMessage tone="error">{error}</InlineMessage></div>}
        </form>
      </Modal>}
    </div>
  );
}
