import { useCallback, useMemo, useState } from 'react';
import { createSale, listCustomers, listProducts } from '../api/businessApi';
import { useBusinessData } from '../api/useBusinessData';
import { ActionButton, InlineMessage, PageHeader, Panel } from '../components/erp';
import { formatMoney } from '../data/demoData';
import { useAuth } from '../context/AuthContext';

const paymentMethods = [
  { label: 'Espèces', value: 'CASH' },
  { label: 'Mobile money', value: 'MOBILE MONEY' },
  { label: 'Virement', value: 'VIREMENT' },
  { label: 'Crédit client', value: 'CREDIT' },
];

export default function SaleView() {
  const { organizationId, storeId, selectedStore, selectedOrganization, settings } = useAuth();
  const load = useCallback(async () => {
    const [products, customers] = await Promise.all([
      listProducts(organizationId, storeId, selectedStore?.is_default),
      listCustomers(organizationId),
    ]);
    return { products, customers };
  }, [organizationId, selectedStore?.is_default, storeId]);
  const { data, loading, error: loadError, refresh } = useBusinessData(load);
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('Toutes');
  const [cart, setCart] = useState([]);
  const [customerId, setCustomerId] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('CASH');
  const [receivedAmount, setReceivedAmount] = useState('');
  const [discount, setDiscount] = useState('0');
  const [message, setMessage] = useState('');
  const [saving, setSaving] = useState(false);

  const products = data?.products || [];
  const selectedCustomer = (data?.customers || []).find((customer) => String(customer.id) === customerId);
  const availableCredit = Math.max((Number(selectedCustomer?.credit_limit) || 0) - (Number(selectedCustomer?.balance) || 0), 0);
  const categories = ['Toutes', ...new Set(products.map((item) => item.category).filter(Boolean))];
  const filteredProducts = useMemo(() => products.filter((product) => (
    (category === 'Toutes' || product.category === category)
    && `${product.name} ${product.code}`.toLowerCase().includes(query.toLowerCase())
  )), [category, products, query]);
  const subtotal = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);
  const discountAmount = Math.max(0, Math.min(subtotal, Number(discount) || 0));
  const taxRate = Number(selectedOrganization?.tax_rate) || 0;
  const taxAmount = Number(((subtotal - discountAmount) * taxRate / 100).toFixed(2));
  const total = subtotal - discountAmount + taxAmount;
  const amountPaid = receivedAmount.trim() === ''
    ? (paymentMethod === 'CREDIT' ? 0 : total)
    : Number(receivedAmount);
  const changeDue = paymentMethod === 'CASH' ? Math.max(amountPaid - total, 0) : 0;
  const mayDiscount = (selectedOrganization?.permissions || []).includes('apply_discount');

  const addProduct = (product) => {
    setMessage('');
    setCart((items) => {
      const current = items.find((item) => item.id === product.id);
      if (current) return items.map((item) => item.id === product.id
        ? { ...item, quantity: Math.min(item.quantity + 1, product.stock) }
        : item);
      return [...items, { ...product, quantity: 1 }];
    });
  };

  const changeQuantity = (id, quantity) => {
    setCart((items) => items.map((item) => item.id === id
      ? { ...item, quantity: Math.max(1, Math.min(quantity, item.stock)) }
      : item));
  };

  const finishSale = async () => {
    setMessage('');
    if (!storeId) {
      setMessage('Aucun magasin actif n’est disponible pour cette entreprise.');
      return;
    }
    if (!cart.length) {
      setMessage('Ajoutez au moins un article au panier.');
      return;
    }
    if (paymentMethod === 'CREDIT' && !customerId) {
      setMessage('Sélectionnez un client pour enregistrer une vente à crédit.');
      return;
    }
    if (!Number.isFinite(amountPaid) || amountPaid < 0) {
      setMessage('Saisissez un montant reçu valide.');
      return;
    }
    if (paymentMethod === 'CREDIT' && amountPaid > total) {
      setMessage('L’acompte ne peut pas dépasser le total de la vente.');
      return;
    }
    if (paymentMethod === 'CREDIT' && total - amountPaid > availableCredit) {
      setMessage(`Crédit disponible insuffisant. Solde maximum autorisé : ${formatMoney(availableCredit, settings.currency)}.`);
      return;
    }
    if (paymentMethod !== 'CREDIT' && amountPaid < total) {
      setMessage('Le règlement est incomplet. Choisissez « Crédit client » pour enregistrer un solde dû.');
      return;
    }
    setSaving(true);
    try {
      const result = await createSale({
        organizationId,
        storeId,
        customerId: customerId || null,
        items: cart.map((item) => ({ product_id: item.id, quantity: item.quantity })),
        discountAmount,
        paymentMethod,
        amountPaid,
      });
      setCart([]);
      setDiscount('0');
      setReceivedAmount('');
      setMessage(`${result.sale_number} enregistrée · ${formatMoney(result.total_amount, settings.currency)}.`);
      await refresh().catch(() => {});
    } catch (failure) {
      setMessage(failure.message || 'La vente n’a pas pu être enregistrée.');
    } finally {
      setSaving(false);
    }
  };

  if (loading && !data) return <div className="erp-standalone" role="status">Chargement du catalogue…</div>;
  if (!data) return <InlineMessage tone="error">{loadError || 'Impossible de charger le catalogue.'}</InlineMessage>;

  return (
    <div className="erp-page">
      <PageHeader title="Caisse" subtitle="Enregistrez une vente dans l’entreprise et le magasin actifs." action={<span className="erp-ticket">VENTE · NOUVELLE</span>} />
      {loadError && <InlineMessage tone="error">{loadError}</InlineMessage>}
      {message && <InlineMessage tone={message.includes('enregistrée') ? 'success' : 'error'}>{message}</InlineMessage>}
      <div className="erp-pos-layout">
        <Panel title="Catalogue produits" description={`${filteredProducts.length} article(s) disponibles`}>
          <div className="erp-pos-filters">
            <input className="erp-control" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Rechercher un produit ou une référence…" />
            <select className="erp-control erp-category-select" value={category} onChange={(event) => setCategory(event.target.value)}>
              {categories.map((item) => <option key={item}>{item}</option>)}
            </select>
          </div>
          <div className="erp-product-grid">
            {filteredProducts.map((product) => (
              <button type="button" className="erp-product-card" key={product.id} onClick={() => addProduct(product)} disabled={product.stock < 1}>
                <span className="erp-product-art">▦</span>
                <strong>{product.name}</strong>
                <small>{product.code} · Stock {product.stock}</small>
                <span>{formatMoney(product.price, settings.currency)}</span>
              </button>
            ))}
            {!filteredProducts.length && <div className="erp-empty-card">Aucun produit actif ne correspond à la recherche.</div>}
          </div>
        </Panel>

        <Panel title="Panier" description={`${cart.reduce((sum, item) => sum + item.quantity, 0)} article(s)`} className="erp-cart-panel">
          <label className="erp-field"><span>Client</span>
            <select value={customerId} onChange={(event) => setCustomerId(event.target.value)}>
              <option value="">Client de passage</option>
              {(data.customers || []).map((customer) => <option key={customer.id} value={customer.id}>{customer.name}</option>)}
            </select>
          </label>
          <div className="erp-cart-items">
            {cart.length ? cart.map((item) => (
              <div className="erp-cart-row" key={item.id}>
                <div className="erp-cart-product"><strong>{item.name}</strong><small>{formatMoney(item.price, settings.currency)} / unité</small></div>
                <div className="erp-quantity">
                  <button type="button" aria-label={`Diminuer ${item.name}`} onClick={() => changeQuantity(item.id, item.quantity - 1)}>−</button>
                  <span>{item.quantity}</span>
                  <button type="button" aria-label={`Augmenter ${item.name}`} onClick={() => changeQuantity(item.id, item.quantity + 1)}>+</button>
                </div>
                <strong>{formatMoney(item.price * item.quantity, settings.currency)}</strong>
                <button type="button" className="erp-remove" aria-label={`Retirer ${item.name}`} onClick={() => setCart((items) => items.filter((product) => product.id !== item.id))}>×</button>
              </div>
            )) : <div className="erp-cart-empty"><span>▣</span><strong>Le panier est vide</strong><small>Sélectionnez un produit pour démarrer la vente.</small></div>}
          </div>
          <div className="erp-sale-fields">
            <label className="erp-field"><span>Mode de paiement</span>
              <select value={paymentMethod} onChange={(event) => { setPaymentMethod(event.target.value); setReceivedAmount(''); }}>
                {paymentMethods.map((method) => <option key={method.value} value={method.value}>{method.label}</option>)}
              </select>
            </label>
            <label className="erp-field"><span>Remise ({settings.currency})</span>
              <input type="number" min="0" max={subtotal} value={discount} disabled={!mayDiscount} onChange={(event) => setDiscount(event.target.value)} />
            </label>
          </div>
          {(paymentMethod === 'CASH' || paymentMethod === 'CREDIT') && <>
            <label className="erp-field">
              <span>{paymentMethod === 'CASH' ? `Espèces reçues (${settings.currency})` : `Acompte versé (${settings.currency})`}</span>
              <input
                type="number"
                min="0"
                max={paymentMethod === 'CREDIT' ? total : undefined}
                step="0.01"
                value={receivedAmount}
                placeholder={paymentMethod === 'CREDIT' ? '0' : String(total)}
                onChange={(event) => setReceivedAmount(event.target.value)}
              />
            </label>
            {paymentMethod === 'CASH' && <div className="erp-payment-hint">{amountPaid < total ? 'Montant restant à recevoir' : 'Monnaie à rendre'} : <strong>{formatMoney(amountPaid < total ? total - amountPaid : changeDue, settings.currency)}</strong></div>}
            {paymentMethod === 'CREDIT' && <div className="erp-payment-hint">Reste à payer : <strong>{formatMoney(Math.max(total - amountPaid, 0), settings.currency)}</strong>{selectedCustomer && <small>Crédit disponible : {formatMoney(availableCredit, settings.currency)}</small>}</div>}
          </>}
          <div className="erp-totals">
            <div><span>Sous-total</span><strong>{formatMoney(subtotal, settings.currency)}</strong></div>
            <div><span>Remise</span><strong>− {formatMoney(discountAmount, settings.currency)}</strong></div>
            {taxRate > 0 && <div><span>Taxe ({taxRate} %)</span><strong>{formatMoney(taxAmount, settings.currency)}</strong></div>}
            <div className="erp-grand-total"><span>Total à payer</span><strong>{formatMoney(total, settings.currency)}</strong></div>
          </div>
          <ActionButton className="erp-full-button" onClick={finishSale} disabled={saving || !storeId}>
            {saving ? 'Enregistrement…' : 'Enregistrer la vente'}
          </ActionButton>
          <p className="erp-helper">Le stock, la facture et l’encaissement sont enregistrés de manière transactionnelle.</p>
        </Panel>
      </div>
    </div>
  );
}
