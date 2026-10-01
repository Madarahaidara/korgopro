// ============================================================================
// Proformas (mobile) — miroir de web/src/pages/Proformas.jsx.
// Lecture seule (RLS admin pour l'écriture) + détail + lignes.
// ============================================================================
import { useCallback, useEffect, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { getProforma, listProformas } from '../api/proformaApi';
import { formatDate, formatMoney } from '../lib/format';
import { colors, sp } from '../theme';
import { Badge, Banner, Card, Empty, Field, Input, KeyValue, Loading, Modal, SectionTitle } from '../components/ui';

export default function ProformasScreen() {
  const [rows, setRows] = useState([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setRows(await listProformas({ limit: 80 }));
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

  const pick = async (row) => {
    setSelected(row);
    setDetail(null);
    try {
      setDetail(await getProforma(row.id));
    } catch (e) {
      setDetail({ ...row, items: [], _error: e.message });
    }
  };

  const q = query.trim().toLowerCase();
  const searched = rows.filter((p) => {
    if (!q) return true;
    return (
      String(p.number || p.proforma_number || '').toLowerCase().includes(q) ||
      String(p.customer?.full_name || '').toLowerCase().includes(q)
    );
  });

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
    >
      <Card>
        <SectionTitle>Proformas</SectionTitle>
        <Text style={styles.sub}>Devis et cycle de vie (lecture seule sur mobile).</Text>
        <Field label="RECHERCHE">
          <Input value={query} onChangeText={setQuery} placeholder="N°, client…" />
        </Field>
      </Card>

      {loading ? <Loading label="Chargement des proformas…" /> : null}
      {error ? <Banner tone="danger" title="Chargement impossible" message={error} /> : null}
      {!loading && searched.length === 0 ? <Empty title="Aucune proforma" hint="Créez les devis depuis desktop/web." /> : null}

      <Card>
        {searched.map((p) => (
          <Pressable key={p.id} style={styles.row} onPress={() => pick(p)}>
            <View style={styles.grow}>
              <Text style={styles.name}>{p.number || p.proforma_number}</Text>
              <Text style={styles.meta}>{formatDate(p.created_date)} · {p.customer?.full_name || '—'}</Text>
            </View>
            <View style={styles.right}>
              <Text style={styles.total}>{formatMoney(p.total_amount, p.currency)}</Text>
              <Badge text={p.status} tone={p.status === 'CONVERTIE' ? 'info' : p.status === 'ACCEPTEE' ? 'success' : p.status === 'REFUSEE' || p.status === 'EXPIREE' ? 'danger' : 'warning'} />
            </View>
          </Pressable>
        ))}
      </Card>

      <Modal visible={!!selected} title={selected ? `Proforma ${selected.number || selected.proforma_number}` : ''} onClose={() => { setSelected(null); setDetail(null); }}>
        {selected ? (
          <View>
            <KeyValue label="Client" value={selected.customer?.full_name || '—'} />
            <KeyValue label="Date" value={formatDate(selected.created_date)} />
            <KeyValue label="Statut" value={selected.status} />
            <KeyValue label="Total" value={formatMoney(selected.total_amount, selected.currency)} strong />
            {(detail?.items || []).map((it) => (
              <View key={it.id} style={styles.line}>
                <Text style={styles.lineLabel} numberOfLines={1}>{it.description || `Produit #${it.product_id}`}</Text>
                <Text style={styles.lineValue}>{it.quantity} × {formatMoney(it.unit_price, selected.currency)}</Text>
              </View>
            ))}
            <Text style={styles.hint}>Création / conversion : desktop ou web (droits admin).</Text>
          </View>
        ) : null}
      </Modal>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  content: { padding: sp(3), paddingBottom: sp(10), gap: sp(3) },
  sub: { fontSize: 13, color: colors.textMuted, marginTop: sp(1), marginBottom: sp(2) },
  row: { flexDirection: 'row', alignItems: 'center', gap: sp(2), paddingVertical: sp(2.5), borderBottomWidth: 1, borderBottomColor: colors.border },
  grow: { flex: 1, minWidth: 0 },
  name: { fontSize: 15, fontWeight: '700', color: colors.text },
  meta: { fontSize: 12, color: colors.textMuted, marginTop: 2 },
  right: { alignItems: 'flex-end', gap: 4 },
  total: { fontSize: 14, fontWeight: '800', color: colors.primary },
  line: { flexDirection: 'row', justifyContent: 'space-between', gap: sp(2), paddingVertical: sp(1.5), borderBottomWidth: 1, borderBottomColor: colors.border },
  lineLabel: { flex: 1, fontSize: 13, color: colors.text },
  lineValue: { fontSize: 13, fontWeight: '700', color: colors.primary },
  hint: { fontSize: 12, color: colors.textLight, marginTop: sp(2) },
});
