import { useState } from 'react';
import { listProducts, toggleProductActive } from '../api/catalogApi';
import { formatMoney } from '../api/db';
import { useStores } from '../context/StoreContext';
import { Badge, toast } from '../components/ui';
import ProductModal from '../components/ProductModal';

export default function Stock() {
  const { activeId, activeStore } = useStores();
  const [products, setProducts] = useState(() => listProducts(true));
  const [query, setQuery] = useState('');
  const [showNew, setShowNew] = useState(false);
  const [editing, setEditing] = useState(null);
  const [showAll, setShowAll] = useState(false);

  const searched = products.filter((p) => {
    const q = query.toLowerCase();
    return p.name.toLowerCase().includes(q) || p.code.toLowerCase().includes(q) || p.category.toLowerCase().includes(q);
  }).filter((p) => showAll || p.active);

  const refresh = () => setProducts(listProducts(true));

  // Recharge la liste quand le magasin actif change.
  const storeKey = activeId;
  const [lastStoreKey, setLastStoreKey] = useState(storeKey);
  if (storeKey !== lastStoreKey) {
    setLastStoreKey(storeKey);
    setProducts(listProducts(true));
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-title">Stock</div>
          <div className="page-subtitle">
            Produits du magasin <b>{activeStore?.name || '—'}</b> — gérez leur niveau d'inventaire.
          </div>
        </div>
        <div className="flex">
          <label className="flex" style={{ fontSize: 13, color: 'var(--text-muted)' }}>
            <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} /> Inclure inactifs
          </label>
          <input className="input" placeholder="Rechercher…" style={{ width: 200 }} value={query} onChange={(e) => setQuery(e.target.value)} />
          <button className="btn btn-primary" onClick={() => { setEditing(null); setShowNew(true); }}>+ Produit</button>
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflowX: 'auto', overflowY: 'hidden' }}>
        <table className="table">
          <thead>
            <tr>
              <th>Code</th>
              <th>Produit</th>
              <th>Catégorie</th>
              <th>Qté</th>
              <th>Seuil</th>
              <th className="text-right">Achat</th>
              <th className="text-right">Vente</th>
              <th>Statut</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {searched.map((p) => (
              <tr key={p.id}>
                <td className="text-muted">{p.code}</td>
                <td>
                  <b>{p.name}</b>
                  {p.supplierName && <div className="text-muted" style={{ fontSize: 12 }}>{p.supplierName}</div>}
                </td>
                <td><Badge status={p.category} /></td>
                <td>
                  <div className="flex">
                    <b>{p.quantity}</b>
                    <StockBar quantity={p.quantity} min={p.min_stock} />
                  </div>
                </td>
                <td>{p.min_stock}</td>
                <td className="text-right">{formatMoney(p.purchase_price)}</td>
                <td className="text-right"><b>{formatMoney(p.sale_price)}</b></td>
                <td>
                  {p.isOutOfStock ? <Badge status="RUPTURE" /> : p.isLowStock ? <Badge status="LOW" /> : <Badge status="ACTIF" />}
                </td>
                <td>
                  <div className="flex">
                    <button className="btn btn-sm" onClick={() => { setEditing(p); setShowNew(true); }}>Éditer</button>
                    <button
                      className="btn btn-sm"
                      onClick={() => { toggleProductActive(p.id); refresh(); toast(p.active ? 'Produit désactivé.' : 'Produit réactivé.'); }}
                    >
                      {p.active ? 'Désactiver' : 'Activer'}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {searched.length === 0 && <tr><td colSpan={9}><div className="empty">Aucun produit.</div></td></tr>}
          </tbody>
        </table>
      </div>

      {showNew && (
        <ProductModal
          product={editing}
          onSave={() => { refresh(); setShowNew(false); toast('Produit enregistré.'); }}
          onClose={() => setShowNew(false)}
        />
      )}
    </div>
  );
}

function StockBar({ quantity, min }) {
  const max = Math.max(min * 2, quantity);
  const pct = Math.min(100, (quantity / max) * 100);
  const color = quantity <= 0 ? 'var(--danger)' : quantity <= min ? 'var(--warning)' : 'var(--success)';
  return (
    <div className="stock-bar"><div style={{ width: `${pct}%`, background: color }} /></div>
  );
}