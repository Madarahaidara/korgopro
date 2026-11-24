import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  createProduct, createStockMovement, listInventoryMovements, listProducts, listSales, listSuppliers, setProductActive, updateProduct,
} from '../api/businessApi';
import { useBusinessData } from '../api/useBusinessData';
import {
  ActionButton, DataTable, Field, InlineMessage, MetricCard, Modal, PageHeader, Panel, StatusBadge, Tabs,
} from '../components/erp';
import { formatMoney } from '../data/demoData';
import { useAuth } from '../context/AuthContext';
import { downloadCsv } from '../utils/downloadCsv';

const stockTabs = ['Produits', 'Mouvements', 'Ventes', 'Calculs', 'Rapports'];
const movementTypes = [
  { value: 'IN', label: 'Entrée' },
  { value: 'OUT', label: 'Sortie' },
  { value: 'ADJUST', label: 'Ajustement' },
  { value: 'LOSS', label: 'Perte' },
  { value: 'RETURN', label: 'Retour' },
];
const emptyProductDraft = { name: '', category: '', supplierId: '', initialQuantity: '0', minStock: '5', maxStock: '100', purchasePrice: '0', salePrice: '0' };

export default function StockView() {
  const { organizationId, storeId, selectedStore, selectedOrganization, settings } = useAuth();
  const permissions = selectedOrganization?.permissions || [];
  const canManageStock = permissions.includes('manage_stock');
  const canExport = permissions.includes('export_data');
  const canViewSales = ['view_dashboard', 'view_sales', 'view_reports', 'create_sales', 'view_invoice_register']
    .some((permission) => permissions.includes(permission));
  const load = useCallback(async () => {
    const [products, movements, sales, suppliers] = await Promise.all([
      listProducts(organizationId, storeId, selectedStore?.is_default, true),
      listInventoryMovements(organizationId, storeId, null, selectedStore?.is_default),
      canViewSales
        ? listSales(organizationId, storeId, null, selectedStore?.is_default)
        : Promise.resolve([]),
      canManageStock ? listSuppliers(organizationId, true) : Promise.resolve([]),
    ]);
    return { products, movements, sales, suppliers };
  }, [canManageStock, canViewSales, organizationId, selectedStore?.is_default, storeId]);
  const { data, loading, error: loadError, refresh } = useBusinessData(load);
  const [tab, setTab] = useState('Produits');
  const [query, setQuery] = useState('');
  const [showProduct, setShowProduct] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [showMovement, setShowMovement] = useState(false);
  const [notice, setNotice] = useState('');
  const [noticeTone, setNoticeTone] = useState('success');
  const [saving, setSaving] = useState(false);
  const [busyProduct, setBusyProduct] = useState(null);
  const [draft, setDraft] = useState(emptyProductDraft);
  const [movement, setMovement] = useState({ productId: '', type: 'IN', quantity: '1', unitCost: '', reason: '', reference: '' });
  const [calcProductId, setCalcProductId] = useState(null);
  const [calcPurchase, setCalcPurchase] = useState('');
  const [calcSale, setCalcSale] = useState('');
  const [calcExpenses, setCalcExpenses] = useState('0');
  const [calcQuantity, setCalcQuantity] = useState('1');
  const [calcTargetMargin, setCalcTargetMargin] = useState('30');
  const [calcFixedCosts, setCalcFixedCosts] = useState('0');

  useEffect(() => {
    if (!canViewSales && tab === 'Ventes') setTab('Produits');
  }, [canViewSales, tab]);

  const products = data?.products || [];
  const suppliers = data?.suppliers || [];
  const filteredProducts = useMemo(() => products.filter((product) => (
    `${product.code} ${product.name} ${product.category} ${product.supplier_name || ''}`.toLowerCase().includes(query.toLowerCase())
  )), [products, query]);
  const activeProducts = useMemo(() => products.filter((product) => product.active), [products]);
  useEffect(() => {
    if (calcProductId == null) {
      const initialProduct = activeProducts[0];
      if (initialProduct) setCalcProductId(String(initialProduct.id));
      return;
    }
    if (calcProductId === '') return;
    const product = activeProducts.find((item) => String(item.id) === calcProductId);
    if (!product) {
      setCalcProductId(null);
      return;
    }
    setCalcPurchase(String(product.cost));
    setCalcSale(String(product.price));
  }, [activeProducts, calcProductId]);
  const calcPurchaseValue = Math.max(Number(calcPurchase) || 0, 0);
  const calcSaleValue = Math.max(Number(calcSale) || 0, 0);
  const calcExpenseValue = Math.max(Number(calcExpenses) || 0, 0);
  const calcQuantityValue = Math.max(Number(calcQuantity) || 1, 1);
  const calcUnitCost = calcPurchaseValue + calcExpenseValue / calcQuantityValue;
  const calcUnitProfit = calcSaleValue - calcUnitCost;
  const calcMarginPercent = calcSaleValue > 0 ? calcUnitProfit / calcSaleValue * 100 : 0;
  const calcCostMarginPercent = calcUnitCost > 0 ? calcUnitProfit / calcUnitCost * 100 : 0;
  const calcTargetValue = Number(calcTargetMargin) || 0;
  const calcSuggestedPrice = calcTargetValue >= 0 && calcTargetValue < 100
    ? calcUnitCost / (1 - calcTargetValue / 100)
    : null;
  const calcRetailMargin = calcTargetValue + 10;
  const calcSuggestedRetail = calcTargetValue >= 0 && calcRetailMargin < 100
    ? calcUnitCost / (1 - calcRetailMargin / 100)
    : null;
  const calcFixedCostValue = Math.max(Number(calcFixedCosts) || 0, 0);
  const calcBreakEvenUnits = calcUnitProfit > 0 ? Math.ceil(calcFixedCostValue / calcUnitProfit) : null;
  const calcBreakEvenRevenue = calcBreakEvenUnits == null ? null : calcBreakEvenUnits * calcSaleValue;
  const calcRoi = calcFixedCostValue > 0 ? calcUnitProfit * calcQuantityValue / calcFixedCostValue * 100 : null;
  const lowStock = activeProducts.filter((product) => product.stock <= product.threshold).length;
  const totalUnits = activeProducts.reduce((sum, product) => sum + product.stock, 0);
  const stockValue = activeProducts.reduce((sum, product) => sum + product.stock * product.cost, 0);
  const exportStockTab = () => {
    const organizationCode = selectedOrganization?.code || 'entreprise';
    if (tab === 'Produits') {
      downloadCsv(`stock-produits-${organizationCode}`, ['Référence', 'Produit', 'Catégorie', 'Fournisseur', 'Quantité', 'Seuil minimum', 'Seuil maximum', 'Coût unitaire', 'Prix de vente', 'Actif'],
        filteredProducts.map((product) => [product.code, product.name, product.category, product.supplier_name, product.stock, product.min_stock, product.max_stock, product.cost, product.price, product.active ? 'Oui' : 'Non']));
    } else if (tab === 'Mouvements') {
      downloadCsv(`stock-mouvements-${organizationCode}`, ['Date', 'Produit', 'Type', 'Quantité', 'Motif', 'Référence'],
        (data?.movements || []).map((movement) => [movement.date, movement.product, movement.type, movement.quantity, movement.source, movement.reference]));
    } else if (tab === 'Ventes') {
      downloadCsv(`stock-ventes-${organizationCode}`, ['N° vente', 'Date', 'Client', 'Total', 'Payé', 'Reste dû', 'Statut', 'Devise'],
        (data?.sales || []).map((sale) => [sale.id, sale.date, sale.customer, sale.total, sale.paid, sale.due, sale.status, sale.currency || settings.currency]));
    }
  };

  useEffect(() => {
    if (activeProducts.length && !activeProducts.some((product) => String(product.id) === movement.productId)) {
      setMovement((current) => ({ ...current, productId: String(activeProducts[0].id) }));
    } else if (!activeProducts.length && movement.productId) {
      setMovement((current) => ({ ...current, productId: '' }));
    }
  }, [activeProducts, movement.productId]);

  const openNewProduct = () => {
    setEditingProduct(null);
    setDraft({ ...emptyProductDraft, supplierId: String(suppliers.find((supplier) => supplier.active)?.id || '') });
    setNotice('');
    setNoticeTone('success');
    setShowProduct(true);
  };

  const openEditProduct = (product) => {
    setEditingProduct(product);
    setDraft({
      name: product.name || '',
      category: product.category || '',
      supplierId: product.supplier_id ? String(product.supplier_id) : '',
      initialQuantity: '0',
      minStock: String(product.min_stock ?? 0),
      maxStock: String(product.max_stock ?? 100),
      purchasePrice: String(product.purchase_price ?? 0),
      salePrice: String(product.sale_price ?? 0),
    });
    setNotice('');
    setNoticeTone('success');
    setShowProduct(true);
  };

  const saveProduct = async (event) => {
    event.preventDefault();
    setNotice('');
    setSaving(true);
    try {
      const result = editingProduct
        ? await updateProduct(organizationId, { id: editingProduct.id, ...draft })
        : await createProduct({ organizationId, storeId, ...draft });
      setShowProduct(false);
      setEditingProduct(null);
      setDraft(emptyProductDraft);
      setNotice(result.message || `${result.code || 'Produit'} enregistré dans le catalogue.`);
      setNoticeTone('success');
      await refresh().catch(() => {});
    } catch (failure) {
      setNotice(failure.message || 'Le produit n’a pas pu être enregistré.');
      setNoticeTone('error');
    } finally {
      setSaving(false);
    }
  };

  const toggleProductActive = async (product) => {
    setBusyProduct(product.id);
    setNotice('');
    try {
      const result = await setProductActive(organizationId, product.id, !product.active);
      setNotice(result.message || 'État du produit mis à jour.');
      setNoticeTone('success');
      await refresh().catch(() => {});
    } catch (failure) {
      setNotice(failure.message || 'L’état du produit n’a pas pu être modifié.');
      setNoticeTone('error');
    } finally {
      setBusyProduct(null);
    }
  };

  const saveMovement = async (event) => {
    event.preventDefault();
    setNotice('');
    setSaving(true);
    try {
      const result = await createStockMovement({
        organizationId,
        productId: Number(movement.productId),
        type: movement.type,
        quantity: movement.quantity,
        unitCost: movement.unitCost || null,
        reason: movement.reason,
        reference: movement.reference,
      });
      setShowMovement(false);
      setMovement((current) => ({ ...current, quantity: '1', reason: '', reference: '' }));
      setNotice(result.message || 'Mouvement de stock enregistré.');
      setNoticeTone('success');
      await refresh().catch(() => {});
    } catch (failure) {
      setNotice(failure.message || 'Le mouvement n’a pas pu être enregistré.');
      setNoticeTone('error');
    } finally {
      setSaving(false);
    }
  };

  if (loading && !data) return <div className="erp-standalone" role="status">Chargement du stock…</div>;
  if (!data) return <InlineMessage tone="error">{loadError || 'Impossible de charger le stock.'}</InlineMessage>;

  return (
    <div className="erp-page">
      <PageHeader
        title="Gestion du stock"
        subtitle="Produits, mouvements et analyses du magasin actif."
        action={<>
          {canExport && ['Produits', 'Mouvements', 'Ventes'].includes(tab) && <ActionButton variant="secondary" onClick={exportStockTab}>Exporter CSV</ActionButton>}
          {canManageStock && tab === 'Mouvements' && <ActionButton variant="secondary" onClick={() => { setNotice(''); setShowMovement(true); }}>＋ Mouvement</ActionButton>}
          {canManageStock && tab === 'Produits' && <ActionButton onClick={openNewProduct}>＋ Nouveau produit</ActionButton>}
        </>}
      />
      {loadError && <InlineMessage tone="error">{loadError}</InlineMessage>}
      {notice && <InlineMessage tone={noticeTone}>{notice}</InlineMessage>}
      <div className="erp-metrics-grid">
        <MetricCard label="Références" value={activeProducts.length} detail="Produits actifs" icon="▦" />
        <MetricCard label="Articles disponibles" value={totalUnits} detail="Unités en stock" icon="▤" tone="green" />
        <MetricCard label="Stock bas" value={lowStock} detail="Sous le seuil défini" icon="⚠" tone="red" />
        <MetricCard label="Valeur du stock" value={formatMoney(stockValue, settings.currency)} detail="Valorisation au coût d’achat" icon="◈" tone="amber" />
      </div>
      <Panel className="erp-tab-panel">
        <Tabs items={canViewSales ? stockTabs : stockTabs.filter((item) => item !== 'Ventes')} value={tab} onChange={setTab} />
        {tab === 'Produits' && (
          <>
            <div className="erp-list-toolbar"><input className="erp-control" placeholder="Rechercher un produit ou une référence…" value={query} onChange={(event) => setQuery(event.target.value)} /><span className="erp-toolbar-count">{filteredProducts.length} résultat(s)</span></div>
            <DataTable columns={[
              { key: 'code', label: 'Référence' }, { key: 'name', label: 'Produit' }, { key: 'category', label: 'Catégorie' },
              { key: 'supplier_name', label: 'Fournisseur', render: (value, product) => value ? `${product.supplier_code} · ${value}` : '—' },
              { key: 'stock', label: 'Quantité', render: (value, product) => <span className={product.active && value <= product.threshold ? 'erp-text-danger' : ''}>{value} unité(s)</span> },
              { key: 'price', label: 'Prix de vente', render: (value) => formatMoney(value, settings.currency) },
              { key: 'status', label: 'État', render: (_, product) => <StatusBadge>{!product.active ? 'Inactif' : product.stock <= product.threshold ? 'Stock bas' : 'Disponible'}</StatusBadge> },
              ...(canManageStock ? [{ key: 'actions', label: 'Actions', render: (_, product) => <div className="erp-row-actions">
                <button className="erp-table-action" type="button" onClick={() => openEditProduct(product)}>Modifier</button>
                <button className="erp-table-action" type="button" disabled={busyProduct === product.id} onClick={() => toggleProductActive(product)}>{product.active ? 'Désactiver' : 'Réactiver'}</button>
              </div> }] : []),
            ]} rows={filteredProducts} />
          </>
        )}
        {tab === 'Mouvements' && <DataTable columns={[
          { key: 'id', label: 'Référence' }, { key: 'date', label: 'Date' }, { key: 'product', label: 'Produit' },
          { key: 'type', label: 'Type', render: (value) => <StatusBadge>{value}</StatusBadge> }, { key: 'quantity', label: 'Quantité' }, { key: 'source', label: 'Motif' },
        ]} rows={data.movements} />}
        {tab === 'Ventes' && canViewSales && <DataTable columns={[
          { key: 'id', label: 'N° vente' }, { key: 'date', label: 'Date' }, { key: 'customer', label: 'Client' },
          { key: 'amount', label: 'Montant', render: (value) => formatMoney(value, settings.currency) }, { key: 'status', label: 'Statut', render: (value) => <StatusBadge>{value}</StatusBadge> },
        ]} rows={data.sales} />}
        {tab === 'Calculs' && <Panel title="Calcul de marge et seuil de rentabilité" description="Estimez la marge d’un produit avec frais supplémentaires et quantité. Ces valeurs ne modifient pas le catalogue.">
          <div className="erp-form-grid">
            <Field label="Produit" value={calcProductId ?? ''} onChange={(id) => {
              setCalcProductId(id);
              const product = activeProducts.find((item) => String(item.id) === id);
              if (product) {
                setCalcPurchase(String(product.cost));
                setCalcSale(String(product.price));
              }
            }} options={[
              { value: '', label: 'Calcul personnalisé' },
              ...activeProducts.map((product) => ({ value: String(product.id), label: product.code + ' · ' + product.name })),
            ]} />
            <Field label={'Prix d’achat unitaire (' + settings.currency + ')'} type="number" min="0" step="0.01" value={calcPurchase} onChange={setCalcPurchase} />
            <Field label={'Prix de vente unitaire (' + settings.currency + ')'} type="number" min="0" step="0.01" value={calcSale} onChange={setCalcSale} />
            <Field label={'Frais supplémentaires totaux (' + settings.currency + ')'} type="number" min="0" step="0.01" value={calcExpenses} onChange={setCalcExpenses} />
            <Field label="Quantité" type="number" min="1" step="1" value={calcQuantity} onChange={setCalcQuantity} />
            <Field label="Marge cible sur le prix de vente (%)" type="number" min="0" max="99" step="0.1" value={calcTargetMargin} onChange={setCalcTargetMargin} />
            <Field label={'Coûts fixes mensuels (' + settings.currency + ')'} type="number" min="0" step="0.01" value={calcFixedCosts} onChange={setCalcFixedCosts} />
          </div>
          <div className="erp-metrics-grid">
            <MetricCard label="Coût unitaire avec frais" value={formatMoney(calcUnitCost, settings.currency)} />
            <MetricCard label="Bénéfice unitaire" value={formatMoney(calcUnitProfit, settings.currency)} />
            <MetricCard label="Marge sur prix de vente" value={calcMarginPercent.toFixed(1) + ' %'} />
            <MetricCard label="Marge sur coût" value={calcCostMarginPercent.toFixed(1) + ' %'} />
            <MetricCard label="Bénéfice total estimé" value={formatMoney(calcUnitProfit * calcQuantityValue, settings.currency)} />
          </div>
          <div className="erp-calculator-grid">
            <article className="erp-calculator-card"><span>Prix conseillé, gros</span><strong>{calcSuggestedPrice == null ? 'Marge cible invalide' : formatMoney(calcSuggestedPrice, settings.currency)}</strong><small>Prix pour atteindre {calcTargetValue.toFixed(1)} % de marge sur le prix de vente.</small></article>
            <article className="erp-calculator-card"><span>Prix conseillé, détail</span><strong>{calcSuggestedRetail == null ? 'Marge cible trop élevée' : formatMoney(calcSuggestedRetail, settings.currency)}</strong><small>Prix conseillé avec 10 points de marge supplémentaires.</small></article>
            <article className="erp-calculator-card"><span>Seuil de rentabilité mensuel</span><strong>{calcBreakEvenUnits == null ? 'Impossible avec une marge nulle ou négative' : calcBreakEvenUnits + ' unité(s)'}</strong><small>{calcBreakEvenRevenue == null ? 'Augmentez le prix de vente ou réduisez les coûts.' : formatMoney(calcBreakEvenRevenue, settings.currency) + ' de chiffre d’affaires estimé.'}</small></article>
            <article className="erp-calculator-card"><span>Retour sur investissement</span><strong>{calcRoi == null ? 'N/A' : calcRoi.toFixed(1) + ' %'}</strong><small>Calculé avec les coûts fixes mensuels saisis.</small></article>
          </div>
        </Panel>}
        {tab === 'Rapports' && (
          <div className="erp-report-grid">
            <div><span>Produits inventoriés</span><strong>{activeProducts.length}</strong></div>
            <div><span>Unités disponibles</span><strong>{totalUnits}</strong></div>
            <div><span>Valeur au coût d’achat</span><strong>{formatMoney(stockValue, settings.currency)}</strong></div>
            <div><span>Références à réapprovisionner</span><strong>{lowStock}</strong></div>
            <p>Indicateurs calculés à partir des produits et mouvements du magasin actif.</p>
          </div>
        )}
      </Panel>
      {showProduct && <Modal title={editingProduct ? `Modifier ${editingProduct.name}` : 'Nouveau produit'} onClose={() => { if (!saving) { setShowProduct(false); setEditingProduct(null); } }} footer={<><ActionButton variant="secondary" onClick={() => { setShowProduct(false); setEditingProduct(null); }} disabled={saving}>Annuler</ActionButton><ActionButton onClick={() => document.getElementById('stock-form').requestSubmit()} disabled={saving}>{saving ? 'Enregistrement…' : editingProduct ? 'Enregistrer les modifications' : 'Créer le produit'}</ActionButton></>}>
        <form id="stock-form" className="erp-form-grid" onSubmit={saveProduct}>
          <div className="erp-field-span"><Field label="Nom du produit" value={draft.name} onChange={(name) => setDraft({ ...draft, name })} required placeholder="Nom du produit" /></div>
          <Field label="Catégorie" value={draft.category} onChange={(category) => setDraft({ ...draft, category })} required />
          <Field label="Fournisseur" value={draft.supplierId} onChange={(supplierId) => setDraft({ ...draft, supplierId })} options={[{ value: '', label: 'Aucun fournisseur' }, ...suppliers.filter((supplier) => supplier.active || String(supplier.id) === draft.supplierId).map((supplier) => ({ value: String(supplier.id), label: `${supplier.code} · ${supplier.name}${supplier.active ? '' : ' (inactif)'}` }))]} />
          {!editingProduct && <Field label="Quantité initiale" type="number" min="0" value={draft.initialQuantity} onChange={(initialQuantity) => setDraft({ ...draft, initialQuantity })} />}
          <Field label="Seuil d’alerte" type="number" min="0" value={draft.minStock} onChange={(minStock) => setDraft({ ...draft, minStock })} required />
          <Field label="Stock maximum" type="number" min={draft.minStock} value={draft.maxStock} onChange={(maxStock) => setDraft({ ...draft, maxStock })} required />
          <Field label="Prix d’achat" type="number" min="0" step="0.01" value={draft.purchasePrice} onChange={(purchasePrice) => setDraft({ ...draft, purchasePrice })} required />
          <Field label="Prix de vente" type="number" min="0" step="0.01" value={draft.salePrice} onChange={(salePrice) => setDraft({ ...draft, salePrice })} required />
          {editingProduct && <p className="erp-field-span erp-modal-copy">Quantité actuelle : <strong>{editingProduct.stock}</strong>. Utilisez un mouvement de stock pour modifier l’inventaire.</p>}
        </form>
      </Modal>}
      {showMovement && <Modal title="Nouveau mouvement de stock" onClose={() => setShowMovement(false)} footer={<><ActionButton variant="secondary" onClick={() => setShowMovement(false)}>Annuler</ActionButton><ActionButton onClick={() => document.getElementById('movement-form').requestSubmit()} disabled={saving || !activeProducts.length}>{saving ? 'Enregistrement…' : 'Enregistrer'}</ActionButton></>}>
        <form id="movement-form" className="erp-form-grid" onSubmit={saveMovement}>
          <label className="erp-field erp-field-span"><span>Produit</span><select value={movement.productId} onChange={(event) => setMovement({ ...movement, productId: event.target.value })} required>{activeProducts.map((product) => <option key={product.id} value={product.id}>{product.code} · {product.name}</option>)}</select></label>
          <Field label="Type" value={movement.type} onChange={(type) => setMovement({ ...movement, type })} options={movementTypes} />
          <Field label="Quantité" type="number" min="1" value={movement.quantity} onChange={(quantity) => setMovement({ ...movement, quantity })} required />
          <Field label={`Coût unitaire (${settings.currency})`} type="number" min="0" step="0.01" value={movement.unitCost} onChange={(unitCost) => setMovement({ ...movement, unitCost })} />
          <Field label="Motif" value={movement.reason} onChange={(reason) => setMovement({ ...movement, reason })} required />
          <Field label="Référence" value={movement.reference} onChange={(reference) => setMovement({ ...movement, reference })} />
        </form>
      </Modal>}
    </div>
  );
}
