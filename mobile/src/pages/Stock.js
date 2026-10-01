// ============================================================================
// Stock (mobile) — miroir de web/src/pages/Stock.jsx (liste + statuts).
// Création/édition produit : réservé admin (RLS) — voir Inventaire (mouvements).
// ============================================================================
import { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { listProducts } from '../api/catalogApi';
import { useStores } from '../context/StoreContext';
import { formatMoney } from '../lib/format';
import { colors, sp } from '../theme';
import { Badge, Banner, Card, Empty, Field, Input, Loading, SectionTitle } from '../components/ui';

export default function StockScreen() {
  const { activeId, activeStore } = useStores();
  const [products, setProducts] = useState([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setProducts(await listProducts({ storeId: activeId, limit: 120 }));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [activeId]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  const q = query.trim().toLowerCase();
  const searched = products.filter((p) => {
    if (!q) return true;
    return (
      String(p.name || '').toLowerCase().includes(q) ||
      String(p.code || '').toLowerCase().includes(q) ||
      String(p.category || '').toLowerCase().includes(q)
    );
  });

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
    >
      <Card>
        <SectionTitle>Stock</SectionTitle>
        <Text style={styles.sub}>Produits du magasin <Text style={styles.strong}>{activeStore?.name || '—'}</Text>.</Text>
        <Field label="RECHERCHE">
          <Input value={query} onChangeText={setQuery} placeholder="Nom, code, catégorie…" />
        </Field>
      </Card>

      {loading ? <Loading label="Chargement du stock…" /> : null}
      {error ? <Banner tone="danger" title="Chargement impossible" message={error} /> : null}
      {!loading && searched.length === 0 ? <Empty title="Aucun produit" hint="Élargissez la recherche ou changez de magasin." /> : null}

      <Card>
        {searched.map((p) => (
          <View key={p.id} style={styles.row}>
            <View style={styles.grow}>
              <Text style={styles.name} numberOfLines={1}>{p.name}</Text>
              <Text style={styles.meta}>{p.code} · {formatMoney(p.sale_price)}</Text>
            </View>
            <Badge text={p.isOutOfStock ? 'Rupture' : p.isLowStock ? `${p.quantity} u · bas` : `${p.quantity} u`} tone={p.isOutOfStock ? 'danger' : p.isLowStock ? 'warning' : 'success'} />
          </View>
        ))}
      </Card>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  content: { padding: sp(3), paddingBottom: sp(10), gap: sp(3) },
  sub: { fontSize: 13, color: colors.textMuted, marginTop: sp(1), marginBottom: sp(2) },
  strong: { fontWeight: '800', color: colors.text },
  row: { flexDirection: 'row', alignItems: 'center', gap: sp(2), paddingVertical: sp(2.5), borderBottomWidth: 1, borderBottomColor: colors.border },
  grow: { flex: 1, minWidth: 0 },
  name: { fontSize: 15, fontWeight: '600', color: colors.text },
  meta: { fontSize: 12, color: colors.textMuted, marginTop: 2 },
});
