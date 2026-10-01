// ============================================================================
// Clients (mobile) — miroir de web/src/pages/Customers.jsx.
// Lecture seule (RLS admin pour l'écriture) + recherche.
// ============================================================================
import { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { listCustomers } from '../api/catalogApi';
import { formatMoney } from '../lib/format';
import { colors, sp } from '../theme';
import { Badge, Banner, Card, Empty, Field, Input, Loading, SectionTitle } from '../components/ui';

export default function CustomersScreen() {
  const [rows, setRows] = useState([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setRows(await listCustomers({ limit: 120 }));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const q = query.trim().toLowerCase();
  const searched = rows.filter((c) => {
    if (!q) return true;
    return (
      String(c.first_name || '').toLowerCase().includes(q) ||
      String(c.last_name || '').toLowerCase().includes(q) ||
      String(c.company || '').toLowerCase().includes(q) ||
      String(c.code || '').toLowerCase().includes(q)
    );
  });

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
    >
      <Card>
        <SectionTitle>Clients</SectionTitle>
        <Text style={styles.sub}>Portefeuille clients (lecture seule sur mobile).</Text>
        <Field label="RECHERCHE">
          <Input value={query} onChangeText={setQuery} placeholder="Nom, société, code…" />
        </Field>
      </Card>

      {loading ? <Loading label="Chargement des clients…" /> : null}
      {error ? <Banner tone="danger" title="Chargement impossible" message={error} /> : null}
      {!loading && searched.length === 0 ? <Empty title="Aucun client" hint="Créez les clients depuis desktop/web." /> : null}

      <Card>
        {searched.map((c) => (
          <View key={c.id} style={styles.row}>
            <View style={styles.grow}>
              <Text style={styles.name} numberOfLines={1}>
                {[c.first_name, c.last_name].filter(Boolean).join(' ') || c.company || 'Client'}
              </Text>
              <Text style={styles.meta}>{c.company || c.phone || c.email || c.code || ''}</Text>
            </View>
            <View style={styles.right}>
              <Badge text={c.customer_type || 'RETAIL'} tone="neutral" />
              <Text style={styles.limit}>{formatMoney(c.credit_limit || 0)}</Text>
            </View>
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
  row: { flexDirection: 'row', alignItems: 'center', gap: sp(2), paddingVertical: sp(2.5), borderBottomWidth: 1, borderBottomColor: colors.border },
  grow: { flex: 1, minWidth: 0 },
  name: { fontSize: 15, fontWeight: '600', color: colors.text },
  meta: { fontSize: 12, color: colors.textMuted, marginTop: 2 },
  right: { alignItems: 'flex-end', gap: 4 },
  limit: { fontSize: 12, color: colors.textMuted },
});
