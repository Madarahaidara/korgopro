// ============================================================================
// Modale « nouveau mouvement » (mobile) — miroir web/src/components/MovementModal.jsx,
// enrichie du TRANSFERT entre comptes (miroir desktop TreasuryManager.transfer).
// Écritures via RPC app_treasury_move / app_treasury_transfer (garde
// manage_treasury serveur, soldes mis à jour dans la même transaction).
// ============================================================================
import { useState } from 'react';
import { createMovement, transfer } from '../api/treasuryApi';
import { useAuth } from '../context/AuthContext';
import { toNumber } from '../lib/format';
import { Banner, Btn, ChipGroup, Field, Input, Modal } from './ui';

// Catégories de mouvement de trésorerie (électricité, eau, internet, etc.).
// Aligné sur web/src/components/MovementModal.jsx (miroir treasury_view desktop).
const CATEGORIES = [
  'ELECTRICITE',
  'EAU',
  'INTERNET',
  'TRANSPORT',
  'MEUBLE',
  'MAINTENANCE',
  'DIVERS',
  'AUTRE',
];

const KIND_OPTIONS = [
  { value: 'IN', label: 'Entrée (+)' },
  { value: 'OUT', label: 'Sortie (−)' },
  { value: 'TRANSFER', label: 'Transfert' },
];

export default function MovementModal({ accounts, onSave, onClose }) {
  const { can } = useAuth();
  const [kind, setKind] = useState('IN');
  const [form, setForm] = useState({
    account_id: accounts[0]?.id ?? '',
    to_account_id: accounts[1]?.id ?? '',
    amount: '',
    reference: '',
    description: '',
    category: 'AUTRE',
  });
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState(null);

  const set = (key) => (value) => setForm({ ...form, [key]: value });

  if (!can('manage_treasury')) return null;

  const accountOptions = accounts.map((a) => ({ value: a.id, label: a.name }));

  const submit = async () => {
    const amount = toNumber(form.amount);
    if (amount <= 0) {
      setFeedback({ tone: 'danger', title: 'Montant invalide',
        message: 'Saisissez un montant supérieur à 0.' });
      return;
    }
    if (kind === 'TRANSFER') {
      if (form.account_id === '' || form.to_account_id === ''
          || Number(form.account_id) === Number(form.to_account_id)) {
        setFeedback({ tone: 'danger', title: 'Comptes invalides',
          message: 'Choisissez un compte source et un compte destination différents.' });
        return;
      }
    } else if (form.account_id === '') {
      setFeedback({ tone: 'danger', title: 'Compte requis',
        message: 'Sélectionnez le compte concerné par le mouvement.' });
      return;
    }
    setSaving(true);
    setFeedback(null);
    try {
      if (kind === 'TRANSFER') {
        await transfer({
          fromAccountId: form.account_id,
          toAccountId: form.to_account_id,
          amount,
          description: form.description,
        });
      } else {
        await createMovement({
          account_id: form.account_id,
          movement_type: kind,
          amount,
          reference: form.reference,
          description: form.description,
          category: form.category,
        });
      }
      if (onSave) onSave();
    } catch (e) {
      setFeedback({ tone: 'danger', title: 'Mouvement refusé', message: e.message });
      setSaving(false);
    }
  };

  return (
    <Modal visible title="Nouveau mouvement" onClose={onClose}>
      {feedback ? (
        <Banner tone={feedback.tone} title={feedback.title} message={feedback.message} />
      ) : null}

      <Field label="TYPE">
        <ChipGroup options={KIND_OPTIONS} value={kind} onChange={setKind} />
      </Field>

      <Field label={kind === 'TRANSFER' ? 'COMPTE SOURCE' : 'COMPTE'}>
        <ChipGroup
          options={accountOptions}
          value={form.account_id}
          onChange={set('account_id')}
        />
      </Field>

      {kind === 'TRANSFER' ? (
        <Field label="COMPTE DESTINATION">
          <ChipGroup
            options={accountOptions}
            value={form.to_account_id}
            onChange={set('to_account_id')}
          />
        </Field>
      ) : null}

      <Field label="MONTANT">
        <Input
          value={form.amount}
          onChangeText={set('amount')}
          keyboardType="numeric"
          placeholder="0"
        />
      </Field>

      {kind !== 'TRANSFER' ? (
        <>
          <Field label="RÉFÉRENCE (FACULTATIF)">
            <Input
              value={form.reference}
              onChangeText={set('reference')}
              placeholder="Reçu n°…"
            />
          </Field>
          <Field label="CATÉGORIE">
            <ChipGroup
              options={CATEGORIES.map((c) => ({ value: c, label: c }))}
              value={form.category}
              onChange={set('category')}
            />
          </Field>
        </>
      ) : null}

      <Field label="DESCRIPTION (FACULTATIF)">
        <Input
          value={form.description}
          onChangeText={set('description')}
          placeholder={kind === 'TRANSFER' ? 'Motif du transfert…' : 'Loyer, électricité…'}
        />
      </Field>

      <Btn
        title={saving ? 'Enregistrement…' : 'Enregistrer'}
        loading={saving}
        onPress={submit}
      />
      <Btn title="Annuler" variant="ghost" onPress={onClose} />
    </Modal>
  );
}
