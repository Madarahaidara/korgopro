// ============================================================================
// Modale « nouveau compte » (mobile) — miroir web/src/components/AccountModal.jsx.
// Écriture via RPC app_treasury_save_account (garde manage_treasury serveur) ;
// le solde courant n'est jamais modifiable ici (uniquement le solde initial,
// qui ne sert qu'à la création).
// ============================================================================
import { useState } from 'react';
import { saveAccount } from '../api/treasuryApi';
import { useAuth } from '../context/AuthContext';
import { toNumber } from '../lib/format';
import { Banner, Btn, ChipGroup, Field, Input, Modal } from './ui';

const TYPE_OPTIONS = [
  { value: 'CASH', label: 'Caisse' },
  { value: 'BANK', label: 'Banque' },
  { value: 'MOBILE_MONEY', label: 'Mobile Money' },
];

export default function AccountModal({ onSave, onClose }) {
  const { can } = useAuth();
  const [form, setForm] = useState({
    name: '',
    account_type: 'CASH',
    initial_balance: '0',
    bank_name: '',
    phone_number: '',
  });
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState(null);

  const set = (key) => (value) => setForm({ ...form, [key]: value });

  if (!can('manage_treasury')) return null;

  const submit = async () => {
    if (!String(form.name).trim()) {
      setFeedback({ tone: 'danger', title: 'Nom requis',
        message: 'Donnez un nom au compte (ex. « Caisse principale »).' });
      return;
    }
    if (toNumber(form.initial_balance) < 0) {
      setFeedback({ tone: 'danger', title: 'Solde invalide',
        message: 'Le solde initial ne peut pas être négatif.' });
      return;
    }
    setSaving(true);
    setFeedback(null);
    try {
      await saveAccount({
        name: String(form.name).trim(),
        account_type: form.account_type,
        initial_balance: toNumber(form.initial_balance),
        bank_name: form.bank_name,
        phone_number: form.phone_number,
      });
      if (onSave) onSave();
    } catch (e) {
      setFeedback({ tone: 'danger', title: 'Compte non enregistré', message: e.message });
      setSaving(false);
    }
  };

  return (
    <Modal visible title="Nouveau compte" onClose={onClose}>
      {feedback ? (
        <Banner tone={feedback.tone} title={feedback.title} message={feedback.message} />
      ) : null}

      <Field label="NOM DU COMPTE">
        <Input
          value={form.name}
          onChangeText={set('name')}
          placeholder="Caisse principale…"
        />
      </Field>

      <Field label="TYPE">
        <ChipGroup options={TYPE_OPTIONS} value={form.account_type} onChange={set('account_type')} />
      </Field>

      <Field label="SOLDE INITIAL" hint="Ne sert qu'à la création : le solde évolue ensuite uniquement par les mouvements.">
        <Input
          value={String(form.initial_balance)}
          onChangeText={set('initial_balance')}
          keyboardType="numeric"
          placeholder="0"
        />
      </Field>

      {form.account_type === 'BANK' ? (
        <Field label="BANQUE (FACULTATIF)">
          <Input value={form.bank_name} onChangeText={set('bank_name')} placeholder="Nom de la banque…" />
        </Field>
      ) : null}

      {form.account_type === 'MOBILE_MONEY' ? (
        <Field label="NUMÉRO (FACULTATIF)">
          <Input value={form.phone_number} onChangeText={set('phone_number')} placeholder="+223 …" />
        </Field>
      ) : null}

      <Btn
        title={saving ? 'Enregistrement…' : 'Créer le compte'}
        loading={saving}
        onPress={submit}
      />
      <Btn title="Annuler" variant="ghost" onPress={onClose} />
    </Modal>
  );
}
