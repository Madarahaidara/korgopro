// ============================================================================
// Factures / Registre (mobile) — miroir de web/src/pages/Invoices.jsx.
// Filtres par statut + recherche + aperçu facture.
// ============================================================================
import { useCallback, useEffect, useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { listSales } from '../api/salesApi';
import { formatDate, formatMoney } from '../lib/format';
import { colors, sp } from '../theme';
import { Badge, Banner, Card, ChipGroup, Empty, Field, Input, KeyValue, Loading, Modal, SectionTitle } from '../components/ui';
import { SuccessOverlay } from '../components/Feedback';
import { AnnulerForm, EncaisserForm } from '../components/SaleActions';
import DocumentActions from '../components/DocumentActions';
import { getSale } from '../api/salesApi';
import { invoiceHtml } from '../lib/documents';

/** Délai avant la confirmation animée : laisse la modale de détail se fermer. */
const OVERLAY_DELAY = 350;

/** Libellés de statut (miroir des badges web). */
const STATUT_LABELS = {
  EMISE: 'Émise',
  PAYEE: 'Payée',
  PARTIELLEMENT_PAYEE: 'Partielle',
  ANNULEE: 'Annulée',
  REFUSEE: 'Refusée',
};

/** Ton du badge : annulée en rouge, payée en vert, partielle en orange. */
function statutTone(statut) {
  const s = String(statut || 'EMISE').toUpperCase();
  if (s === 'ANNULEE' || s === 'REFUSEE') return 'danger';
  if (s === 'PAYEE') return 'success';
  if (s === 'PARTIELLEMENT_PAYEE') return 'warning';
  return 'info';
}

const FILTERS = [
  { value: 'TOUTES', label: 'Toutes' },
  { value: 'EMISE', label: 'Émise' },
  { value: 'PARTIELLEMENT_PAYEE', label: 'Partielle' },
  { value: 'PAYEE', label: 'Payée' },
  { value: 'ANNULEE', label: 'Annulée' },
];

export default function InvoicesScreen() {
  const [sales, setSales] = useState([]);
  const [filter, setFilter] = useState('TOUTES');
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [validation, setValidation] = useState(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setSales(await listSales({ limit: 100 }));
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

  const pick = async (sale) => {
    setSelected(sale);
    setDetail(null);
    setDetailLoading(true);
    try {
      setDetail(await getSale(sale.id));
    } catch (e) {
      setDetail({ ...sale, items: [], _detailError: e.message });
    } finally {
      setDetailLoading(false);
    }
  };

  /**
   * Après un encaissement / une annulation : refermer l'aperçu, recharger la
   * liste puis afficher la confirmation animée (le léger différé laisse la
   * modale d'aperçu terminer son fondu de fermeture).
   */
  const afterAction = ({ summary } = {}) => {
    setSelected(null);
    setDetail(null);
    load();
    if (summary) setTimeout(() => setValidation(summary), OVERLAY_DELAY);
  };

  const q = query.trim().toLowerCase();
  const filtered = sales.filter((s) => {
    const okFilter = filter === 'TOUTES' || (s.statut || 'EMISE') === filter;
    const okQuery =
      !q ||
      String(s.sale_number || '').toLowerCase().includes(q) ||
      String(s.customer_name || '').toLowerCase().includes(q);
    return okFilter && okQuery;
  });

  return (
    <KeyboardAvoidingView
      style={styles.screen}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
      keyboardDismissMode="on-drag"
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
    >
      <Card>
        <SectionTitle>Facturation</SectionTitle>
        <Text style={styles.sub}>Registre de toutes vos factures.</Text>
        <Field label="STATUT">
          <ChipGroup options={FILTERS} value={filter} onChange={setFilter} />
        </Field>
        <Field label="RECHERCHE">
          <Input value={query} onChangeText={setQuery} placeholder="N°, client…" />
        </Field>
      </Card>

      {loading ? <Loading label="Chargement des factures…" /> : null}
      {error ? <Banner tone="danger" title="Chargement impossible" message={error} /> : null}
      {!loading && filtered.length === 0 ? <Empty title="Aucune facture" hint="Aucune facture pour ce filtre." /> : null}

      <Card>
        {filtered.map((s) => {
          const cancelled = s.sale_status === 'CANCELLED';
          return (
            <Pressable
              key={s.id}
              style={[styles.row, cancelled ? styles.rowCancelled : null]}
              onPress={() => pick(s)}
            >
              <View style={styles.grow}>
                <Text style={styles.name}>{s.sale_number}</Text>
                <Text style={styles.meta}>{formatDate(s.sale_date)} · {s.customer_name}</Text>
              </View>
              <View style={styles.right}>
                <Text style={styles.total}>{formatMoney(s.total_amount)}</Text>
                <Badge
                  text={STATUT_LABELS[s.statut] || s.statut || 'EMISE'}
                  tone={statutTone(s.statut)}
                />
                {!cancelled && s.due > 0.001 ? (
                  <Text style={styles.due}>Reste {formatMoney(s.due)}</Text>
                ) : null}
              </View>
            </Pressable>
          );
        })}
      </Card>

      <Modal visible={!!selected} title={selected ? `Facture ${selected.sale_number}` : 'Facture'} onClose={() => { setSelected(null); setDetail(null); }}>
        {selected ? (
          <View>
            {detailLoading ? <Loading label="Chargement du détail de la facture…" /> : null}
            {detail?._detailError ? <Banner tone="warning" title="Détail incomplet" message={detail._detailError} /> : null}
            <Text style={styles.invoiceTitle}>FACTURE</Text>
            <Text style={styles.meta}>N° {selected.sale_number} · {formatDate(selected.sale_date)}</Text>
            <KeyValue label="Client" value={selected.customer_name} />
            {(detail?.items || []).map((item) => (
              <View key={item.id} style={styles.itemRow}>
                <Text style={styles.itemName}>{item.products?.name || `Article #${item.product_id}`} · {item.quantity}</Text>
                <Text style={styles.itemPrice}>{formatMoney(item.line_total, detail?.currency)}</Text>
              </View>
            ))}
            <KeyValue label="Sous-total" value={formatMoney(detail?.subtotal ?? selected.subtotal ?? selected.total_amount, detail?.currency)} />
            <KeyValue label="Remise" value={formatMoney(detail?.discount_amount ?? selected.discount_amount ?? 0, detail?.currency)} />
            <KeyValue label="Taxe" value={formatMoney(detail?.tax_amount ?? selected.tax_amount ?? 0, detail?.currency)} />
            <KeyValue label="Total" value={formatMoney(detail?.total_amount ?? selected.total_amount, detail?.currency)} strong />
            <KeyValue label="Payé" value={formatMoney(detail?.amount_paid ?? selected.amount_paid, detail?.currency)} />
            <KeyValue label="Reste dû" value={selected.sale_status === 'CANCELLED' ? '— (annulée)' : formatMoney(detail?.due ?? selected.due, detail?.currency)} strong />
            <KeyValue label="Statut" value={STATUT_LABELS[selected.statut] || selected.statut || 'EMISE'} />
            <KeyValue label="Mode" value={selected.payment_method} />
            {selected.notes ? <KeyValue label="Note" value={String(selected.notes)} /> : null}
            {!detailLoading && detail && !detail._detailError ? <DocumentActions html={invoiceHtml(detail)} fileName={`Facture-${selected.sale_number}`} /> : null}
            <EncaisserForm sale={selected} onDone={afterAction} />
            <AnnulerForm sale={selected} onDone={afterAction} />
          </View>
        ) : null}
      </Modal>

      {/* Confirmation animée : encaissement / annulation validé(e). */}
      <SuccessOverlay
        visible={!!validation}
        tone={validation?.tone || 'success'}
        title={validation?.title}
        message={validation?.message}
        onClose={() => setValidation(null)}
      />
    </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  content: { padding: sp(3), paddingBottom: sp(10), gap: sp(3) },
  sub: { fontSize: 13, color: colors.textMuted, marginTop: sp(1) },
  row: { flexDirection: 'row', alignItems: 'center', gap: sp(2), paddingVertical: sp(2.5), borderBottomWidth: 1, borderBottomColor: colors.border },
  grow: { flex: 1, minWidth: 0 },
  name: { fontSize: 15, fontWeight: '700', color: colors.text },
  meta: { fontSize: 12, color: colors.textMuted, marginTop: 2 },
  right: { alignItems: 'flex-end', gap: 4 },
  total: { fontSize: 14, fontWeight: '800', color: colors.primary },
  due: { fontSize: 11, fontWeight: '700', color: colors.warning },
  rowCancelled: { opacity: 0.55 },
  invoiceTitle: { fontSize: 18, fontWeight: '800', color: colors.text, marginBottom: sp(1) },
  itemRow: { flexDirection: 'row', justifyContent: 'space-between', gap: sp(2), paddingVertical: sp(1.5), borderBottomWidth: 1, borderBottomColor: colors.border },
  itemName: { flex: 1, fontSize: 12, color: colors.text },
  itemPrice: { fontSize: 12, fontWeight: '700', color: colors.primary },
});
