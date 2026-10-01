// ============================================================================
// Trésorerie (mobile) — miroir de web/src/pages/Treasury.jsx.
// Lecture : comptes + synthèse + derniers mouvements. Écritures : RPC/admin.
// ============================================================================
import { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { TYPE_LABELS, listAccounts, listClosures, listMovements, periodLabel, treasurySummary } from '../api/treasuryApi';
import { formatDate, formatMoney } from '../lib/format';
import { colors, sp } from '../theme';
import { Badge, Banner, Card, Empty, Loading, SectionTitle, StatCard } from '../components/ui';
import Icon from '../components/Icon';

export default function TreasuryScreen() {
  const [accounts, setAccounts] = useState([]);
  const [movements, setMovements] = useState([]);
  const [summary, setSummary] = useState(null);
  const [closures, setClosures] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [accs, movs, sum, clos] = await Promise.all([
        listAccounts(),
        listMovements({ limit: 40 }),
        treasurySummary(),
        listClosures({ limit: 12 }).catch(() => []),
      ]);
      setAccounts(accs);
      setMovements(movs);
      setSummary(sum);
      setClosures(clos);
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

  const currency = accounts[0]?.currency || 'FCFA';

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
    >
      <Card>
        <SectionTitle>Trésorerie</SectionTitle>
        <Text style={styles.sub}>Comptes, soldes et derniers mouvements.</Text>
      </Card>

      {loading ? <Loading label="Chargement de la trésorerie…" /> : null}
      {error ? <Banner tone="danger" title="Chargement impossible" message={error} /> : null}

      {summary ? (
        <View style={styles.grid}>
          <StatCard icon={<Icon name="treasury" size={20} color="#2f6fed" />} label="Solde total" value={formatMoney(summary.total, currency)} color="#2f6fed" />
          <StatCard icon={<Icon name="cash" size={20} color="#1a9e5e" />} label="Caisse" value={formatMoney(summary.byType.CASH || 0, currency)} color="#1a9e5e" />
          <StatCard icon={<Icon name="treasury" size={20} color="#e5a50a" />} label="Banque" value={formatMoney(summary.byType.BANK || 0, currency)} color="#e5a50a" />
          <StatCard icon={<Icon name="phone" size={20} color="#0ea5c9" />} label="Mobile Money" value={formatMoney(summary.byType.MOBILE_MONEY || 0, currency)} color="#0ea5c9" />
        </View>
      ) : null}

      <Card>
        <SectionTitle>Comptes</SectionTitle>
        {accounts.length === 0 && !loading ? <Empty title="Aucun compte" hint="Créez les comptes depuis desktop/web." /> : null}
        {accounts.map((a) => (
          <View key={a.id} style={styles.row}>
            <View style={styles.grow}>
              <Text style={styles.name}>{a.name}</Text>
              <Text style={styles.meta}>{TYPE_LABELS[a.account_type] || a.account_type}</Text>
            </View>
            <Text style={styles.balance}>{formatMoney(a.balance, a.currency)}</Text>
          </View>
        ))}
      </Card>

      <Card>
        <SectionTitle>Mouvements récents</SectionTitle>
        {movements.length === 0 && !loading ? <Empty title="Aucun mouvement" hint="Les ventes et encaissements alimentent la trésorerie." /> : null}
        {movements.map((m) => (
          <View key={m.id} style={styles.row}>
            <View style={styles.grow}>
              <Text style={styles.name} numberOfLines={1}>{m.description || m.reference || 'Mouvement'}</Text>
              <Text style={styles.meta}>{formatDate(m.date)} · {m.accountName || ''}</Text>
            </View>
            <Text style={[styles.amount, { color: m.movement_type === 'IN' ? colors.success : colors.danger }]}>
              {m.movement_type === 'IN' ? '+' : '-'}{formatMoney(m.amount, currency)}
            </Text>
          </View>
        ))}
      </Card>

      <Card>
        <SectionTitle>Clôtures mensuelles</SectionTitle>
        {closures.length === 0 && !loading ? <Empty title="Aucune clôture" hint="Les clôtures sont gérées côté admin." /> : null}
        {closures.map((c) => (
          <View key={c.id} style={styles.row}>
            <View style={styles.grow}>
              <Text style={styles.name}>{periodLabel(c.period)}</Text>
              <Text style={styles.meta}>{c.sales_count ?? '—'} vente(s)</Text>
            </View>
            <Badge text={c.status === 'CLOSED' ? 'Clôturé' : c.status || '—'} tone={c.status === 'CLOSED' ? 'success' : 'neutral'} />
          </View>
        ))}
      </Card>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  content: { padding: sp(3), paddingBottom: sp(10), gap: sp(3) },
  sub: { fontSize: 13, color: colors.textMuted, marginTop: sp(1) },
  grid: { gap: sp(2) },
  row: { flexDirection: 'row', alignItems: 'center', gap: sp(2), paddingVertical: sp(2.5), borderBottomWidth: 1, borderBottomColor: colors.border },
  grow: { flex: 1, minWidth: 0 },
  name: { fontSize: 14, fontWeight: '600', color: colors.text },
  meta: { fontSize: 12, color: colors.textMuted, marginTop: 2 },
  balance: { fontSize: 15, fontWeight: '800', color: colors.primary },
  amount: { fontSize: 14, fontWeight: '800' },
});
