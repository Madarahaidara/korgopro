import { useCallback, useMemo, useState } from 'react';
import {
  closeTreasuryMonth, createTreasuryAccount, createTreasuryMovement, listAccounts,
  listOpenCashSession, listTreasuryMonthClosures, listTreasuryMovements,
  loadMonthlyTreasuryPreview, updateCashSession,
} from '../api/businessApi';
import { useBusinessData } from '../api/useBusinessData';
import {
  ActionButton, DataTable, Field, InlineMessage, MetricCard, Modal, PageHeader, Panel, StatusBadge, Tabs,
} from '../components/erp';
import { formatMoney } from '../data/demoData';
import { useAuth } from '../context/AuthContext';
import { downloadCsv } from '../utils/downloadCsv';

const treasuryTabs = ['Vue d’ensemble', 'Comptes', 'Mouvements', 'Session de caisse'];
const movementCategories = ['ELECTRICITE', 'EAU', 'INTERNET', 'TRANSPORT', 'MEUBLE', 'MAINTENANCE', 'DIVERS', 'AUTRE'];

function currentMonthPeriod() {
  const now = new Date();
  return String(now.getFullYear()) + '-' + String(now.getMonth() + 1).padStart(2, '0');
}

export default function TreasuryView() {
  const { organizationId, user, settings, selectedOrganization } = useAuth();
  const currentPeriod = currentMonthPeriod();
  const load = useCallback(async () => {
    const [accounts, movements, session, monthlyPreview, closures] = await Promise.all([
      listAccounts(organizationId),
      listTreasuryMovements(organizationId, null),
      listOpenCashSession(organizationId, user?.id),
      loadMonthlyTreasuryPreview(organizationId, currentPeriod),
      listTreasuryMonthClosures(organizationId),
    ]);
    return { accounts, movements, session, monthlyPreview, closures };
  }, [currentPeriod, organizationId, user?.id]);
  const { data, loading, error: loadError, refresh } = useBusinessData(load);
  const [tab, setTab] = useState(treasuryTabs[0]);
  const [showAccount, setShowAccount] = useState(false);
  const [showMovement, setShowMovement] = useState(false);
  const [showSession, setShowSession] = useState(false);
  const [showMonthClose, setShowMonthClose] = useState(false);
  const [monthCloseNotes, setMonthCloseNotes] = useState('');
  const [monthCloseError, setMonthCloseError] = useState('');
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);
  const [accountError, setAccountError] = useState('');
  const [accountDraft, setAccountDraft] = useState({
    name: '', accountType: 'CASH', initialBalance: '0',
    bankName: '', accountNumber: '', phoneNumber: '', isDefault: false,
  });
  const [draft, setDraft] = useState({ label: '', accountId: '', type: 'IN', amount: '', reference: '', category: 'AUTRE' });
  const [sessionDraft, setSessionDraft] = useState({ accountId: '', amount: '0', notes: '' });

  const accounts = data?.accounts || [];
  const movements = data?.movements || [];
  const closures = data?.closures || [];
  const currentClosure = closures.find((closure) => closure.period === currentPeriod);
  const monthlySummary = currentClosure?.status === 'CLOSED' ? currentClosure : data?.monthlyPreview;
  const session = data?.session || null;
  const balance = accounts.reduce((sum, account) => sum + account.balance, 0);
  const totalIn = movements.filter((item) => item.type === 'Entrée').reduce((sum, item) => sum + item.amount, 0);
  const totalOut = movements.filter((item) => item.type === 'Sortie').reduce((sum, item) => sum + item.amount, 0);
  const canManageTreasury = (selectedOrganization?.permissions || []).includes('manage_treasury');
  const canCreateSales = (selectedOrganization?.permissions || []).includes('create_sales');
  const canOperateSession = canManageTreasury || canCreateSales;
  const canExport = (selectedOrganization?.permissions || []).includes('export_data');
  const cashAccounts = useMemo(() => accounts.filter((account) => account.account_type === 'CASH'), [accounts]);
  const saveMonthClosure = async (event) => {
    event.preventDefault();
    setSaving(true);
    setMonthCloseError('');
    try {
      const result = await closeTreasuryMonth(organizationId, currentPeriod, monthCloseNotes);
      setShowMonthClose(false);
      setMonthCloseNotes('');
      setNotice(result.message || 'Mois clôturé et totaux enregistrés.');
      await refresh().catch(() => {});
    } catch (failure) {
      setMonthCloseError(failure.message || 'La clôture mensuelle a échoué.');
    } finally {
      setSaving(false);
    }
  };
  const saveAccount = async (event) => {
    event.preventDefault();
    const initialBalance = Number(accountDraft.initialBalance);
    if (!accountDraft.name.trim() || !Number.isFinite(initialBalance) || initialBalance < 0) {
      setAccountError('Indiquez un nom de compte et un solde initial positif ou nul.');
      return;
    }
    setSaving(true);
    setAccountError('');
    setNotice('');
    try {
      const result = await createTreasuryAccount({ organizationId, ...accountDraft, initialBalance });
      setShowAccount(false);
      setAccountDraft({ name: '', accountType: 'CASH', initialBalance: '0', bankName: '', accountNumber: '', phoneNumber: '', isDefault: false });
      setNotice(result.message || 'Compte de trésorerie enregistré.');
      await refresh().catch(() => {});
    } catch (failure) {
      setAccountError(failure.message || 'Le compte n’a pas pu être créé.');
    } finally {
      setSaving(false);
    }
  };
  const exportTreasuryTab = () => {
    const organizationCode = selectedOrganization?.code || 'entreprise';
    if (tab === 'Mouvements') {
      downloadCsv(`tresorerie-mouvements-${organizationCode}`, ['Date', 'Libellé', 'Compte', 'Type', 'Montant', 'Référence', 'Catégorie'],
        movements.map((movement) => [movement.date, movement.label, movement.account, movement.type, movement.amount, movement.reference, movement.category]));
    } else if (tab === 'Comptes' || tab === 'Vue d’ensemble') {
      downloadCsv(`tresorerie-comptes-${organizationCode}`, ['Compte', 'Type', 'Devise', 'Solde initial', 'Solde courant', 'Statut'],
        accounts.map((account) => [account.name, account.type, account.currency, account.initial_balance, account.balance, account.status]));
    }
  };

  const openMovementForm = () => {
    setNotice('');
    setDraft({
      label: '',
      accountId: String(accounts.find((account) => account.is_default)?.id || accounts[0]?.id || ''),
      type: 'IN',
      amount: '',
      reference: '',
      category: 'AUTRE',
    });
    setShowMovement(true);
  };

  const saveMovement = async (event) => {
    event.preventDefault();
    const amount = Number(draft.amount);
    if (!draft.label.trim() || amount <= 0) {
      setNotice('Indiquez un libellé et un montant positif.');
      return;
    }
    setSaving(true);
    setNotice('');
    try {
      const result = await createTreasuryMovement({
        organizationId,
        accountId: Number(draft.accountId),
        movementType: draft.type,
        amount,
        reference: draft.reference,
        description: draft.label,
        category: draft.category,
      });
      setShowMovement(false);
      setDraft({ label: '', accountId: '', type: 'IN', amount: '', reference: '', category: 'AUTRE' });
      setNotice(result.message || 'Mouvement de trésorerie enregistré.');
      await refresh().catch(() => {});
    } catch (failure) {
      setNotice(failure.message || 'Le mouvement n’a pas pu être enregistré.');
    } finally {
      setSaving(false);
    }
  };

  const saveSessionAction = async (event) => {
    event.preventDefault();
    const opening = !session;
    setSaving(true);
    setNotice('');
    try {
      const result = await updateCashSession({
        organizationId,
        action: opening ? 'open' : 'close',
        accountId: opening ? Number(sessionDraft.accountId) : null,
        sessionId: session?.id,
        amount: Number(sessionDraft.amount),
        notes: sessionDraft.notes,
      });
      setShowSession(false);
      setSessionDraft({ accountId: '', amount: '0', notes: '' });
      const difference = result.difference == null
        ? ''
        : ` Écart : ${formatMoney(result.difference, settings.currency)}.`;
      setNotice(`${result.message || 'Opération de caisse enregistrée.'}${difference}`);
      await refresh().catch(() => {});
    } catch (failure) {
      setNotice(failure.message || 'L’opération de caisse a échoué.');
    } finally {
      setSaving(false);
    }
  };

  const openSessionForm = () => {
    setNotice('');
    setSessionDraft({
      accountId: String(cashAccounts.find((account) => account.is_default)?.id || cashAccounts[0]?.id || ''),
      amount: session ? String(session.expected_amount ?? 0) : '0',
      notes: '',
    });
    setShowSession(true);
  };

  if (loading && !data) return <div className="erp-standalone" role="status">Chargement de la trésorerie…</div>;
  if (!data) return <InlineMessage tone="error">{loadError || 'Impossible de charger la trésorerie.'}</InlineMessage>;

  return (
    <div className="erp-page">
      <PageHeader title="Trésorerie" subtitle="Soldes, mouvements et sessions de caisse de l’entreprise active." action={<>
        {canExport && ['Vue d’ensemble', 'Comptes', 'Mouvements'].includes(tab) && <ActionButton variant="secondary" onClick={exportTreasuryTab}>Exporter CSV</ActionButton>}
        {tab === 'Comptes' && canManageTreasury && <ActionButton onClick={() => { setAccountError(''); setShowAccount(true); }}>＋ Nouveau compte</ActionButton>}
        {tab === 'Mouvements' && canManageTreasury && <ActionButton onClick={openMovementForm}>＋ Nouveau mouvement</ActionButton>}
      </>} />
      {loadError && <InlineMessage tone="error">{loadError}</InlineMessage>}
      {notice && <InlineMessage tone={notice.includes('enregistré') || notice.includes('ouverte') || notice.includes('fermée') ? 'success' : 'error'}>{notice}</InlineMessage>}
      <div className="erp-metrics-grid">
        <MetricCard label="Solde total" value={formatMoney(balance, settings.currency)} detail="Comptes actifs" icon="◈" />
        <MetricCard label="Entrées récentes" value={formatMoney(totalIn, settings.currency)} detail="Mouvements chargés" icon="↘" tone="green" />
        <MetricCard label="Sorties récentes" value={formatMoney(totalOut, settings.currency)} detail="Mouvements chargés" icon="↗" tone="red" />
        <MetricCard label="Session de caisse" value={session ? 'Ouverte' : 'Fermée'} detail={session ? `Depuis ${new Date(session.opened_at).toLocaleString('fr-FR')}` : 'Aucune session personnelle ouverte'} icon="◷" tone={session ? 'green' : 'amber'} />
      </div>
      <Panel className="erp-tab-panel">
        <Tabs items={treasuryTabs} value={tab} onChange={setTab} />
        {tab === 'Vue d’ensemble' && <div className="erp-treasury-overview">
          <div className="erp-overview-total"><span>Solde disponible</span><strong>{formatMoney(balance, settings.currency)}</strong><small>Solde courant des comptes actifs</small></div>
          <h3>Solde par compte</h3>
          <DataTable columns={[
            { key: 'name', label: 'Compte' }, { key: 'type', label: 'Type' },
            { key: 'balance', label: 'Solde', render: (value) => <strong>{formatMoney(value, settings.currency)}</strong> },
          ]} rows={accounts} />
        </div>}
        {tab === 'Comptes' && <DataTable columns={[
          { key: 'name', label: 'Nom du compte' }, { key: 'type', label: 'Type de compte' },
          { key: 'initial_balance', label: 'Solde initial', render: (value) => formatMoney(value, settings.currency) },
          { key: 'is_default', label: 'Par défaut', render: (value) => value ? 'Oui' : 'Non' },
          { key: 'status', label: 'Statut', render: (value) => <StatusBadge>{value}</StatusBadge> },
        ]} rows={accounts} />}
        {tab === 'Mouvements' && <DataTable columns={[
          { key: 'date', label: 'Date', render: (value) => value ? new Date(value).toLocaleString('fr-FR') : '—' }, { key: 'label', label: 'Libellé' }, { key: 'account', label: 'Compte' },
          { key: 'type', label: 'Type', render: (value) => <StatusBadge>{value}</StatusBadge> },
          { key: 'amount', label: 'Montant', render: (value, movement) => <strong className={movement.type === 'Entrée' ? 'erp-text-success' : 'erp-text-danger'}>{movement.type === 'Entrée' ? '+' : '−'} {formatMoney(value, settings.currency)}</strong> },
        ]} rows={movements} />}
        {tab === 'Session de caisse' && <div className="erp-session-card">
          <span className={`erp-session-icon${session ? ' is-open' : ''}`}>◷</span>
          <h3>{session ? 'Session de caisse ouverte' : 'Aucune session ouverte'}</h3>
          <p>{session
            ? `Fond initial : ${formatMoney(session.opening_amount, settings.currency)} · montant attendu : ${formatMoney(session.expected_amount, settings.currency)}`
            : 'Ouvrez une session pour enregistrer les mouvements de caisse liés à votre compte.'}</p>
          <ActionButton variant={session ? 'danger' : 'primary'} onClick={openSessionForm} disabled={session ? !canOperateSession : (!canCreateSales || !cashAccounts.length)}>
            {session ? 'Clôturer la session' : 'Ouvrir une session'}
          </ActionButton>
          {!session && !canCreateSales && <small>La permission create_sales est requise pour ouvrir une session.</small>}
          {session && !canOperateSession && <small>La permission create_sales ou manage_treasury est requise pour fermer cette session.</small>}
          {!session && !cashAccounts.length && <small>Aucun compte de caisse actif n’est configuré.</small>}
        </div>}
      </Panel>
      {showAccount && <Modal title="Nouveau compte de trésorerie" onClose={() => { if (!saving) setShowAccount(false); }} footer={<>
        <ActionButton variant="secondary" onClick={() => setShowAccount(false)} disabled={saving}>Annuler</ActionButton>
        <ActionButton onClick={() => document.getElementById('treasury-account-form').requestSubmit()} disabled={saving}>{saving ? 'Création…' : 'Créer le compte'}</ActionButton>
      </>}>
        <form id="treasury-account-form" className="erp-form-grid" onSubmit={saveAccount}>
          {accountError && <div className="erp-field-span"><InlineMessage tone="error">{accountError}</InlineMessage></div>}
          <Field label="Nom du compte" value={accountDraft.name} onChange={(name) => setAccountDraft({ ...accountDraft, name })} required maxLength="100" />
          <Field label="Type de compte" value={accountDraft.accountType} onChange={(accountType) => setAccountDraft({ ...accountDraft, accountType })} options={[
            { value: 'CASH', label: 'Espèces' },
            { value: 'BANK', label: 'Banque' },
            { value: 'MOBILE_MONEY', label: 'Mobile money' },
          ]} />
          <Field label={'Solde initial (' + settings.currency + ')'} type="number" min="0" max="999999999" step="0.01" value={accountDraft.initialBalance} onChange={(initialBalance) => setAccountDraft({ ...accountDraft, initialBalance })} required />
          {accountDraft.accountType === 'BANK' && <>
            <Field label="Nom de la banque" value={accountDraft.bankName} onChange={(bankName) => setAccountDraft({ ...accountDraft, bankName })} maxLength="100" />
            <Field label="Numéro de compte" value={accountDraft.accountNumber} onChange={(accountNumber) => setAccountDraft({ ...accountDraft, accountNumber })} maxLength="50" />
          </>}
          {accountDraft.accountType === 'MOBILE_MONEY' && <Field label="Téléphone" value={accountDraft.phoneNumber} onChange={(phoneNumber) => setAccountDraft({ ...accountDraft, phoneNumber })} maxLength="30" />}
          <label className="erp-field-span"><input type="checkbox" checked={accountDraft.isDefault} onChange={(event) => setAccountDraft({ ...accountDraft, isDefault: event.target.checked })} /> Définir comme compte par défaut</label>
        </form>
      </Modal>}
      {showMovement && <Modal title="Nouveau mouvement de trésorerie" onClose={() => setShowMovement(false)} footer={<><ActionButton variant="secondary" onClick={() => setShowMovement(false)}>Annuler</ActionButton><ActionButton onClick={() => document.getElementById('movement-form').requestSubmit()} disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</ActionButton></>}>
        <form id="movement-form" className="erp-form-grid" onSubmit={saveMovement}>
          <div className="erp-field-span"><Field label="Libellé" value={draft.label} onChange={(label) => setDraft({ ...draft, label })} required placeholder="Motif du mouvement" /></div>
          <label className="erp-field"><span>Compte</span><select value={draft.accountId} onChange={(event) => setDraft({ ...draft, accountId: event.target.value })} required>{accounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}</select></label>
          <Field label="Type" value={draft.type} onChange={(type) => setDraft({ ...draft, type })} options={[{ value: 'IN', label: 'Entrée' }, { value: 'OUT', label: 'Sortie' }]} />
          <Field label="Catégorie" value={draft.category} onChange={(category) => setDraft({ ...draft, category })} options={movementCategories.map((category) => ({ value: category, label: category }))} />
          <div className="erp-field-span"><Field label={'Montant (' + settings.currency + ')'} type="number" min="0.01" step="0.01" value={draft.amount} onChange={(amount) => setDraft({ ...draft, amount })} required /></div>
          <Field label="Référence (facultatif)" value={draft.reference} onChange={(reference) => setDraft({ ...draft, reference })} maxLength="100" />
        </form>
      </Modal>}
      {showSession && <Modal title={session ? 'Clôturer la session de caisse' : 'Ouvrir une session de caisse'} onClose={() => setShowSession(false)} footer={<><ActionButton variant="secondary" onClick={() => setShowSession(false)}>Annuler</ActionButton><ActionButton onClick={() => document.getElementById('session-form').requestSubmit()} disabled={saving}>{saving ? 'Enregistrement…' : session ? 'Clôturer' : 'Ouvrir'}</ActionButton></>}>
        <form id="session-form" className="erp-form-grid" onSubmit={saveSessionAction}>
          {!session && <label className="erp-field erp-field-span"><span>Compte de caisse</span><select value={sessionDraft.accountId} onChange={(event) => setSessionDraft({ ...sessionDraft, accountId: event.target.value })} required>{cashAccounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}</select></label>}
          <div className="erp-field-span"><Field label={session ? `Montant compté (${settings.currency})` : `Fond de caisse (${settings.currency})`} type="number" min="0" step="0.01" value={sessionDraft.amount} onChange={(amount) => setSessionDraft({ ...sessionDraft, amount })} required /></div>
          <div className="erp-field-span"><Field label="Notes" value={sessionDraft.notes} onChange={(notes) => setSessionDraft({ ...sessionDraft, notes })} /></div>
        </form>
      </Modal>}
      <Panel
        title={'Clôture mensuelle — ' + new Date(currentPeriod + '-01T00:00:00').toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' })}
        description={currentClosure?.status === 'CLOSED' ? 'Les totaux du mois ont été figés.' : 'Aperçu des ventes et dépenses du mois courant.'}
        action={canManageTreasury && currentClosure?.status !== 'CLOSED' && (
          <ActionButton onClick={() => { setMonthCloseError(''); setShowMonthClose(true); }}>Clôturer le mois</ActionButton>
        )}
      >
        {monthlySummary && <div className="erp-metrics-grid">
          <MetricCard label="Ventes" value={monthlySummary.sales_count + ' · ' + formatMoney(monthlySummary.total_sales, settings.currency)} />
          <MetricCard label="Encaissé" value={formatMoney(monthlySummary.total_collected, settings.currency)} />
          <MetricCard label="Crédit restant" value={formatMoney(monthlySummary.total_credit, settings.currency)} />
          <MetricCard label="Dépenses" value={formatMoney(monthlySummary.total_out, settings.currency)} />
          <MetricCard label="Net" value={formatMoney(monthlySummary.net, settings.currency)} />
        </div>}
        <h3>Historique des clôtures</h3>
        <DataTable columns={[
          { key: 'period', label: 'Période' },
          { key: 'sales_count', label: 'Ventes' },
          { key: 'total_sales', label: 'Total ventes', render: (value) => formatMoney(value, settings.currency) },
          { key: 'total_collected', label: 'Encaissé', render: (value) => formatMoney(value, settings.currency) },
          { key: 'total_credit', label: 'Crédit', render: (value) => formatMoney(value, settings.currency) },
          { key: 'total_out', label: 'Dépenses', render: (value) => formatMoney(value, settings.currency) },
          { key: 'net', label: 'Net', render: (value) => formatMoney(value, settings.currency) },
          { key: 'status', label: 'Statut', render: (value) => <StatusBadge>{value}</StatusBadge> },
          { key: 'closed_at', label: 'Clôturé le', render: (value) => value ? new Date(value).toLocaleDateString('fr-FR') : '—' },
        ]} rows={closures} emptyMessage="Aucune clôture mensuelle." />
      </Panel>
      {showMonthClose && <Modal title="Confirmer la clôture mensuelle" onClose={() => { if (!saving) setShowMonthClose(false); }} footer={<>
        <ActionButton variant="secondary" onClick={() => setShowMonthClose(false)} disabled={saving}>Annuler</ActionButton>
        <ActionButton variant="danger" onClick={() => document.getElementById('month-close-form').requestSubmit()} disabled={saving}>{saving ? 'Clôture…' : 'Confirmer la clôture'}</ActionButton>
      </>}>
        <form id="month-close-form" className="erp-form-grid" onSubmit={saveMonthClosure}>
          <p className="erp-field-span">Cette opération fige les totaux de {currentPeriod}. Un mois clôturé ne peut pas être clôturé une seconde fois.</p>
          {monthCloseError && <div className="erp-field-span"><InlineMessage tone="error">{monthCloseError}</InlineMessage></div>}
          <div className="erp-field-span"><Field label="Notes (facultatif)" value={monthCloseNotes} onChange={setMonthCloseNotes} maxLength="1000" /></div>
        </form>
      </Modal>}
    </div>
  );
}
