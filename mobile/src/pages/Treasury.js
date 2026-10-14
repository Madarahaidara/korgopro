// ============================================================================
// Trésorerie (mobile) — miroir de web/src/pages/Treasury.jsx.
// Lecture : comptes + synthèse + derniers mouvements + clôtures.
// Écriture : modales Nouveau compte / Nouveau mouvement (RPC app_treasury_*)
// et clôture mensuelle (ADMIN strict, comme le web).
// ============================================================================
import { useCallback, useEffect, useState } from 'react';
import { Alert, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import {
  TYPE_LABELS,
  closeMonth,
  computeMonthlyPreview,
  listAccounts,
  listClosures,
  listMovements,
  monthPeriod,
  periodLabel,
  treasurySummary,
} from '../api/treasuryApi';
import { formatDate, formatMoney } from '../lib/format';
import { useAuth } from '../context/AuthContext';
import { colors, sp } from '../theme';
import { Badge, Banner, Btn, Card, Empty, Loading, SectionTitle, StatCard } from '../components/ui';
import AccountModal from '../components/AccountModal';
import MovementModal from '../components/MovementModal';
import Icon from '../components/Icon';

export default function TreasuryScreen() {
  const { user, can, isAdmin } = useAuth();
  const [accounts, setAccounts] = useState([]);
  const [movements, setMovements] = useState([]);
  const [summary, setSummary] = useState(null);
  const [closures, setClosures] = useState([]);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [showAccount, setShowAccount] = useState(false);
  const [showMovement, setShowMovement] = useState(false);

  const canManage = can('manage_treasury');
  const currentPeriod = monthPeriod();

  const load = useCallback(async () => {
    setError(null);
    try {
      const [accs, movs, sum, clos, prev] = await Promise.all([
        listAccounts(),
        listMovements({ limit: 40 }),
        treasurySummary(),
        listClosures({ limit: 12 }).catch(() => []),
        computeMonthlyPreview(currentPeriod).catch(() => null),
      ]);
      setAccounts(accs);
      setMovements(movs);
      setSummary(sum);
      setClosures(clos);
      setPreview(prev);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [currentPeriod]);

  useEffect(() => {
    load();
  }, [load]);

  const currency = accounts[0]?.currency || 'FCFA';
  const currentClosure = closures.find((c) => c.period === currentPeriod) || null;
  const closed = currentClosure?.status === 'CLOSED';
  const shown = currentClosure || preview;

  const onCloseMonth = () => {
    if (!shown) return;
    Alert.alert(
      `Clôturer ${periodLabel(currentPeriod)} ?`,
      `Les totaux du mois seront figés : ${shown.sales_count} vente(s), `
        + `encaissé ${formatMoney(shown.total_collected, currency)}.\n`
        + 'Cette action est enregistrée dans la base.',
      [
        { text: 'Annuler', style: 'cancel' },
        {
          text: 'Clôturer',
          style: 'destructive',
          onPress: async () => {
            try {
              await closeMonth(currentPeriod, user);
              load();
            } catch (e) {
              Alert.alert('Clôture refusée', e.message);
            }
          },
        },
      ]
    );
  };

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
    >
      <Card>
        <SectionTitle
          right={
            canManage ? (
              <View style={styles.actions}>
                <Btn title="+ Compte" variant="ghost" onPress={() => setShowAccount(true)} style={styles.actionBtn} />
                <Btn title="+ Mouvement" onPress={() => setShowMovement(true)} style={styles.actionBtn} />
              </View>
            ) : null
          }
        >
          Trésorerie
        </SectionTitle>
        <Text style={styles.sub}>Suivez vos comptes, entrées et sorties d'argent.</Text>
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
        {accounts.length === 0 && !loading ? (
          <Empty
            title="Aucun compte"
            hint={canManage ? 'Créez votre premier compte avec « + Compte ».' : 'Créez les comptes depuis desktop/web.'}
          />
        ) : null}
        {accounts.map((a) => (
          <View key={a.id} style={styles.row}>
            <View style={styles.grow}>
              <Text style={styles.name}>{a.name}</Text>
              <Text style={styles.meta}>
                {TYPE_LABELS[a.account_type] || a.account_type}
                {a.is_default ? ' · Défaut' : ''}
              </Text>
            </View>
            <Text style={styles.balance}>{formatMoney(a.balance, a.currency)}</Text>
          </View>
        ))}
      </Card>

      {/* ------------------------------------------------------------------
          Clôture mensuelle : aperçu du mois courant (calcul serveur) +
          bouton réservé aux administrateurs, comme web/src/pages/Treasury.jsx.
          ------------------------------------------------------------------ */}
      <Card>
        <SectionTitle>Clôture mensuelle — {periodLabel(currentPeriod)}</SectionTitle>
        <Text style={styles.sub}>
          {closed
            ? `Mois clôturé${currentClosure.closed_at ? ` le ${formatDate(currentClosure.closed_at)}` : ''}. Les totaux sont figés.`
            : 'Ventes du mois en cours. Clôturez en fin de mois pour figer les totaux.'}
        </Text>
        {shown ? (
          <View style={styles.grid}>
            <StatCard icon={<Icon name="sale" size={20} color="#2f6fed" />} label="Ventes" value={`${shown.sales_count} · ${formatMoney(shown.total_sales, currency)}`} color="#2f6fed" />
            <StatCard icon={<Icon name="cash" size={20} color="#1a9e5e" />} label="Encaissé" value={formatMoney(shown.total_collected, currency)} color="#1a9e5e" />
            <StatCard icon={<Icon name="clock" size={20} color="#e5a50a" />} label="Crédit (reste dû)" value={formatMoney(shown.total_credit, currency)} color="#e5a50a" />
            <StatCard icon={<Icon name="wallet" size={20} color="#ef4444" />} label="Dépenses" value={formatMoney(shown.total_out, currency)} color="#ef4444" />
            <StatCard icon={<Icon name="treasury" size={20} color="#8b5cf6" />} label="Net" value={formatMoney(shown.net, currency)} color="#8b5cf6" />
          </View>
        ) : null}
        {isAdmin() ? (
          <Btn
            title={closed ? 'Mois clôturé' : 'Clôturer le mois'}
            disabled={closed || !shown}
            onPress={onCloseMonth}
            style={styles.closeBtn}
          />
        ) : (
          <Text style={styles.adminHint}>La clôture mensuelle est réservée aux administrateurs.</Text>
        )}
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
        {closures.length === 0 && !loading ? <Empty title="Aucune clôture" hint="Clôturez le mois en cours depuis la carte ci-dessus." /> : null}
        {closures.map((c) => (
          <View key={c.id} style={styles.row}>
            <View style={styles.grow}>
              <Text style={styles.name}>{periodLabel(c.period)}</Text>
              <Text style={styles.meta}>{c.sales_count ?? '—'} vente(s) · net {formatMoney(c.net, currency)}</Text>
            </View>
            <Badge text={c.status === 'CLOSED' ? 'Clôturé' : c.status || '—'} tone={c.status === 'CLOSED' ? 'success' : 'neutral'} />
          </View>
        ))}
      </Card>

      {showAccount ? (
        <AccountModal
          onSave={() => { setShowAccount(false); load(); }}
          onClose={() => setShowAccount(false)}
        />
      ) : null}

      {showMovement ? (
        <MovementModal
          accounts={accounts}
          onSave={() => { setShowMovement(false); load(); }}
          onClose={() => setShowMovement(false)}
        />
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  content: { padding: sp(3), paddingBottom: sp(10), gap: sp(3) },
  sub: { fontSize: 13, color: colors.textMuted, marginTop: sp(1) },
  grid: { gap: sp(2), marginTop: sp(2) },
  actions: { flexDirection: 'row', gap: sp(2) },
  actionBtn: { paddingHorizontal: sp(2) },
  adminHint: { fontSize: 12, color: colors.textMuted, marginTop: sp(2) },
  closeBtn: { marginTop: sp(3) },
  row: { flexDirection: 'row', alignItems: 'center', gap: sp(2), paddingVertical: sp(2.5), borderBottomWidth: 1, borderBottomColor: colors.border },
  grow: { flex: 1, minWidth: 0 },
  name: { fontSize: 14, fontWeight: '600', color: colors.text },
  meta: { fontSize: 12, color: colors.textMuted, marginTop: 2 },
  balance: { fontSize: 15, fontWeight: '800', color: colors.primary },
  amount: { fontSize: 14, fontWeight: '800' },
});
