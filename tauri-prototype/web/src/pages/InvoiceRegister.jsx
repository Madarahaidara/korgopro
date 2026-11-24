import { useCallback, useMemo, useState } from 'react';
import { cancelSale, listSales, loadInvoiceDetails, registerPayment } from '../api/businessApi';
import { useBusinessData } from '../api/useBusinessData';
import {
  ActionButton, DataTable, Field, InlineMessage, MetricCard, Modal, PageHeader, Panel, StatusBadge,
} from '../components/erp';
import { formatMoney } from '../data/demoData';
import { useAuth } from '../context/AuthContext';
import { downloadCsv } from '../utils/downloadCsv';

export default function InvoiceRegister() {
  const { organizationId, storeId, selectedStore, selectedOrganization, settings } = useAuth();
  const permissions = selectedOrganization?.permissions || [];
  const canCollectPayments = permissions.includes('create_sales') || permissions.includes('manage_treasury');
  const canCancelSales = permissions.includes('cancel_sales');
  const canExport = permissions.includes('export_data');
  const load = useCallback(async () => {
    const sales = await listSales(organizationId, storeId, null, selectedStore?.is_default);
    return {
      invoices: sales.filter((sale) => sale.type_document === 'FACTURE' && sale.sale_status !== 'CANCELLED'),
    };
  }, [organizationId, selectedStore?.is_default, storeId]);
  const { data, loading, error: loadError, refresh } = useBusinessData(load);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('Tous');
  const [selected, setSelected] = useState(null);
  const [selectedCancel, setSelectedCancel] = useState(null);
  const [cancelReason, setCancelReason] = useState('');
  const [cancelSaving, setCancelSaving] = useState(false);
  const [printInvoice, setPrintInvoice] = useState(null);
  const [printLoading, setPrintLoading] = useState(false);
  const [printError, setPrintError] = useState('');
  const [amount, setAmount] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('CASH');
  const [paymentError, setPaymentError] = useState('');
  const [cancelError, setCancelError] = useState('');
  const [notice, setNotice] = useState('');
  const [noticeTone, setNoticeTone] = useState('success');
  const [saving, setSaving] = useState(false);

  const invoices = data?.invoices || [];
  const filtered = useMemo(() => invoices.filter((invoice) => (
    (status === 'Tous' || invoice.status === status)
    && `${invoice.id} ${invoice.customer}`.toLowerCase().includes(query.toLowerCase())
  )), [invoices, query, status]);
  const due = invoices.reduce((sum, invoice) => sum + invoice.due, 0);
  const total = invoices.reduce((sum, invoice) => sum + invoice.total, 0);
  const paid = invoices.reduce((sum, invoice) => sum + invoice.paid, 0);
  const exportInvoices = () => downloadCsv(
    `factures-${selectedOrganization?.code || 'entreprise'}`,
    ['N° facture', 'Date', 'Client', 'Total', 'Payé', 'Reste dû', 'Statut', 'Devise'],
    filtered.map((invoice) => [invoice.id, invoice.date, invoice.customer, invoice.total, invoice.paid, invoice.due, invoice.status, invoice.currency || settings.currency]),
  );

  const openPayment = (invoice) => {
    setSelected(invoice);
    setAmount(String(invoice.due));
    setPaymentMethod('CASH');
    setPaymentError('');
    setNotice('');
    setNoticeTone('success');
  };

  const openCancellation = (invoice) => {
    setSelectedCancel(invoice);
    setCancelReason('');
    setCancelError('');
    setNotice('');
    setNoticeTone('success');
  };

  const openInvoice = async (invoice) => {
    setPrintInvoice(null);
    setPrintError('');
    setPrintLoading(true);
    try {
      setPrintInvoice(await loadInvoiceDetails(organizationId, invoice.sale_id));
    } catch (failure) {
      setPrintError(failure.message || 'Impossible de charger le détail de cette facture.');
    } finally {
      setPrintLoading(false);
    }
  };

  const receivePayment = async (event) => {
    event.preventDefault();
    const payment = Number(amount);
    if (!selected || payment <= 0 || payment > selected.due) {
      setPaymentError('Saisissez un montant positif qui ne dépasse pas le reste dû.');
      return;
    }
    setSaving(true);
    setNotice('');
    setPaymentError('');
    try {
      const result = await registerPayment({
        organizationId,
        saleId: selected.sale_id,
        amount: payment,
        paymentMethod,
      });
      setSelected(null);
      setAmount('');
      setNotice(result.message || `Paiement de ${formatMoney(payment, settings.currency)} enregistré.`);
      setNoticeTone('success');
      await refresh().catch(() => {});
    } catch (failure) {
      setPaymentError(failure.message || 'Le paiement n’a pas pu être enregistré.');
    } finally {
      setSaving(false);
    }
  };

  const submitCancellation = async (event) => {
    event.preventDefault();
    const reason = cancelReason.trim();
    if (!selectedCancel || !reason) {
      setCancelError('Indiquez le motif de l’annulation.');
      return;
    }
    setCancelSaving(true);
    setCancelError('');
    try {
      const result = await cancelSale(organizationId, selectedCancel.sale_id, reason);
      setSelectedCancel(null);
      setCancelReason('');
      setNotice(result.message || 'Vente annulée.');
      setNoticeTone('success');
      await refresh().catch(() => {});
    } catch (failure) {
      setCancelError(failure.message || 'La vente n’a pas pu être annulée.');
    } finally {
      setCancelSaving(false);
    }
  };

  if (loading && !data) return <div className="erp-standalone" role="status">Chargement du registre des factures…</div>;
  if (!data) return <InlineMessage tone="error">{loadError || 'Impossible de charger le registre des factures.'}</InlineMessage>;

  return (
    <div className="erp-page">
      <PageHeader title="Registre des factures" subtitle="Suivez les montants facturés, encaissés et restant dus." action={canExport ? <ActionButton variant="secondary" onClick={exportInvoices}>Exporter CSV</ActionButton> : null} />
      {loadError && <InlineMessage tone="error">{loadError}</InlineMessage>}
      {notice && <InlineMessage tone={noticeTone}>{notice}</InlineMessage>}
      <div className="erp-metrics-grid">
        <MetricCard label="Factures" value={invoices.length} detail="Factures actives" icon="▤" />
        <MetricCard label="Montant total" value={formatMoney(total, settings.currency)} detail="Émis" icon="◈" />
        <MetricCard label="Encaissé" value={formatMoney(paid, settings.currency)} detail="Paiements enregistrés" icon="✓" tone="green" />
        <MetricCard label="Reste dû" value={formatMoney(due, settings.currency)} detail="À recouvrer" icon="◷" tone="amber" />
      </div>
      <Panel title="Factures clients" description="Encaissements sécurisés par une opération métier Supabase.">
        <div className="erp-list-toolbar">
          <input className="erp-control" placeholder="N° facture ou nom du client…" value={query} onChange={(event) => setQuery(event.target.value)} />
          <select className="erp-control erp-filter-select" value={status} onChange={(event) => setStatus(event.target.value)}>
            {['Tous', 'Payée', 'Partielle', 'À payer'].map((item) => <option key={item}>{item}</option>)}
          </select>
        </div>
        <DataTable columns={[
          { key: 'id', label: 'N° Facture' }, { key: 'customer', label: 'Client' }, { key: 'date', label: 'Date' },
          { key: 'total', label: 'Total', render: (value) => formatMoney(value, settings.currency) },
          { key: 'paid', label: 'Payé', render: (value) => formatMoney(value, settings.currency) },
          { key: 'due', label: 'Reste dû', render: (value) => <strong>{formatMoney(value, settings.currency)}</strong> },
          { key: 'status', label: 'Statut', render: (value) => <StatusBadge>{value}</StatusBadge> },
          { key: 'action', label: 'Actions', render: (_, invoice) => <div className="erp-row-actions">
            <button className="erp-table-action" type="button" onClick={() => openInvoice(invoice)}>Voir / imprimer</button>
            {canCollectPayments && invoice.due > 0 && <button className="erp-table-action" type="button" onClick={() => openPayment(invoice)}>Encaisser</button>}
            {canCancelSales && <button className="erp-table-action erp-table-action-danger" type="button" onClick={() => openCancellation(invoice)}>Annuler</button>}
          </div> },
        ]} rows={filtered} />
      </Panel>
      {selected && <Modal title={`Encaisser ${selected.id}`} onClose={() => setSelected(null)} footer={<><ActionButton variant="secondary" onClick={() => setSelected(null)}>Annuler</ActionButton><ActionButton onClick={() => document.getElementById('payment-form').requestSubmit()} disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer le paiement'}</ActionButton></>}>
        <form id="payment-form" className="erp-form-grid" onSubmit={receivePayment}>
          <p className="erp-field-span erp-modal-copy">Client : <strong>{selected.customer}</strong> · reste dû : <strong>{formatMoney(selected.due, settings.currency)}</strong></p>
          {paymentError && <div className="erp-field-span"><InlineMessage tone="error">{paymentError}</InlineMessage></div>}
          <Field label={`Montant reçu (${settings.currency})`} type="number" min="0.01" max={selected.due} step="0.01" value={amount} onChange={setAmount} required />
          <Field label="Mode de paiement" value={paymentMethod} onChange={setPaymentMethod} options={[
            { value: 'CASH', label: 'Espèces' },
            { value: 'MOBILE MONEY', label: 'Mobile money' },
            { value: 'VIREMENT', label: 'Virement' },
          ]} />
        </form>
      </Modal>}
      {selectedCancel && <Modal
        title={`Annuler la vente ${selectedCancel.id} ?`}
        onClose={() => { if (!cancelSaving) setSelectedCancel(null); }}
        footer={<>
          <ActionButton variant="secondary" onClick={() => setSelectedCancel(null)} disabled={cancelSaving}>Garder la facture</ActionButton>
          <ActionButton variant="danger" onClick={() => document.getElementById('cancel-sale-form').requestSubmit()} disabled={cancelSaving}>
            {cancelSaving ? 'Annulation…' : 'Confirmer l’annulation'}
          </ActionButton>
        </>}
      >
        <form id="cancel-sale-form" className="erp-form-grid" onSubmit={submitCancellation}>
          <p className="erp-field-span erp-modal-copy">
            Le stock sera rétabli, le solde client recalculé et les encaissements liés seront compensés en trésorerie. L’opération restera dans l’historique.
          </p>
          {cancelError && <div className="erp-field-span"><InlineMessage tone="error">{cancelError}</InlineMessage></div>}
          <Field label="Motif (obligatoire)" value={cancelReason} onChange={setCancelReason} required maxLength="200" />
        </form>
      </Modal>}
      {(printLoading || printError || printInvoice) && <Modal
        title={printInvoice ? `Facture ${printInvoice.invoice.id}` : 'Préparer la facture'}
        onClose={() => { setPrintInvoice(null); setPrintError(''); }}
        footer={<>
          <ActionButton variant="secondary" onClick={() => { setPrintInvoice(null); setPrintError(''); }}>Fermer</ActionButton>
          {printInvoice && <ActionButton onClick={() => window.print()}>Imprimer / enregistrer en PDF</ActionButton>}
        </>}
      >
        {printLoading && <p role="status">Chargement du détail de la facture…</p>}
        {printError && <InlineMessage tone="error">{printError}</InlineMessage>}
        {printInvoice && <article className="erp-print-invoice" id="invoice-print-area">
          <header className="erp-print-invoice-header">
            <div>
              <h2>{printInvoice.company.companyName}</h2>
              {printInvoice.company.companyCode && <p>{printInvoice.company.companyCode}</p>}
              {printInvoice.company.address && <p>{printInvoice.company.address}</p>}
              {(printInvoice.company.phone || printInvoice.company.email) && <p>{[printInvoice.company.phone, printInvoice.company.email].filter(Boolean).join(' · ')}</p>}
            </div>
            <div className="erp-print-invoice-title">
              <h1>FACTURE</h1>
              <strong>{printInvoice.invoice.id}</strong>
              <span>{printInvoice.invoice.date}</span>
            </div>
          </header>
          <section className="erp-print-invoice-customer">
            <strong>Facturé à</strong>
            <span>{printInvoice.invoice.customer}</span>
            {printInvoice.invoice.customers?.company && <span>{printInvoice.invoice.customers.company}</span>}
            {printInvoice.invoice.customers?.phone && <span>{printInvoice.invoice.customers.phone}</span>}
            {printInvoice.invoice.customers?.email && <span>{printInvoice.invoice.customers.email}</span>}
          </section>
          <table className="erp-print-invoice-lines">
            <thead><tr><th>Article</th><th>Qté</th><th>Prix unitaire</th><th>Remise</th><th>Total</th></tr></thead>
            <tbody>{printInvoice.items.map((item) => <tr key={item.id}>
              <td>{item.name}{item.code && <small>{item.code}</small>}</td>
              <td>{item.quantity}</td>
              <td>{formatMoney(item.unitPrice, printInvoice.invoice.currency || settings.currency)}</td>
              <td>{formatMoney(item.discount, printInvoice.invoice.currency || settings.currency)}</td>
              <td>{formatMoney(item.total, printInvoice.invoice.currency || settings.currency)}</td>
            </tr>)}</tbody>
          </table>
          <section className="erp-print-invoice-totals">
            <div><span>Sous-total</span><strong>{formatMoney(Number(printInvoice.invoice.subtotal) || 0, printInvoice.invoice.currency || settings.currency)}</strong></div>
            <div><span>Remise</span><strong>{formatMoney(Number(printInvoice.invoice.discount_amount) || 0, printInvoice.invoice.currency || settings.currency)}</strong></div>
            <div><span>Taxe</span><strong>{formatMoney(Number(printInvoice.invoice.tax_amount) || 0, printInvoice.invoice.currency || settings.currency)}</strong></div>
            <div className="erp-print-invoice-total"><span>Total TTC</span><strong>{formatMoney(printInvoice.invoice.total, printInvoice.invoice.currency || settings.currency)}</strong></div>
            <div><span>Payé</span><strong>{formatMoney(printInvoice.invoice.paid, printInvoice.invoice.currency || settings.currency)}</strong></div>
            <div><span>Reste dû</span><strong>{formatMoney(printInvoice.invoice.due, printInvoice.invoice.currency || settings.currency)}</strong></div>
          </section>
          {printInvoice.company.invoiceFooter && <footer className="erp-print-invoice-footer">{printInvoice.company.invoiceFooter}</footer>}
        </article>}
      </Modal>}
    </div>
  );
}
