import { useCallback, useMemo, useState } from 'react';
import {
  cancelPurchaseOrder, createPurchaseOrder, listAccounts, listProducts, listPurchaseOrders,
  listSuppliers, payPurchaseOrder, receivePurchaseOrder,
} from '../api/businessApi';
import { useBusinessData } from '../api/useBusinessData';
import { ActionButton, DataTable, Field, InlineMessage, MetricCard, Modal, PageHeader, Panel, StatusBadge } from '../components/erp';
import { useAuth } from '../context/AuthContext';
import { formatMoney } from '../data/demoData';
import { downloadCsv } from '../utils/downloadCsv';

const emptyLine = { productId: '', quantity: '1', unitPrice: '0' };

function orderStatus(status) {
  return ({ ORDERED: 'En cours', RECEIVED: 'Reçue', CANCELLED: 'Annulée', PENDING: 'Brouillon' })[status] || status;
}

export default function PurchaseOrdersView() {
  const { organizationId, storeId, selectedStore, selectedOrganization, settings } = useAuth();
  const canExport = (selectedOrganization?.permissions || []).includes('export_data');
  const canManageTreasury = (selectedOrganization?.permissions || []).includes('manage_treasury');
  const load = useCallback(async () => {
    const [orders, suppliers, products, accounts] = await Promise.all([
      listPurchaseOrders(organizationId, canManageTreasury),
      listSuppliers(organizationId),
      listProducts(organizationId, storeId, selectedStore?.is_default),
      canManageTreasury ? listAccounts(organizationId) : Promise.resolve([]),
    ]);
    return { orders, suppliers, products, accounts };
  }, [canManageTreasury, organizationId, selectedStore?.is_default, storeId]);
  const { data, loading, error: loadError, refresh } = useBusinessData(load);
  const orders = data?.orders || [];
  const suppliers = data?.suppliers || [];
  const products = data?.products || [];
  const accounts = data?.accounts || [];
  const [query, setQuery] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');
  const [draft, setDraft] = useState({ supplierId: '', expectedDelivery: '', notes: '', items: [{ ...emptyLine }] });
  const [receivingOrder, setReceivingOrder] = useState(null);
  const [payingOrder, setPayingOrder] = useState(null);
  const [paymentDraft, setPaymentDraft] = useState({ accountId: '', amount: '', paymentMethod: 'CASH', notes: '' });
  const [savingPayment, setSavingPayment] = useState(false);
  const [receiveItems, setReceiveItems] = useState([]);
  const [busyOrder, setBusyOrder] = useState(null);
  const [notice, setNotice] = useState('');
  const [actionError, setActionError] = useState('');

  const filtered = useMemo(() => orders.filter((order) => (
    `${order.order_number} ${order.supplier_name} ${order.status}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())
  )), [orders, query]);
  const openOrders = orders.filter((order) => ['PENDING', 'ORDERED'].includes(order.status));
  const receivedTotal = orders.filter((order) => order.status === 'RECEIVED').reduce((sum, order) => sum + order.total_amount, 0);
  const pendingAmount = openOrders.reduce((sum, order) => sum + order.items.reduce(
    (orderSum, item) => orderSum + Math.max(item.quantity - item.received_quantity, 0) * item.unit_price,
    0,
  ), 0);

  const openCreateDialog = () => {
    const initialProduct = products[0];
    setDraft({
      supplierId: suppliers[0] ? String(suppliers[0].id) : '',
      expectedDelivery: '', notes: '',
      items: [{ ...emptyLine, productId: initialProduct ? String(initialProduct.id) : '', unitPrice: String(initialProduct?.cost || 0) }],
    });
    setCreateError('');
    setShowCreate(true);
  };

  const updateOrderLine = (index, key, value) => setDraft((current) => ({
    ...current,
    items: current.items.map((item, itemIndex) => {
      if (itemIndex !== index) return item;
      if (key === 'productId') {
        const product = products.find((candidate) => String(candidate.id) === String(value));
        return { ...item, productId: value, unitPrice: String(product?.cost || 0) };
      }
      return { ...item, [key]: value };
    }),
  }));

  const saveOrder = async (event) => {
    event.preventDefault();
    setCreating(true);
    setCreateError('');
    setNotice('');
    try {
      const result = await createPurchaseOrder({
        organizationId, storeId, supplierId: draft.supplierId,
        expectedDelivery: draft.expectedDelivery, notes: draft.notes,
        items: draft.items,
      });
      setShowCreate(false);
      setNotice(`${result.order_number} créée · ${formatMoney(result.total_amount, settings.currency)}.`);
      await refresh().catch(() => {});
    } catch (failure) {
      setCreateError(failure.message || 'La commande fournisseur n’a pas pu être enregistrée.');
    } finally {
      setCreating(false);
    }
  };

  const openReceiveDialog = (order) => {
    setReceivingOrder(order);
    setReceiveItems(order.items
      .filter((item) => item.received_quantity < item.quantity)
      .map((item) => ({ itemId: item.id, name: `${item.code} · ${item.name}`, remaining: item.quantity - item.received_quantity, quantity: String(item.quantity - item.received_quantity) })));
    setActionError('');
  };

  const saveReceipt = async (event) => {
    event.preventDefault();
    const items = receiveItems.filter((item) => Number(item.quantity) > 0);
    if (!items.length) { setActionError('Saisissez au moins une quantité reçue.'); return; }
    setBusyOrder(receivingOrder.id);
    setActionError('');
    setNotice('');
    try {
      const result = await receivePurchaseOrder({
        organizationId, orderId: receivingOrder.id, storeId,
        items: items.map((item) => ({ itemId: item.itemId, quantity: item.quantity })),
      });
      setReceivingOrder(null);
      setNotice(result.message || 'Réception enregistrée et stock mis à jour.');
      await refresh().catch(() => {});
    } catch (failure) {
      setActionError(failure.message || 'La réception n’a pas pu être enregistrée.');
    } finally {
      setBusyOrder(null);
    }
  };

  const openPaymentDialog = (order) => {
    const due = Math.max(order.total_amount - order.amount_paid, 0);
    setPayingOrder(order);
    setPaymentDraft({ accountId: String(accounts.find((account) => account.is_default)?.id || accounts[0]?.id || ''), amount: due ? String(due) : '', paymentMethod: 'CASH', notes: '' });
    setActionError('');
  };

  const savePayment = async (event) => {
    event.preventDefault();
    const amount = Number(paymentDraft.amount);
    const due = Math.max(payingOrder.total_amount - payingOrder.amount_paid, 0);
    if (!Number.isFinite(amount) || amount <= 0 || amount > due || !paymentDraft.accountId) {
      setActionError('Choisissez un compte et un montant positif qui ne dépasse pas le solde dû.');
      return;
    }
    setSavingPayment(true);
    setActionError('');
    setNotice('');
    try {
      const result = await payPurchaseOrder({ organizationId, orderId: payingOrder.id, accountId: paymentDraft.accountId, amount, paymentMethod: paymentDraft.paymentMethod, notes: paymentDraft.notes });
      setPayingOrder(null);
      setNotice(result.message || 'Paiement fournisseur enregistré.');
      await refresh().catch(() => {});
    } catch (failure) {
      setActionError(failure.message || 'Le paiement fournisseur n’a pas pu être enregistré.');
    } finally {
      setSavingPayment(false);
    }
  };

  const cancelOrder = async (order) => {
    if (!window.confirm(`Annuler la commande ${order.order_number} ?`)) return;
    setBusyOrder(order.id);
    setActionError('');
    setNotice('');
    try {
      const result = await cancelPurchaseOrder(organizationId, order.id);
      setNotice(result.message || 'Commande annulée.');
      await refresh().catch(() => {});
    } catch (failure) {
      setActionError(failure.message || 'La commande ne peut pas être annulée.');
    } finally {
      setBusyOrder(null);
    }
  };

  const exportOrders = () => {
    const headers = ['Commande', 'Fournisseur', 'Date', 'Livraison prévue', 'Statut', 'Montant'];
    if (canManageTreasury) headers.push('Réglé', 'Reste dû');
    headers.push('Devise');
    const rows = filtered.map((order) => {
      const row = [order.order_number, order.supplier_name, order.created_at, order.expected_delivery, orderStatus(order.status), order.total_amount];
      if (canManageTreasury) row.push(order.amount_paid, Math.max(order.total_amount - order.amount_paid, 0));
      row.push(settings.currency);
      return row;
    });
    downloadCsv(`commandes-achats-${selectedOrganization?.code || 'entreprise'}`, headers, rows);
  };

  if (loading && !data) return <div className="erp-standalone" role="status">Chargement des commandes…</div>;
  if (!data) return <InlineMessage tone="error">{loadError || 'Impossible de charger les commandes fournisseurs.'}</InlineMessage>;

  return (
    <div className="erp-page">
      <PageHeader
        title="Achats fournisseurs"
        subtitle={`Commandes et réceptions de stock · ${selectedStore?.name || 'magasin actif'}`}
        action={<>
          {canExport && <ActionButton variant="secondary" onClick={exportOrders} disabled={!filtered.length}>Exporter CSV</ActionButton>}
          <ActionButton onClick={openCreateDialog} disabled={!suppliers.length || !products.length || !storeId}>Nouvelle commande</ActionButton>
        </>}
      />
      {loadError && <InlineMessage tone="error">{loadError}</InlineMessage>}
      {notice && <InlineMessage tone="success">{notice}</InlineMessage>}
      {actionError && !receivingOrder && <InlineMessage tone="error">{actionError}</InlineMessage>}
      {!suppliers.length && <InlineMessage tone="info">Ajoutez d’abord un fournisseur actif dans la section Fournisseurs.</InlineMessage>}
      <div className="erp-metrics-grid">
        <MetricCard label="Commandes ouvertes" value={openOrders.length} detail="En attente de réception complète" icon="▣" tone="amber" />
        <MetricCard label="Valeur à recevoir" value={formatMoney(pendingAmount, settings.currency)} detail="Montant des commandes ouvertes" icon="¤" tone="blue" />
        <MetricCard label="Commandes reçues" value={orders.filter((order) => order.status === 'RECEIVED').length} detail={formatMoney(receivedTotal, settings.currency)} icon="✓" tone="green" />
        <MetricCard label="Annulées" value={orders.filter((order) => order.status === 'CANCELLED').length} detail="Sans réception de stock" icon="↶" tone="red" />
      </div>
      <Panel title="Commandes" description="Les réceptions partielles augmentent le stock et restent traçables dans les mouvements.">
        <div className="erp-list-toolbar">
          <input className="erp-control" placeholder="Rechercher un numéro ou un fournisseur…" value={query} onChange={(event) => setQuery(event.target.value)} />
          <span className="erp-toolbar-count">{filtered.length} résultat(s)</span>
        </div>
        <DataTable columns={[
          { key: 'order_number', label: 'N° commande' },
          { key: 'supplier_name', label: 'Fournisseur' },
          { key: 'created_at', label: 'Créée le', render: (value) => value ? new Date(value).toLocaleDateString('fr-FR') : '—' },
          { key: 'expected_delivery', label: 'Livraison prévue', render: (value) => value ? new Date(value).toLocaleDateString('fr-FR') : '—' },
          { key: 'items', label: 'Articles reçus', render: (items) => `${items.reduce((sum, item) => sum + item.received_quantity, 0)} / ${items.reduce((sum, item) => sum + item.quantity, 0)}` },
          { key: 'total_amount', label: canManageTreasury ? 'Montant / dû' : 'Montant', render: (value, order) => <>{formatMoney(value, settings.currency)}{canManageTreasury && <small className="erp-modal-copy">Réglé : {formatMoney(order.amount_paid, settings.currency)} · Reste : {formatMoney(Math.max(value - order.amount_paid, 0), settings.currency)}</small>}</> },
          { key: 'status', label: 'État', render: (value) => <StatusBadge>{orderStatus(value)}</StatusBadge> },
          { key: 'actions', label: 'Actions', render: (_, order) => <div className="erp-row-actions">
            {canManageTreasury && order.status === 'RECEIVED' && order.amount_paid < order.total_amount && <button className="erp-table-action" type="button" disabled={busyOrder === order.id || savingPayment || !accounts.length} onClick={() => openPaymentDialog(order)}>Régler</button>}
            {['PENDING', 'ORDERED'].includes(order.status) && <>
              <button className="erp-table-action" type="button" disabled={busyOrder === order.id} onClick={() => openReceiveDialog(order)}>Réceptionner</button>
              <button className="erp-table-action erp-text-danger" type="button" disabled={busyOrder === order.id} onClick={() => cancelOrder(order)}>Annuler</button>
            </>}
          </div> },
        ]} rows={filtered} emptyMessage="Aucune commande fournisseur." />
      </Panel>

      {showCreate && <Modal title="Nouvelle commande fournisseur" onClose={() => { if (!creating) setShowCreate(false); }} footer={<>
        <ActionButton variant="secondary" onClick={() => setShowCreate(false)} disabled={creating}>Annuler</ActionButton>
        <ActionButton onClick={() => document.getElementById('purchase-form').requestSubmit()} disabled={creating}>{creating ? 'Enregistrement…' : 'Créer la commande'}</ActionButton>
      </>}>
        <form id="purchase-form" className="erp-form-grid" onSubmit={saveOrder}>
          <div className="erp-field-span"><Field label="Fournisseur" value={draft.supplierId} onChange={(supplierId) => setDraft({ ...draft, supplierId })} options={suppliers.map((supplier) => ({ value: String(supplier.id), label: `${supplier.code} · ${supplier.name}` }))} required /></div>
          <Field label="Livraison prévue" type="date" value={draft.expectedDelivery} onChange={(expectedDelivery) => setDraft({ ...draft, expectedDelivery })} />
          <div className="erp-field-span"><strong>Articles commandés</strong></div>
          {draft.items.map((item, index) => (
            <div className="erp-field-span erp-order-line" key={`order-line-${index}`}>
              <label className="erp-field"><span>Produit</span><select value={item.productId} onChange={(event) => updateOrderLine(index, 'productId', event.target.value)} required>
                {products.map((product) => <option key={product.id} value={String(product.id)} disabled={draft.items.some((line, lineIndex) => lineIndex !== index && line.productId === String(product.id))}>{product.code} · {product.name}</option>)}
              </select></label>
              <Field label="Quantité" type="number" min="1" step="1" value={item.quantity} onChange={(quantity) => updateOrderLine(index, 'quantity', quantity)} required />
              <Field label={`Coût unitaire (${settings.currency})`} type="number" min="0" step="0.01" value={item.unitPrice} onChange={(unitPrice) => updateOrderLine(index, 'unitPrice', unitPrice)} required />
              <button className="erp-table-action erp-text-danger" type="button" disabled={draft.items.length <= 1} onClick={() => setDraft((current) => ({ ...current, items: current.items.filter((_, lineIndex) => lineIndex !== index) }))}>Retirer</button>
            </div>
          ))}
          <div className="erp-field-span"><ActionButton variant="secondary" onClick={() => setDraft((current) => ({ ...current, items: [...current.items, { ...emptyLine, productId: products[0] ? String(products[0].id) : '', unitPrice: String(products[0]?.cost || 0) }] }))} disabled={draft.items.length >= products.length}>Ajouter une ligne</ActionButton></div>
          <div className="erp-field-span"><Field label="Notes" value={draft.notes} onChange={(notes) => setDraft({ ...draft, notes })} /></div>
          {createError && <div className="erp-field-span"><InlineMessage tone="error">{createError}</InlineMessage></div>}
        </form>
      </Modal>}

      {receivingOrder && <Modal title={`Réception · ${receivingOrder.order_number}`} onClose={() => { if (!busyOrder) setReceivingOrder(null); }} footer={<>
        <ActionButton variant="secondary" onClick={() => setReceivingOrder(null)} disabled={Boolean(busyOrder)}>Fermer</ActionButton>
        <ActionButton onClick={() => document.getElementById('receipt-form').requestSubmit()} disabled={Boolean(busyOrder)}>{busyOrder ? 'Enregistrement…' : 'Enregistrer la réception'}</ActionButton>
      </>}>
        <form id="receipt-form" className="erp-form-grid" onSubmit={saveReceipt}>
          {receiveItems.map((item, index) => <div className="erp-field-span erp-order-line" key={item.itemId}>
            <span>{item.name}<small className="erp-modal-copy">Reste à recevoir : {item.remaining}</small></span>
            <Field label="Quantité reçue" type="number" min="0" max={item.remaining} step="1" value={item.quantity} onChange={(quantity) => setReceiveItems((current) => current.map((line, lineIndex) => lineIndex === index ? { ...line, quantity } : line))} />
          </div>)}
          {actionError && <div className="erp-field-span"><InlineMessage tone="error">{actionError}</InlineMessage></div>}
        </form>
      </Modal>}
      {payingOrder && <Modal title={`Règlement · ${payingOrder.order_number}`} onClose={() => { if (!savingPayment) setPayingOrder(null); }} footer={<>
        <ActionButton variant="secondary" onClick={() => setPayingOrder(null)} disabled={savingPayment}>Annuler</ActionButton>
        <ActionButton onClick={() => document.getElementById('purchase-payment-form').requestSubmit()} disabled={savingPayment || !accounts.length}>{savingPayment ? 'Enregistrement…' : 'Enregistrer le paiement'}</ActionButton>
      </>}>
        <form id="purchase-payment-form" className="erp-form-grid" onSubmit={savePayment}>
          <div className="erp-field-span"><InlineMessage tone="info">Solde dû : {formatMoney(Math.max(payingOrder.total_amount - payingOrder.amount_paid, 0), settings.currency)}</InlineMessage></div>
          <div className="erp-field-span"><Field label="Compte de trésorerie" value={paymentDraft.accountId} onChange={(accountId) => setPaymentDraft({ ...paymentDraft, accountId })} options={accounts.map((account) => ({ value: String(account.id), label: `${account.name} · solde ${formatMoney(account.balance, settings.currency)}` }))} required /></div>
          <Field label={`Montant (${settings.currency})`} type="number" min="0.01" max={Math.max(payingOrder.total_amount - payingOrder.amount_paid, 0)} step="0.01" value={paymentDraft.amount} onChange={(amount) => setPaymentDraft({ ...paymentDraft, amount })} required />
          <Field label="Mode de paiement" value={paymentDraft.paymentMethod} onChange={(paymentMethod) => setPaymentDraft({ ...paymentDraft, paymentMethod })} options={[{ value: 'CASH', label: 'Espèces' }, { value: 'CARD', label: 'Carte' }, { value: 'BANK_TRANSFER', label: 'Virement' }, { value: 'MOBILE_MONEY', label: 'Mobile money' }, { value: 'CHEQUE', label: 'Chèque' }]} />
          <div className="erp-field-span"><Field label="Notes" value={paymentDraft.notes} onChange={(notes) => setPaymentDraft({ ...paymentDraft, notes })} maxLength="500" /></div>
          {actionError && <div className="erp-field-span"><InlineMessage tone="error">{actionError}</InlineMessage></div>}
        </form>
      </Modal>}
    </div>
  );
}
