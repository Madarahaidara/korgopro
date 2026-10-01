import { useCallback, useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { listSalesOpen, registerPayment } from '../api/salesApi';
import {
  Badge,
  Banner,
  Btn,
  Card,
  ChipGroup,
  Empty,
  Field,
  Input,
  KeyValue,
  Loading,
  SectionTitle,
} from '../components/ui';
import { PulseOnChange, SuccessOverlay } from '../components/Feedback';
import { config } from '../config';
import { useAuth } from '../context/AuthContext';
import { useStores } from '../context/StoreContext';
import { formatDate, formatMoney, toNumber } from '../lib/format';
import { colors, radius, sp } from '../theme';

const PAYMENT_METHODS = [
  { value: 'CASH', label: 'Espèces' },
  { value: 'MOBILE_MONEY', label: 'Mobile Money' },
  { value: 'CARD', label: 'Carte' },
];

/**
 * Écran Encaissement — solde des factures clients.
 *
 * Équivalent mobile de core/invoice_register_manager.py -> receive_payment :
 * le montant ne peut pas dépasser le reste dû, la trésorerie est créditée et
 * le statut de la facture est recalculé (PAYEE / PARTIELLEMENT_PAYEE).
 */
export default function PaiementsScreen() {
  const { can } = useAuth();
  const { activeId, activeStore } = useStores();
  const canCollect = can('create_sales') || can('manage_treasury');

  const [sales, setSales] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [amount, setAmount] = useState('');
  const [method, setMethod] = useState('CASH');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [validation, setValidation] = useState(null);

  const currency = config.currency;

  const load = useCallback(async () => {
    if (!canCollect || activeId == null) return;
    setLoading(true);
    try {
      const rows = await listSalesOpen({ storeId: activeId, limit: 100 });
      setSales(rows);
    } catch (e) {
      setFeedback({ tone: 'danger', title: 'Chargement impossible', message: e.message });
    } finally {
      setLoading(false);
    }
  }, [activeId, canCollect]);

  useEffect(() => {
    load();
  }, [load]);

  const totalDue = sales.reduce((sum, s) => sum + s.due, 0);

  const pick = (sale) => {
    setSelected(sale);
    setAmount(String(Math.round(sale.due)));
    setNotes('');
    setFeedback(null);
  };

  const submit = async () => {
    if (!selected) return;
    const value = toNumber(amount);
    if (value <= 0) {
      setFeedback({ tone: 'danger', title: 'Montant invalide', message: 'Saisissez un montant supérieur à 0.' });
      return;
    }
    if (value > selected.due + 0.001) {
      setFeedback({
        tone: 'danger',
        title: 'Montant trop élevé',
        message: `Le reste dû sur ${selected.sale_number} est de ${formatMoney(selected.due, currency)}.`,
      });
      return;
    }

    setSaving(true);
    setFeedback(null);
    try {
      const result = await registerPayment({
        saleId: selected.id,
        amount: value,
        paymentMethod: method,
        notes,
      });
      const summary = {
        tone: 'success',
        title: `Encaissement enregistré (${selected.sale_number})`,
        message:
          result.due > 0
            ? `Reste dû : ${formatMoney(result.due, currency)}`
            : 'Facture entièrement réglée.',
      };
      setFeedback(summary);
      // Confirmation animée (coche + carte qui « pop »).
      setValidation(summary);
      setSelected(null);
      setAmount('');
      setNotes('');
      await load();
    } catch (e) {
      setFeedback({ tone: 'danger', title: 'Encaissement refusé', message: e.message });
    } finally {
      setSaving(false);
    }
  };

  if (!canCollect) {
    return (
      <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
        <Banner
          tone="warning"
          title="Accès refusé"
          message="Votre rôle ne permet pas d'encaisser des paiements."
        />
      </ScrollView>
    );
  }

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
    >
      <Card>
        <SectionTitle right={<Badge text={activeStore?.name || 'Magasin —'} tone="info" />}>
          Reste à encaisser
        </SectionTitle>
        <View style={styles.summary}>
          <PulseOnChange value={totalDue}>
            <Text style={styles.summaryValue}>{formatMoney(totalDue, currency)}</Text>
          </PulseOnChange>
          <Text style={styles.summaryLabel}>
            {sales.length} facture(s) en attente de règlement
          </Text>
        </View>
        <Btn variant="ghost" title="Rafraîchir" onPress={load} loading={loading} />
      </Card>

      {feedback ? (
        <Banner tone={feedback.tone} title={feedback.title} message={feedback.message} />
      ) : null}

      {selected ? (
        <Card>
          <SectionTitle
            right={
              <Btn
                variant="ghost"
                title="Annuler"
                onPress={() => setSelected(null)}
                style={styles.smallBtn}
              />
            }
          >
            Encaisser {selected.sale_number}
          </SectionTitle>
          <KeyValue label="Client" value={selected.customer_name} />
          <KeyValue label="Total facture" value={formatMoney(selected.total_amount, currency)} />
          <KeyValue label="Déjà payé" value={formatMoney(selected.amount_paid, currency)} />
          <KeyValue label="Reste dû" value={formatMoney(selected.due, currency)} strong />

          <Field label="MONTANT REÇU">
            <Input value={amount} onChangeText={setAmount} keyboardType="numeric" />
          </Field>
          <Field label="MOYEN DE PAIEMENT">
            <ChipGroup options={PAYMENT_METHODS} value={method} onChange={setMethod} />
          </Field>
          <Field label="NOTE (FACULTATIF)">
            <Input value={notes} onChangeText={setNotes} placeholder="Reçu n°…" />
          </Field>

          <Btn
            title={`Encaisser ${amount ? formatMoney(toNumber(amount), currency) : ''}`}
            variant="success"
            onPress={submit}
            loading={saving}
            style={styles.fullBtn}
          />
        </Card>
      ) : null}

      <Card>
        <SectionTitle>Factures à encaisser</SectionTitle>
        {loading && sales.length === 0 ? <Loading label="Chargement des factures…" /> : null}
        {!loading && sales.length === 0 ? (
          <Empty
            title="Aucun reste dû"
            hint="Aucune facture à crédit ou partiellement payée pour ce magasin."
          />
        ) : null}
        {sales.map((s) => (
          <Pressable
            key={s.id}
            style={[styles.row, selected?.id === s.id ? styles.rowActive : null]}
            onPress={() => pick(s)}
          >
            <View style={styles.grow}>
              <Text style={styles.rowTitle} numberOfLines={1}>
                {s.sale_number}
              </Text>
              <Text style={styles.rowMeta}>
                {formatDate(s.sale_date)} · {s.customer_name}
              </Text>
              <Text style={styles.rowMeta}>
                Payé {formatMoney(s.amount_paid, currency)} / {formatMoney(s.total_amount, currency)}
              </Text>
            </View>
            <View style={styles.rowRight}>
              <Text style={styles.rowDue}>{formatMoney(s.due, currency)}</Text>
              <Badge
                text={s.payment_status === 'PARTIAL' ? 'Partiel' : 'Impayé'}
                tone={s.payment_status === 'PARTIAL' ? 'warning' : 'danger'}
              />
            </View>
          </Pressable>
        ))}
      </Card>

      {/* Confirmation animée : coche + carte qui « pop » après validation. */}
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
  content: { padding: sp(3), paddingBottom: sp(10) },
  summary: { alignItems: 'center', marginBottom: sp(3) },
  summaryValue: { fontSize: 26, fontWeight: '800', color: colors.primary },
  summaryLabel: { fontSize: 12, color: colors.textMuted, marginTop: sp(1) },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: sp(2),
    paddingVertical: sp(2.5),
    paddingHorizontal: sp(2),
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  rowActive: { backgroundColor: colors.primarySoft, borderRadius: radius.md },
  rowTitle: { fontSize: 15, fontWeight: '700', color: colors.text },
  rowMeta: { fontSize: 12, color: colors.textMuted, marginTop: sp(0.5) },
  rowRight: { alignItems: 'flex-end', gap: sp(1) },
  rowDue: { fontSize: 15, fontWeight: '800', color: colors.danger },
  grow: { flex: 1, minWidth: 0 },
  smallBtn: { minHeight: 36, paddingHorizontal: sp(3) },
  fullBtn: { width: '100%', marginTop: sp(2) },
});
