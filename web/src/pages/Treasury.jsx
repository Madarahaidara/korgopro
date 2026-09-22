import { useState } from 'react';
import {
  listAccounts, listMovements, treasurySummary,
  listClosures, monthPeriod, periodLabel, computeMonthlyPreview, closeMonth,
} from '../api/treasuryApi';
import { formatMoney, formatDate } from '../api/db';
import { Badge, Stat } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import AccountModal from '../components/AccountModal';
import MovementModal from '../components/MovementModal';
import Icon from '../components/Icon';

const TYPE_LABELS = { CASH: 'Caisse', BANK: 'Banque', MOBILE_MONEY: 'Mobile Money' };

export default function Treasury() {
  const { user, isAdmin } = useAuth();
  const [accounts, setAccounts] = useState(() => listAccounts());
  const [movements, setMovements] = useState(() => listMovements());
  const [showAccount, setShowAccount] = useState(false);
  const [showMovement, setShowMovement] = useState(false);

  const summary = treasurySummary();
  const currency = accounts[0]?.currency || 'FCFA';
  const currentPeriod = monthPeriod();
  const currentClosure = listClosures().find((c) => c.period === currentPeriod);
  const preview = currentClosure || computeMonthlyPreview(currentPeriod);
  const closed = currentClosure?.status === 'CLOSED';

  const refresh = () => { setAccounts(listAccounts()); setMovements(listMovements()); };

  const onCloseMonth = () => {
    if (!window.confirm(
      `Clôturer ${periodLabel(currentPeriod)} ?\n\n` +
      `Les totaux du mois seront figés : ${preview.sales_count} vente(s), ` +
      `encaissé ${formatMoney(preview.total_collected, currency)}.\nCette action est enregistrée dans la base.`
    )) return;
    try {
      closeMonth(currentPeriod, user);
      refresh();
    } catch (e) {
      window.alert(e.message);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-title">Trésorerie</div>
          <div className="page-subtitle">Suivez vos comptes, entrées et sorties d'argent.</div>
        </div>
        <div className="flex">
          <button className="btn" onClick={() => setShowAccount(true)}>+ Compte</button>
          <button className="btn btn-primary" onClick={() => setShowMovement(true)}>+ Mouvement</button>
        </div>
      </div>

      <div className="grid grid-4">
        <Stat icon={<Icon name="treasury" size={22} />} label="Solde total" value={formatMoney(summary.total, currency)} color="#2f6fed" />
        <Stat icon={<Icon name="cash" size={22} />} label="Caisse" value={formatMoney(summary.byType.CASH || 0, currency)} color="#1a9e5e" />
        <Stat icon={<Icon name="treasury" size={22} />} label="Banque" value={formatMoney(summary.byType.BANK || 0, currency)} color="#e5a50a" />
        <Stat icon={<Icon name="phone" size={22} />} label="Mobile Money" value={formatMoney(summary.byType.MOBILE_MONEY || 0, currency)} color="#0ea5c9" />
      </div>

      <div className="grid grid-3 mt-16">
        {accounts.map((a) => (
          <div className="card" key={a.id}>
            <div className="justify-between">
              <div>
                <div className="card-title" style={{ marginBottom: 2 }}>{a.name}</div>
                <div className="text-muted" style={{ fontSize: 12 }}>{TYPE_LABELS[a.account_type] || a.account_type}</div>
              </div>
              {a.is_default && <Badge status="DEFAUT" />}
            </div>
            <div className="mt-8" style={{ fontSize: 20, fontWeight: 800 }}>{formatMoney(a.balance, a.currency)}</div>
            <div className="text-muted" style={{ fontSize: 12 }}>
              {a.account_type === 'BANK' && a.bank_name}
              {a.account_type === 'MOBILE_MONEY' && a.phone_number}
            </div>
          </div>
        ))}
        {accounts.length === 0 && <div className="card empty">Aucun compte. Créez-en un.</div>}
      </div>

      {/* ------------------------------------------------------------------
          Clôture mensuelle des ventes : aperçu du mois courant + historique.
          ------------------------------------------------------------------ */}
      <div className="card mt-16">
        <div className="justify-between" style={{ marginBottom: 12 }}>
          <div>
            <div className="card-title">Clôture mensuelle — {periodLabel(currentPeriod)}</div>
            <div className="text-muted" style={{ fontSize: 12 }}>
              {closed
                ? `Mois clôturé${currentClosure.closed_at ? ` le ${formatDate(currentClosure.closed_at)}` : ''}. Les totaux ci-dessous sont figés.`
                : "Ventes du mois en cours. Clôturez en fin de mois pour figer les totaux."}
            </div>
          </div>
          <button
            className="btn btn-primary"
            onClick={onCloseMonth}
            disabled={closed || !isAdmin()}
            title={!isAdmin() ? 'Réservé aux administrateurs' : undefined}
          >
            {closed ? 'Mois clôturé' : 'Clôturer le mois'}
          </button>
        </div>
        <div className="grid grid-4" style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}>
          <Stat icon={<Icon name="sale" size={22} />} label="Ventes" value={`${preview.sales_count} · ${formatMoney(preview.total_sales, currency)}`} color="#2f6fed" />
          <Stat icon={<Icon name="cash" size={22} />} label="Encaissé" value={formatMoney(preview.total_collected, currency)} color="#1a9e5e" />
          <Stat icon={<Icon name="clock" size={22} />} label="Crédit (reste dû)" value={formatMoney(preview.total_credit, currency)} color="#e5a50a" />
          <Stat icon={<Icon name="wallet" size={22} />} label="Dépenses" value={formatMoney(preview.total_out, currency)} color="#ef4444" />
          <Stat icon={<Icon name="treasury" size={22} />} label="Net" value={formatMoney(preview.net, currency)} color="#8b5cf6" />
        </div>
      </div>

      <div className="card mt-16" style={{ padding: 0, overflowX: 'auto', overflowY: 'hidden' }}>
        <div className="card-title" style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', marginBottom: 0 }}>Historique des clôtures</div>
        <table className="table">
          <thead>
            <tr>
              <th>Période</th>
              <th className="text-right">Ventes</th>
              <th className="text-right">Encaissé</th>
              <th className="text-right">Crédit</th>
              <th className="text-right">Dépenses</th>
              <th className="text-right">Net</th>
              <th>Statut</th>
              <th>Clôturé le</th>
            </tr>
          </thead>
          <tbody>
            {listClosures().map((c) => (
              <tr key={c.id}>
                <td><b>{periodLabel(c.period)}</b></td>
                <td className="text-right">{c.sales_count} · {formatMoney(c.total_sales, currency)}</td>
                <td className="text-right">{formatMoney(c.total_collected, currency)}</td>
                <td className="text-right">{formatMoney(c.total_credit, currency)}</td>
                <td className="text-right">{formatMoney(c.total_out, currency)}</td>
                <td className="text-right"><b style={{ color: c.net >= 0 ? 'var(--success)' : 'var(--danger)' }}>{formatMoney(c.net, currency)}</b></td>
                <td><Badge status={c.status === 'CLOSED' ? 'PAID' : 'PENDING'} /></td>
                <td className="text-muted">{c.closed_at ? formatDate(c.closed_at) : '—'}</td>
              </tr>
            ))}
            {listClosures().length === 0 && (
              <tr><td colSpan={8}><div className="empty">Aucune clôture. Clôturez le mois en cours en fin de période.</div></td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card mt-16" style={{ padding: 0, overflowX: 'auto', overflowY: 'hidden' }}>
        <div className="card-title" style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', marginBottom: 0 }}>Mouvements récents</div>
        <table className="table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Type</th>
              <th>Compte</th>
              <th>Référence</th>
              <th>Description</th>
              <th>Catégorie</th>
              <th className="text-right">Montant</th>
            </tr>
          </thead>
          <tbody>
            {movements.map((m) => (
              <tr key={m.id}>
                <td>{formatDate(m.date)}</td>
                <td>{m.movement_type === 'IN' ? <Badge status="PAID" /> : <Badge status="SORTIE" />}</td>
                <td>{m.accountName}</td>
                <td className="text-muted">{m.reference || '—'}</td>
                <td>{m.description || '—'}</td>
                <td>{m.category || '—'}</td>
                <td className="text-right">
                  <b style={{ color: m.movement_type === 'IN' ? 'var(--success)' : 'var(--danger)' }}>
                    {m.movement_type === 'IN' ? '+' : '-'}{formatMoney(m.amount, currency)}
                  </b>
                </td>
              </tr>
            ))}
            {movements.length === 0 && <tr><td colSpan={7}><div className="empty">Aucun mouvement.</div></td></tr>}
          </tbody>
        </table>
      </div>

      {showAccount && (
        <AccountModal
          onSave={() => { refresh(); setShowAccount(false); }}
          onClose={() => setShowAccount(false)}
        />
      )}
      {showMovement && (
        <MovementModal
          accounts={accounts}
          onSave={() => { refresh(); setShowMovement(false); }}
          onClose={() => setShowMovement(false)}
        />
      )}
    </div>
  );
}

export { TYPE_LABELS };