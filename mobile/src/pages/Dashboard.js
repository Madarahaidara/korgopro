// ============================================================================
// Dashboard (mobile) — miroir de web/src/pages/Dashboard.jsx.
// Mêmes blocs : accueil, 4 stats, 7 derniers jours, alertes, vue d'ensemble,
// trésorerie, modules disponibles. Données via statsApi (PostgREST à la demande).
// ============================================================================
import { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { getDashboardStats } from '../api/statsApi';
import { useAuth } from '../context/AuthContext';
import { useStores } from '../context/StoreContext';
import { formatMoney } from '../lib/format';
import { colors, sp } from '../theme';
import { Banner, Card, Empty, Loading, SectionTitle, StatCard } from '../components/ui';
import Icon from '../components/Icon';

export default function DashboardScreen({ navigation }) {
  const { user, settings } = useAuth();
  const { activeId, activeStore } = useStores();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const currency = settings?.currency || 'FCFA';

  const load = useCallback(async () => {
    if (activeId == null) {
      setLoading(false);
      return;
    }
    setError(null);
    try {
      const s = await getDashboardStats({ storeId: activeId });
      setStats(s);
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

  const maxAmount = Math.max(1, ...(stats?.last7 || []).map((d) => d.amount || 0));

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
    >
      <Card>
        <Text style={styles.hello}>Bonjour, {user?.username || '—'}</Text>
        <Text style={styles.sub}>Voici l'activité de {activeStore?.name || 'votre entreprise'}.</Text>
      </Card>

      {loading ? <Loading label="Chargement du tableau de bord…" /> : null}
      {error ? <Banner tone="danger" title="Chargement impossible" message={error} /> : null}
      {!loading && !stats ? (
        <Empty title="Aucune donnée" hint="Sélectionnez un magasin puis tirez pour rafraîchir." />
      ) : null}

      {stats ? (
        <>
          <View style={styles.grid2}>
            <StatCard icon={<Icon name="receipt" size={20} color="#2f6fed" />} label="Ventes (total)" value={formatMoney(stats.totalSales, currency)} color="#2f6fed" />
            <StatCard icon={<Icon name="cash" size={20} color="#1a9e5e" />} label="Ventes du jour" value={formatMoney(stats.salesToday, currency)} color="#1a9e5e" />
            <StatCard icon={<Icon name="stock" size={20} color="#e5a50a" />} label="Valeur du stock" value={formatMoney(stats.stockValue, currency)} color="#e5a50a" />
            <StatCard icon={<Icon name="wallet" size={20} color="#0ea5c9" />} label="Trésorerie" value={formatMoney(stats.cashBalance, currency)} color="#0ea5c9" />
          </View>

          <Card>
            <SectionTitle>Ventes — 7 derniers jours</SectionTitle>
            <View style={styles.bars}>
              {(stats.last7 || []).map((d, i) => (
                <View key={i} style={styles.barCol}>
                  <View style={[styles.bar, { height: Math.max(4, ((d.amount || 0) / maxAmount) * 90) }]} />
                  <Text style={styles.barLabel} numberOfLines={1}>{d.label}</Text>
                </View>
              ))}
            </View>
          </Card>

          <Card>
            <SectionTitle>Alertes stock</SectionTitle>
            <View style={styles.row}>
              <Text style={styles.meta}>Stock bas : <Text style={styles.strong}>{stats.lowStock}</Text></Text>
              <Text style={styles.meta}>Rupture : <Text style={styles.strong}>{stats.outOfStock}</Text></Text>
            </View>
          </Card>

          <Card>
            <SectionTitle>Vue d'ensemble</SectionTitle>
            <View style={styles.metrics}>
              <Metric label="Produits" value={stats.productCount} />
              <Metric label="Clients" value={stats.customerCount} />
              <Metric label="Ventes" value={stats.salesCount} />
              <Metric label="Proformas en attente" value={stats.proformaPending} />
            </View>
          </Card>
        </>
      ) : null}
    </ScrollView>
  );
}

function Metric({ label, value }) {
  return (
    <View style={styles.metric}>
      <Text style={styles.metricValue}>{String(value ?? '—')}</Text>
      <Text style={styles.metricLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  content: { padding: sp(3), paddingBottom: sp(10), gap: sp(3) },
  hello: { fontSize: 18, fontWeight: '800', color: colors.text },
  sub: { fontSize: 13, color: colors.textMuted, marginTop: sp(1) },
  grid2: { gap: sp(2) },
  bars: { flexDirection: 'row', alignItems: 'flex-end', gap: sp(1.5), height: 120, marginTop: sp(2) },
  barCol: { flex: 1, alignItems: 'center', justifyContent: 'flex-end', gap: 4 },
  bar: { width: '70%', backgroundColor: colors.primary, borderRadius: 4 },
  barLabel: { fontSize: 10, color: colors.textMuted },
  row: { flexDirection: 'row', justifyContent: 'space-between', gap: sp(2), marginTop: sp(1) },
  meta: { fontSize: 13, color: colors.textMuted },
  strong: { fontWeight: '800', color: colors.text },
  metrics: { flexDirection: 'row', flexWrap: 'wrap', gap: sp(3), marginTop: sp(1) },
  metric: { minWidth: '45%', flexGrow: 1 },
  metricValue: { fontSize: 17, fontWeight: '800', color: colors.text },
  metricLabel: { fontSize: 12, color: colors.textMuted },
});
