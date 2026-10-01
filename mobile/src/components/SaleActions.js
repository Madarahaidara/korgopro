// ============================================================================
// Actions sur une facture (mobile) : encaisser un solde de crédit / partiel,
// ou annuler la vente. Partagé par pages/Sales.js et pages/Invoices.js :
//
//   * encaissement -> RPC app_register_payment (montant <= reste dû,
//     trésorerie créditée, statut PAYEE / PARTIELLEMENT_PAYEE) ;
//   * annulation   -> RPC app_cancel_sale (stock remis, dette effacée,
//     encaissements compensés, facture ANNULEE / CANCELLED), réservée aux
//     rôles `cancel_sales` — la garde est rappelée ici et appliquée en base.
// ============================================================================
import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { cancelSale, registerPayment } from '../api/salesApi';
import { config } from '../config';
import { useAuth } from '../context/AuthContext';
import { formatMoney, toNumber } from '../lib/format';
import { Banner, Btn, ChipGroup, Field, Input } from './ui';
import { colors, sp } from '../theme';

const METHODS = [
  { value: 'CASH', label: 'Espèces' },
  { value: 'MOBILE_MONEY', label: 'Mobile Money' },
  { value: 'CARD', label: 'Carte' },
];

/** Encaissement du reste dû (crédit ou paiement partiel). */
export function EncaisserForm({ sale, onDone }) {
  const { can } = useAuth();
  const currency = sale.currency || config.currency;
  const [method, setMethod] = useState('CASH');
  const [amount, setAmount] = useState(String(Math.round(sale.due)));
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState(null);

  if (!(can('create_sales') || can('manage_treasury'))) return null;
  if (sale.sale_status === 'CANCELLED' || !(sale.due > 0.001)) return null;

  const submit = async () => {
    const value = toNumber(amount);
    if (value <= 0) {
      setFeedback({ tone: 'danger', title: 'Montant invalide',
        message: 'Saisissez un montant supérieur à 0.' });
      return;
    }
    if (value > sale.due + 0.001) {
      setFeedback({ tone: 'danger', title: 'Montant trop élevé',
        message: `Le reste dû sur ${sale.sale_number} est de ${formatMoney(sale.due, currency)}.` });
      return;
    }
    setSaving(true);
    setFeedback(null);
    try {
      const result = await registerPayment({
        saleId: sale.id, amount: value, paymentMethod: method, notes,
      });
      const summary = {
        tone: 'success',
        title: `Encaissement enregistré — ${sale.sale_number}`,
        message: result.due > 0
          ? `Reste dû : ${formatMoney(result.due, currency)}`
          : 'Facture entièrement réglée.',
      };
      setFeedback(summary);
      setNotes('');
      if (onDone) onDone({ action: 'PAYMENT', sale, summary });
    } catch (e) {
      setFeedback({ tone: 'danger', title: 'Encaissement refusé', message: e.message });
    } finally {
      setSaving(false);
    }
  };

  return (
    <View style={styles.block}>
      <Text style={styles.title}>Encaisser — reste dû {formatMoney(sale.due, currency)}</Text>
      {feedback ? (
        <Banner tone={feedback.tone} title={feedback.title} message={feedback.message} />
      ) : null}
      <Field label="MONTANT ENCAISSÉ">
        <Input
          value={amount}
          onChangeText={setAmount}
          keyboardType="numeric"
          placeholder={String(Math.round(sale.due))}
        />
      </Field>
      <Field label="MOYEN DE PAIEMENT">
        <ChipGroup options={METHODS} value={method} onChange={setMethod} />
      </Field>
      <Field label="RÉFÉRENCE / NOTE (FACULTATIF)">
        <Input value={notes} onChangeText={setNotes} placeholder="N° de transaction…" />
      </Field>
      <Btn
        title={saving ? 'Encaissement…' : `Encaisser ${formatMoney(toNumber(amount), currency)}`}
        loading={saving}
        onPress={submit}
      />
    </View>
  );
}

/** Annulation de la vente (motif obligatoire, confirmation en 2 temps). */
export function AnnulerForm({ sale, onDone }) {
  const { can } = useAuth();
  const [reason, setReason] = useState('');
  const [armed, setArmed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState(null);

  if (!can('cancel_sales')) return null;
  if (sale.sale_status === 'CANCELLED') return null;

  const submit = async () => {
    if (!armed) {
      if (reason.trim().length < 3) {
        setFeedback({ tone: 'danger', title: 'Motif obligatoire',
          message: 'Précisez le motif d’annulation (3 caractères minimum).' });
        return;
      }
      setArmed(true);
      setFeedback({ tone: 'info', title: 'Confirmez l’annulation',
        message: 'Stock remis, dette effacée, caisse remboursée — appuyez de nouveau pour valider.' });
      return;
    }
    setSaving(true);
    setFeedback(null);
    try {
      const result = await cancelSale(sale.id, reason.trim());
      const summary = {
        tone: 'success',
        title: `Vente ${sale.sale_number} annulée`,
        message: result.message,
      };
      setFeedback(summary);
      setArmed(false);
      if (onDone) onDone({ action: 'CANCEL', sale, summary });
    } catch (e) {
      setFeedback({ tone: 'danger', title: 'Annulation refusée', message: e.message });
      setArmed(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <View style={styles.block}>
      <Text style={styles.title}>Annuler la vente</Text>
      {feedback ? (
        <Banner tone={feedback.tone} title={feedback.title} message={feedback.message} />
      ) : null}
      <Field label="MOTIF D’ANNULATION">
        <Input
          value={reason}
          onChangeText={setReason}
          placeholder="Erreur de caisse, article défectueux…"
        />
      </Field>
      <Btn
        title={saving ? 'Annulation…' : armed ? 'Confirmer l’annulation' : 'Annuler la vente'}
        variant="danger"
        loading={saving}
        onPress={submit}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  block: {
    marginTop: sp(3),
    paddingTop: sp(3),
    borderTopWidth: 1,
    borderTopColor: colors.border,
    gap: sp(1.5),
  },
  title: { fontSize: 13, fontWeight: '800', color: colors.text },
});
