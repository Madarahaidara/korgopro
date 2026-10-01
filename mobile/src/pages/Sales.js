// ============================================================================
// Ventes (mobile) — miroir de web/src/pages/Sales.jsx.
// Liste filtrable + détail (lignes, totaux). Création via l'onglet Caisse.
// ============================================================================
import { useCallback, useEffect, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { listSales } from '../api/salesApi';
import { useStores } from '../context/StoreContext';
import { formatDate, formatMoney } from '../lib/format';
import { colors, sp } from '../theme';
import { Badge, Banner, Card, Empty, Field, Input, KeyValue, Loading, Modal, SectionTitle } from '../components/ui';
import { SuccessOverlay } from '../components/Feedback';
import { AnnulerForm, EncaisserForm } from '../components/SaleActions';

/** Délai avant la confirmation animée : laisse la modale de détail se fermer. */
const OVERLAY_DELAY = 350;

/**
 * Badge de la liste : l'annulation prime sur l'état de paiement (une facture
 * annulée n'est plus à encaisser ni à payer).
 */
function statusBits(s) {
  if (s.sale_status === 'CANCELLED') return { text: 'Annulée', tone: 'danger' };
  if (s.payment_status === 'PAID') return { text: 'Payée', tone: 'success' };
  if (s.payment_status === 'PARTIAL') return { text: 'Partielle', tone: 'warning' };
  return { text: 'Impayée', tone: 'danger' };
}

export default function SalesScreen() {
  const { activeId } = useStores();
  const [sales, setSales] = useState([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);
  const [validation, setValidation] = useState(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setSales(await listSales({ storeId: activeId, limit: 80 }));
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

  /**
   * Après un encaissement / une annulation : refermer le détail, recharger la
   * liste puis afficher la confirmation animée (le léger différé laisse la
   * modale de détail terminer son fondu de fermeture).
   */
  const afterAction = ({ summary } = {}) => {
    setSelected(null);
    load();
    if (summary) setTimeout(() => setValidation(summary), OVERLAY_DELAY);
  };

  const q = query.trim().toLowerCase();
  const searched = sales.filter((s) => {
    if (!q) return true;
    return (
      String(s.sale_number || '').toLowerCase().includes(q) ||
      String(s.customer_name || '').toLowerCase().includes(q)
    );
  });

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
    >
      <Card>
        <SectionTitle>Ventes</SectionTitle>
        <Text style={styles.sub}>Enregistrez vos factures et suivez les paiements.</Text>
        <Field label="RECHERCHE">
          <Input value={query} onChangeText={setQuery} placeholder="N° facture, client…" />
        </Field>
      </Card>

      {loading ? <Loading label="Chargement des ventes…" /> : null}
      {error ? <Banner tone="danger" title="Chargement impossible" message={error} /> : null}
      {!loading && searched.length === 0 ? (
        <Empty title="Aucune vente" hint="Créez une vente depuis l'onglet Caisse." />
      ) : null}

      <Card>
        {searched.map((s) => {
          const bits = statusBits(s);
          const cancelled = s.sale_status === 'CANCELLED';
          return (
            <Pressable
              key={s.id}
              style={[styles.row, cancelled ? styles.rowCancelled : null]}
              onPress={() => setSelected(s)}
            >
              <View style={styles.grow}>
                <Text style={styles.rowTitle} numberOfLines={1}>{s.sale_number}</Text>
                <Text style={styles.rowMeta}>{formatDate(s.sale_date)} · {s.customer_name}</Text>
              </View>
              <View style={styles.right}>
                <Text style={styles.total}>{formatMoney(s.total_amount)}</Text>
                <Badge text={bits.text} tone={bits.tone} />
                {!cancelled && s.due > 0.001 ? (
                  <Text style={styles.due}>Reste {formatMoney(s.due)}</Text>
                ) : null}
              </View>
            </Pressable>
          );
        })}
      </Card>

      <Modal visible={!!selected} title={selected ? `Vente ${selected.sale_number}` : ''} onClose={() => setSelected(null)}>
        {selected ? (
          <View>
            <KeyValue label="Client" value={selected.customer_name} />
            <KeyValue label="Date" value={formatDate(selected.sale_date)} />
            <KeyValue label="Paiement" value={selected.payment_method} />
            <KeyValue label="Statut" value={statusBits(selected).text} />
            <KeyValue label="Total" value={formatMoney(selected.total_amount)} strong />
            <KeyValue label="Payé" value={formatMoney(selected.amount_paid)} />
            <KeyValue label="Reste dû" value={selected.sale_status === 'CANCELLED' ? '— (annulée)' : formatMoney(selected.due)} strong />
            {selected.notes ? <KeyValue label="Note" value={String(selected.notes)} /> : null}
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
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  content: { padding: sp(3), paddingBottom: sp(10), gap: sp(3) },
  sub: { fontSize: 13, color: colors.textMuted, marginTop: sp(1), marginBottom: sp(2) },
  row: { flexDirection: 'row', alignItems: 'center', gap: sp(2), paddingVertical: sp(2.5), borderBottomWidth: 1, borderBottomColor: colors.border },
  grow: { flex: 1, minWidth: 0 },
  rowTitle: { fontSize: 15, fontWeight: '700', color: colors.text },
  rowMeta: { fontSize: 12, color: colors.textMuted, marginTop: 2 },
  right: { alignItems: 'flex-end', gap: 4 },
  total: { fontSize: 14, fontWeight: '800', color: colors.primary },
  due: { fontSize: 11, fontWeight: '700', color: colors.warning || '#b45309' },
  rowCancelled: { opacity: 0.55 },
});
