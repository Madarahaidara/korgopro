// ============================================================================
// Administration (mobile) — miroir de web/src/pages/Admin.jsx.
// Réservé ADMIN : diagnostic système + contexte serveur (rôle/permissions).
// (Gestion users/logs/données : desktop/web, RLS admin-only sans RPC mobile.)
// ============================================================================
import { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { checkHealth } from '../api/systemApi';
import { useAuth } from '../context/AuthContext';
import { colors, sp } from '../theme';
import { Banner, Card, ChipGroup, Empty, KeyValue, Loading, SectionTitle } from '../components/ui';
import Icon from '../components/Icon';

const TABS = [
  { id: 'overview', label: "Vue d'ensemble" },
  { id: 'server', label: 'Serveur' },
  { id: 'users', label: 'Utilisateurs' },
  { id: 'activity', label: 'Journal' },
  { id: 'data', label: 'Données' },
];

export default function AdminScreen() {
  const { user } = useAuth();
  const [tab, setTab] = useState('overview');
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setHealth(await checkHealth());
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

  if (user?.role !== 'ADMIN' && String(user?.role || '').toUpperCase() !== 'ADMIN') {
    return (
      <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
        <Card>
          <View style={styles.center}>
            <Icon name="admin" size={40} color={colors.textLight} />
            <Text style={styles.title}>Accès réservé</Text>
            <Text style={styles.meta}>L'administration est réservée aux administrateurs.</Text>
          </View>
        </Card>
      </ScrollView>
    );
  }

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
    >
      <Card>
        <SectionTitle>Administration</SectionTitle>
        <Text style={styles.meta}>Système, serveurs et données.</Text>
        <View style={styles.tabs}>
          <ChipGroup options={TABS.map((t) => ({ value: t.id, label: t.label }))} value={tab} onChange={setTab} />
        </View>
      </Card>

      {loading ? <Loading label="Diagnostic en cours…" /> : null}
      {error ? <Banner tone="danger" title="Diagnostic impossible" message={error} /> : null}

      {tab === 'overview' || tab === 'server' ? (
        <Card>
          <SectionTitle>Serveur Supabase</SectionTitle>
          <KeyValue label="Statut" value={health?.status || '—'} />
          <KeyValue label="Latence" value={health?.latency != null ? `${health.latency} ms` : '—'} />
          <KeyValue label="Source" value={health?.served_by || '—'} />
          <KeyValue label="Message" value={health?.message || '—'} />
          <KeyValue label="Requêtes" value={health?.requests != null ? String(health.requests) : '—'} />
          <KeyValue label="Rôle serveur" value={health?.context?.role || '—'} />
        </Card>
      ) : (
        <Card>
          <Empty title="Module desktop/web" hint="Utilisateurs, journal et données : administrez depuis desktop ou web (RLS admin-only)." />
        </Card>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  content: { padding: sp(3), paddingBottom: sp(10), gap: sp(3) },
  meta: { fontSize: 13, color: colors.textMuted, marginTop: sp(1) },
  tabs: { marginTop: sp(2) },
  center: { alignItems: 'center', gap: sp(2), paddingVertical: sp(4) },
  title: { fontSize: 17, fontWeight: '800', color: colors.text },
});
