import { useCallback, useEffect, useMemo, useState } from 'react';
import { convertProforma, createProforma, listCustomers, listProducts, listProformas, loadProformaDetails, setProformaStatus } from '../api/businessApi';
import { useBusinessData } from '../api/useBusinessData';
import {
  ActionButton, DataTable, Field, InlineMessage, MetricCard, Modal, PageHeader, Panel, StatusBadge,
} from '../components/erp';
import { formatMoney } from '../data/demoData';
import { useAuth } from '../context/AuthContext';
import { downloadCsv } from '../utils/downloadCsv';

export default function ProformaInvoice() {
  const { organizationId, storeId, selectedStore, selectedOrganization, settings } = useAuth();
  const permissions = selectedOrganization?.permissions || [];
  const canExport = permissions.includes('export_data');
  const load = useCallback(async () => {
    const [documents, customers, products] = await Promise.all([
      listProformas(organizationId, null),
      listCustomers(organizationId),
      listProducts(organizationId, storeId, selectedStore?.is_default),
    ]);
    return { documents, customers, products };
  }, [organizationId, selectedStore?.is_default, storeId]);
  const { data, loading, error: loadError, refresh } = useBusinessData(load);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('Tous');
  const [showForm, setShowForm] = useState(false);
  const [notice, setNotice] = useState('');
  const [noticeTone, setNoticeTone] = useState('success');
  const [saving, setSaving] = useState(false);
  const [printDocument, setPrintDocument] = useState(null);
  const [printLoading, setPrintLoading] = useState(false);
  const [printError, setPrintError] = useState('');
  const [busyDocument, setBusyDocument] = useState(null);
  const [draft, setDraft] = useState({ customerId: '', items: [{ productId: '', quantity: '1' }], validity: '7', object: '' });

  const documents = data?.documents || [];
  const customers = data?.customers || [];
  const products = data?.products || [];
  const filtered = useMemo(() => documents.filter((item) => (
    (status === 'Tous' || item.status === status)
    && `${item.id} ${item.customer}`.toLowerCase().includes(query.toLowerCase())
  )), [documents, query, status]);
  const selectedCustomer = customers.find((item) => String(item.id) === String(draft.customerId));
  const estimateBase = draft.items.reduce((sum, line) => {
    const product = products.find((item) => String(item.id) === String(line.productId));
    return sum + (product?.price || 0) * (Number(line.quantity) || 0);
  }, 0);
  const taxRate = Number(selectedOrganization?.tax_rate) || 0;
  const estimate = estimateBase + Number((estimateBase * taxRate / 100).toFixed(2));
  const exportProformas = () => downloadCsv(
    `proformas-${selectedOrganization?.code || 'entreprise'}`,
    ['N° pro forma', 'Client', 'Date', 'Valide jusqu’au', 'Montant', 'Statut', 'Devise'],
    filtered.map((document) => [document.id, document.customer, document.date, document.due, document.amount, document.status, document.currency || settings.currency]),
  );

  useEffect(() => {
    if (data && products.length && draft.items.some((item) => !item.productId)) {
      setDraft((current) => ({
        ...current,
        items: current.items.map((item) => item.productId ? item : { ...item, productId: String(products[0].id) }),
      }));
    }
    if (data && !draft.customerId && customers.length) {
      setDraft((current) => ({ ...current, customerId: String(customers[0].id) }));
    }
  }, [customers, data, draft.customerId, draft.items, products]);

  const updateDraftItem = (index, key, value) => {
    setDraft((current) => ({
      ...current,
      items: current.items.map((item, itemIndex) => itemIndex === index ? { ...item, [key]: value } : item),
    }));
  };

  const addDraftItem = () => {
    setDraft((current) => ({
      ...current,
      items: [...current.items, {
        productId: String(products.find((product) => !current.items.some((item) => String(item.productId) === String(product.id)))?.id || ''),
        quantity: '1',
      }],
    }));
  };

  const saveDraft = async (event) => {
    event.preventDefault();
    setNotice('');
    if (!draft.customerId) {
      setNotice('Sélectionnez un client pour créer une pro forma convertible en facture.');
      setNoticeTone('error');
      return;
    }
    setSaving(true);
    try {
      const validUntil = new Date();
      validUntil.setDate(validUntil.getDate() + Number(draft.validity));
      const result = await createProforma({
        organizationId,
        customerId: draft.customerId ? Number(draft.customerId) : null,
        items: draft.items,
        validUntil: validUntil.toISOString().slice(0, 10),
        notes: draft.object,
      });
      setShowForm(false);
      setNotice(`${result.proforma_number} créée · ${formatMoney(result.total_amount, settings.currency)}.`);
      setNoticeTone('success');
      await refresh().catch(() => {});
    } catch (failure) {
      setNotice(failure.message || 'La pro forma n’a pas pu être créée.');
      setNoticeTone('error');
    } finally {
      setSaving(false);
    }
  };

  const openDocument = async (document) => {
    setPrintDocument(null);
    setPrintError('');
    setPrintLoading(true);
    try {
      setPrintDocument(await loadProformaDetails(organizationId, document.proforma_id));
    } catch (failure) {
      setPrintError(failure.message || 'Impossible de charger cette pro forma.');
    } finally {
      setPrintLoading(false);
    }
  };

  const changeStatus = async (document, nextStatus) => {
    if (!nextStatus || nextStatus === document.status) return;
    setNotice('');
    setBusyDocument(document.proforma_id);
    try {
      await setProformaStatus(organizationId, document.proforma_id, nextStatus);
      setNotice(`Statut de ${document.id} mis à jour.`);
      setNoticeTone('success');
      await refresh().catch(() => {});
    } catch (failure) {
      setNotice(failure.message || 'Impossible de modifier le statut.');
      setNoticeTone('error');
    } finally {
      setBusyDocument(null);
    }
  };

  const convertDocument = async (document) => {
    if (!window.confirm(`Convertir ${document.id} en facture ? Cette opération déduira le stock et créera un solde client.`)) return;
    setNotice('');
    setBusyDocument(document.proforma_id);
    try {
      const result = await convertProforma(organizationId, document.proforma_id, storeId);
      setNotice(`${document.id} convertie en facture ${result.sale_number}.`);
      setNoticeTone('success');
      await refresh().catch(() => {});
    } catch (failure) {
      setNotice(failure.message || 'Impossible de convertir cette pro forma.');
      setNoticeTone('error');
    } finally {
      setBusyDocument(null);
    }
  };

  if (loading && !data) return <div className="erp-standalone" role="status">Chargement des pro formas…</div>;
  if (!data) return <InlineMessage tone="error">{loadError || 'Impossible de charger les pro formas.'}</InlineMessage>;

  return (
    <div className="erp-page">
      <PageHeader title="Factures Pro Forma" subtitle="Préparez vos propositions commerciales enregistrées dans Supabase." action={<>
        {canExport && <ActionButton variant="secondary" onClick={exportProformas}>Exporter CSV</ActionButton>}
        <ActionButton onClick={() => { setNotice(''); setShowForm(true); }}>＋ Nouvelle pro forma</ActionButton>
      </>} />
      {loadError && <InlineMessage tone="error">{loadError}</InlineMessage>}
      {notice && <InlineMessage tone={noticeTone}>{notice}</InlineMessage>}
      <div className="erp-metrics-grid erp-metrics-3">
        <MetricCard label="Documents" value={documents.length} detail="Toutes périodes" icon="▤" />
        <MetricCard label="Brouillons" value={documents.filter((item) => item.status === 'Brouillon').length} detail="À finaliser" icon="◷" tone="amber" />
        <MetricCard label="Acceptées" value={documents.filter((item) => item.status === 'Acceptée').length} detail="Prêtes à facturer" icon="✓" tone="green" />
      </div>
      <Panel title="Documents" description="Pro formas de l’entreprise active" className="erp-list-panel">
        <div className="erp-list-toolbar">
          <input className="erp-control" placeholder="Rechercher un numéro ou un client…" value={query} onChange={(event) => setQuery(event.target.value)} />
          <select className="erp-control erp-filter-select" value={status} onChange={(event) => setStatus(event.target.value)}>
            {['Tous', 'Brouillon', 'En attente', 'Envoyée', 'Acceptée', 'Refusée', 'Expirée', 'Convertie'].map((item) => <option key={item}>{item}</option>)}
          </select>
        </div>
        <DataTable columns={[
          { key: 'id', label: 'N° Pro Forma' },
          { key: 'customer', label: 'Client' },
          { key: 'date', label: 'Date', render: (value) => value ? new Date(value).toLocaleDateString('fr-FR') : '—' },
          { key: 'due', label: 'Valide jusqu’au', render: (value) => value ? new Date(value).toLocaleDateString('fr-FR') : '—' },
          { key: 'amount', label: 'Montant', render: (amount) => <strong>{formatMoney(amount, settings.currency)}</strong> },
          { key: 'status', label: 'Statut', render: (value) => <StatusBadge>{value}</StatusBadge> },
          { key: 'action', label: 'Actions', render: (_, document) => <div className="erp-row-actions">
            <button className="erp-table-action" type="button" onClick={() => openDocument(document)}>Voir / imprimer</button>
            {permissions.includes('manage_proformas') && document.status !== 'Convertie' && <select className="erp-control erp-filter-select" aria-label={`Statut ${document.id}`} value="" disabled={busyDocument === document.proforma_id} onChange={(event) => changeStatus(document, event.target.value)}>
              <option value="">Changer le statut…</option>
              {[['BROUILLON', 'Brouillon'], ['EN_ATTENTE', 'En attente'], ['ENVOYEE', 'Envoyée'], ['ACCEPTEE', 'Acceptée'], ['REFUSEE', 'Refusée'], ['EXPIREE', 'Expirée']].filter(([, label]) => label !== document.status).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>}
            {permissions.includes('create_sales') && document.status === 'Acceptée' && <button className="erp-table-action" type="button" disabled={busyDocument === document.proforma_id} onClick={() => convertDocument(document)}>{busyDocument === document.proforma_id ? 'Conversion…' : 'Convertir en facture'}</button>}
          </div> },
        ]} rows={filtered} />
      </Panel>

      {showForm && <Modal title="Nouvelle pro forma" onClose={() => setShowForm(false)} footer={<><ActionButton variant="secondary" onClick={() => setShowForm(false)}>Annuler</ActionButton><ActionButton onClick={() => document.getElementById('proforma-form').requestSubmit()} disabled={saving || !products.length || !customers.length}>{saving ? 'Enregistrement…' : 'Créer le brouillon'}</ActionButton></>}>
        <form id="proforma-form" className="erp-form-grid" onSubmit={saveDraft}>
          <label className="erp-field erp-field-span"><span>Client</span><select value={draft.customerId} onChange={(event) => setDraft({ ...draft, customerId: event.target.value })} required><option value="">Sélectionnez un client</option>{customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.name}</option>)}</select></label>
          {!customers.length && <div className="erp-field-span"><InlineMessage tone="info">Créez d’abord un client pour établir une pro forma convertible en facture.</InlineMessage></div>}
          <div className="erp-field-span erp-proforma-items">
            <div className="erp-list-toolbar"><strong>Articles du devis</strong><ActionButton variant="secondary" onClick={addDraftItem} disabled={!products.length || draft.items.length >= products.length}>Ajouter un article</ActionButton></div>
            {draft.items.map((item, index) => <div className="erp-proforma-line" key={`${index}-${item.productId}`}>
              <label className="erp-field"><span>Produit</span><select value={item.productId} onChange={(event) => updateDraftItem(index, 'productId', event.target.value)} required>{products.filter((product) => String(product.id) === String(item.productId) || !draft.items.some((other, otherIndex) => otherIndex !== index && String(other.productId) === String(product.id))).map((product) => <option key={product.id} value={product.id}>{product.code} · {product.name}</option>)}</select></label>
              <Field label="Quantité" type="number" min="1" step="1" value={item.quantity} onChange={(quantity) => updateDraftItem(index, 'quantity', quantity)} required />
              <button className="erp-table-action erp-text-danger" type="button" aria-label="Retirer cet article" disabled={draft.items.length === 1} onClick={() => setDraft((current) => ({ ...current, items: current.items.filter((_, itemIndex) => itemIndex !== index) }))}>Retirer</button>
            </div>)}
          </div>
          <Field label="Validité (jours)" type="number" min="1" value={draft.validity} onChange={(validity) => setDraft({ ...draft, validity })} required />
          <div className="erp-field-span"><Field label="Objet du document" placeholder="Ex. Fourniture mensuelle" value={draft.object} onChange={(object) => setDraft({ ...draft, object })} /></div>
          <div className="erp-form-total"><span>Total estimatif · {selectedCustomer?.name || 'Client de passage'}</span><strong>{formatMoney(estimate, settings.currency)}</strong></div>
        </form>
      </Modal>}
      {(printLoading || printError || printDocument) && <Modal
        title={printDocument ? `Pro forma ${printDocument.document.proforma_number}` : 'Préparer la pro forma'}
        onClose={() => { setPrintDocument(null); setPrintError(''); }}
        footer={<>
          <ActionButton variant="secondary" onClick={() => { setPrintDocument(null); setPrintError(''); }}>Fermer</ActionButton>
          {printDocument && <ActionButton onClick={() => window.print()}>Imprimer / enregistrer en PDF</ActionButton>}
        </>}
      >
        {printLoading && <p role="status">Chargement du document…</p>}
        {printError && <InlineMessage tone="error">{printError}</InlineMessage>}
        {printDocument && <article className="erp-print-invoice" id="invoice-print-area">
          <header className="erp-print-invoice-header">
            <div><h2>{printDocument.company.companyName}</h2>
              {printDocument.company.companyCode && <p>{printDocument.company.companyCode}</p>}
              {printDocument.company.address && <p>{printDocument.company.address}</p>}
              {(printDocument.company.phone || printDocument.company.email) && <p>{[printDocument.company.phone, printDocument.company.email].filter(Boolean).join(' · ')}</p>}
            </div>
            <div className="erp-print-invoice-title"><h1>PRO FORMA</h1><strong>{printDocument.document.proforma_number}</strong><span>Émise le {new Date(printDocument.document.created_date).toLocaleDateString('fr-FR')}</span><span>Valide jusqu’au {printDocument.document.valid_until ? new Date(printDocument.document.valid_until).toLocaleDateString('fr-FR') : '—'}</span></div>
          </header>
          <section className="erp-print-invoice-customer"><strong>Proposé à</strong><span>{printDocument.document.customer}</span>
            {printDocument.document.customers?.company && <span>{printDocument.document.customers.company}</span>}
            {printDocument.document.customers?.phone && <span>{printDocument.document.customers.phone}</span>}
            {printDocument.document.customers?.email && <span>{printDocument.document.customers.email}</span>}
          </section>
          <table className="erp-print-invoice-lines"><thead><tr><th>Article</th><th>Qté</th><th>Prix unitaire</th><th>Remise</th><th>Total</th></tr></thead>
            <tbody>{printDocument.document.items.map((item) => <tr key={item.id}><td>{item.name}{item.code && <small>{item.code}</small>}</td><td>{item.quantity}</td><td>{formatMoney(item.unitPrice, printDocument.document.currency || settings.currency)}</td><td>{formatMoney(item.discount, printDocument.document.currency || settings.currency)}</td><td>{formatMoney(item.total, printDocument.document.currency || settings.currency)}</td></tr>)}</tbody>
          </table>
          <section className="erp-print-invoice-totals">
            <div><span>Sous-total</span><strong>{formatMoney(printDocument.document.subtotal, printDocument.document.currency || settings.currency)}</strong></div>
            <div><span>Remise</span><strong>{formatMoney(printDocument.document.discount_amount, printDocument.document.currency || settings.currency)}</strong></div>
            <div><span>Taxe</span><strong>{formatMoney(printDocument.document.tax_amount, printDocument.document.currency || settings.currency)}</strong></div>
            <div className="erp-print-invoice-total"><span>Total TTC</span><strong>{formatMoney(printDocument.document.total_amount, printDocument.document.currency || settings.currency)}</strong></div>
          </section>
          {printDocument.document.notes && <p className="erp-print-invoice-footer">{printDocument.document.notes}</p>}
        </article>}
      </Modal>}
    </div>
  );
}
