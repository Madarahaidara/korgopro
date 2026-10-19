// ============================================================================
// Administration mobile — accès aux fonctions d'administration desktop
// compatibles avec l'API mobile. La création d'utilisateur reste exclue.
// ============================================================================
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  RefreshControl,
  ScrollView,
  Share,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import Icon from '../components/Icon';
import {
  Banner,
  Badge,
  Btn,
  Card,
  ChipGroup,
  Empty,
  Input,
  KeyValue,
  Loading,
  Modal,
  SectionTitle,
} from '../components/ui';
import { useAuth } from '../context/AuthContext';
import {
  CANONICAL_ROLES,
  PAGE_SIZE,
  PERMISSIONS,
  ROLE_LABELS,
  deleteAdminUser,
  deleteOldActivityLogs,
  getDatabaseTableCounts,
  getRolePermissions,
  listActivityLogs,
  listAdminUsers,
  listSaleLogs,
  setAdminUserActive,
  setAdminUserPassword,
  updateAdminUser,
} from '../api/adminApi';
import { checkHealth, getUptime } from '../api/systemApi';
import { colors, sp } from '../theme';

const TABS = [
  { id: 'overview', label: 'Vue générale' },
  { id: 'users', label: 'Utilisateurs' },
  { id: 'roles', label: 'Rôles' },
  { id: 'activity', label: 'Journal système' },
  { id: 'sales', label: 'Journal ventes' },
  { id: 'data', label: 'Base de données' },
];

const ACTIONS = [
  'Connexion',
  'Déconnexion',
  'Création utilisateur',
  'Modification utilisateur',
  'Suppression utilisateur',
  'Changement mot de passe',
  'Modification rôle',
  'Export données',
  'Modification permissions',
  'Backup base données',
  'Restauration base données',
  'Optimisation base données',
  'Accès administration',
  'Consultation base données',
  'Exécution SQL',
  'Nettoyage logs',
  'Autre',
];

const SALE_ACTIONS = ['CREATE', 'CANCEL', 'REFUND', 'PRINT', 'DELETE', 'PAID'];

function dateLabel(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('fr-FR');
}

function errorText(error) {
  return error?.message || 'Une erreur inattendue est survenue.';
}

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function monthAgoISO() {
  const date = new Date();
  date.setDate(date.getDate() - 30);
  return date.toISOString().slice(0, 10);
}

export default function AdminScreen() {
  const { user } = useAuth();
  const [tab, setTab] = useState('overview');
  const [health, setHealth] = useState(null);
  const [users, setUsers] = useState([]);
  const [activity, setActivity] = useState({ rows: [], total: 0 });
  const [saleLogs, setSaleLogs] = useState({ rows: [], total: 0 });
  const [tableCounts, setTableCounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [page, setPage] = useState(0);
  const [userQuery, setUserQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [activityDraft, setActivityDraft] = useState({
    username: '',
    action: '',
    startDate: monthAgoISO(),
    endDate: todayISO(),
  });
  const [activityFilter, setActivityFilter] = useState(activityDraft);
  const [saleDraft, setSaleDraft] = useState({
    saleNumber: '',
    username: '',
    customerName: '',
    action: '',
    startDate: monthAgoISO(),
    endDate: todayISO(),
  });
  const [saleFilter, setSaleFilter] = useState(saleDraft);
  const [profileEdit, setProfileEdit] = useState(null);
  const [passwordEdit, setPasswordEdit] = useState(null);
  const [profileDraft, setProfileDraft] = useState({ username: '', role: '' });
  const [newPassword, setNewPassword] = useState('');
  const [busy, setBusy] = useState(false);

  const isAdmin = String(user?.role || '').toUpperCase() === 'ADMIN';

  const load = useCallback(async (isRefresh = false) => {
    setError(null);
    setNotice(null);
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    try {
      if (tab === 'overview') {
        setHealth(await checkHealth());
      } else if (tab === 'users') {
        setUsers(await listAdminUsers());
      } else if (tab === 'activity') {
        setActivity(await listActivityLogs({ ...activityFilter, page }));
      } else if (tab === 'sales') {
        setSaleLogs(await listSaleLogs({ ...saleFilter, page }));
      } else if (tab === 'data') {
        setTableCounts(await getDatabaseTableCounts());
      }
    } catch (loadError) {
      setError(errorText(loadError));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [activityFilter, page, saleFilter, tab]);

  useEffect(() => {
    load();
  }, [load]);

  const filteredUsers = useMemo(() => users.filter((entry) => {
    const query = userQuery.trim().toLowerCase();
    const matchesQuery = !query
      || [entry.username, entry.email, entry.role].some((value) =>
        String(value || '').toLowerCase().includes(query));
    const matchesRole = roleFilter === 'all' || entry.role === roleFilter;
    const matchesStatus = statusFilter === 'all'
      || (statusFilter === 'active' ? entry.active : !entry.active);
    return matchesQuery && matchesRole && matchesStatus;
  }), [roleFilter, statusFilter, userQuery, users]);

  const changeTab = (nextTab) => {
    setPage(0);
    setTab(nextTab);
  };

  const runUserAction = async (action, target) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action(target);
      await listAdminUsers().then(setUsers);
      setNotice('Modification enregistrée.');
      setProfileEdit(null);
      setPasswordEdit(null);
      setNewPassword('');
    } catch (actionError) {
      setError(errorText(actionError));
    } finally {
      setBusy(false);
    }
  };

  const openProfileEditor = (target) => {
    setProfileDraft({ username: target.username || '', role: target.role || 'CAISSIER' });
    setProfileEdit(target);
  };

  const saveProfile = () => {
    if (!profileDraft.username.trim()) {
      setError("Le nom d'utilisateur ne peut pas être vide.");
      return;
    }
    runUserAction((target) => updateAdminUser({
      email: target.email,
      username: profileDraft.username.trim(),
      role: profileDraft.role,
    }), profileEdit);
  };

  const resetPassword = () => {
    if (!newPassword) {
      setError('Saisissez le nouveau mot de passe.');
      return;
    }
    runUserAction(
      (target) => setAdminUserPassword(target.email, newPassword),
      passwordEdit
    );
  };

  const confirmToggleActive = (target) => {
    const active = !target.active;
    Alert.alert(
      'Confirmer',
      `${active ? 'Activer' : 'Désactiver'} le compte ${target.username} ?`,
      [
        { text: 'Annuler', style: 'cancel' },
        {
          text: active ? 'Activer' : 'Désactiver',
          style: active ? 'default' : 'destructive',
          onPress: () => runUserAction(
            (entry) => setAdminUserActive(entry.email, active),
            target
          ),
        },
      ]
    );
  };

  const confirmDeleteUser = (target) => {
    Alert.alert(
      'Supprimer le compte',
      `Cette action supprimera définitivement ${target.username}. Continuer ?`,
      [
        { text: 'Annuler', style: 'cancel' },
        {
          text: 'Supprimer',
          style: 'destructive',
          onPress: () => runUserAction(
            (entry) => deleteAdminUser(entry.email),
            target
          ),
        },
      ]
    );
  };

  const shareUsers = async () => {
    try {
      await Share.share({
        title: 'Export des utilisateurs',
        message: JSON.stringify(users, null, 2),
      });
    } catch (shareError) {
      setError(errorText(shareError));
    }
  };

  const shareDiagnostics = async () => {
    setBusy(true);
    setError(null);
    try {
      const currentHealth = health || await checkHealth();
      const report = {
        app: 'Korgo Pro Mobile',
        generated_at: new Date().toISOString(),
        platform: require('react-native').Platform.OS,
        platform_version: String(require('react-native').Platform.Version),
        uptime_ms: getUptime(),
        user_role: user?.role || null,
        health: currentHealth,
        database_tables: tableCounts,
      };
      await Share.share({
        title: 'Rapport de diagnostic Korgo Pro',
        message: JSON.stringify(report, null, 2),
      });
    } catch (shareError) {
      setError(errorText(shareError));
    } finally {
      setBusy(false);
    }
  };

  const cleanActivity = () => {
    Alert.alert(
      'Nettoyage du journal',
      'Supprimer définitivement les entrées de plus de 30 jours ?',
      [
        { text: 'Annuler', style: 'cancel' },
        {
          text: 'Nettoyer',
          style: 'destructive',
          onPress: async () => {
            setBusy(true);
            setError(null);
            try {
              const deleted = await deleteOldActivityLogs(30);
              setNotice(`${deleted} entrée(s) supprimée(s).`);
              await load(true);
            } catch (cleanupError) {
              setError(errorText(cleanupError));
            } finally {
              setBusy(false);
            }
          },
        },
      ]
    );
  };

  const applyActivityFilters = () => {
    setPage(0);
    setActivityFilter({ ...activityDraft });
  };

  const applySaleFilters = () => {
    setPage(0);
    setSaleFilter({ ...saleDraft });
  };

  const totalForTab = tab === 'activity' ? activity.total : saleLogs.total;
  const pageCount = Math.max(1, Math.ceil(totalForTab / PAGE_SIZE));

  if (!isAdmin) {
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
    <>
      <ScrollView
        style={styles.screen}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => load(true)} />
        }
      >
        <Card>
          <SectionTitle>Administration</SectionTitle>
          <Text style={styles.meta}>
            Outils de gestion et de diagnostic. La création d’utilisateur n’est pas disponible sur mobile.
          </Text>
          <View style={styles.tabs}>
            <ChipGroup
              options={TABS.map(({ id, label }) => ({ value: id, label }))}
              value={tab}
              onChange={changeTab}
            />
          </View>
        </Card>

        {error ? <Banner tone="danger" title="Opération impossible" message={error} /> : null}
        {notice ? <Banner tone="success" message={notice} /> : null}
        {loading ? <Loading label="Chargement de l’administration…" /> : null}

        {!loading && tab === 'overview' ? (
          <Overview health={health} onDiagnostics={shareDiagnostics} busy={busy} />
        ) : null}
        {!loading && tab === 'users' ? (
          <UsersPanel
            users={filteredUsers}
            query={userQuery}
            setQuery={setUserQuery}
            roleFilter={roleFilter}
            setRoleFilter={setRoleFilter}
            statusFilter={statusFilter}
            setStatusFilter={setStatusFilter}
            currentUser={user}
            onEdit={openProfileEditor}
            onResetPassword={setPasswordEdit}
            onToggleActive={confirmToggleActive}
            onDelete={confirmDeleteUser}
            onExport={shareUsers}
          />
        ) : null}
        {!loading && tab === 'roles' ? <RolesPanel /> : null}
        {!loading && tab === 'activity' ? (
          <ActivityPanel
            result={activity}
            filters={activityDraft}
            setFilters={setActivityDraft}
            onFilter={applyActivityFilters}
            onCleanup={cleanActivity}
            onDiagnostics={shareDiagnostics}
            busy={busy}
            page={page}
            pageCount={pageCount}
            onPage={setPage}
          />
        ) : null}
        {!loading && tab === 'sales' ? (
          <SalesPanel
            result={saleLogs}
            filters={saleDraft}
            setFilters={setSaleDraft}
            onFilter={applySaleFilters}
            page={page}
            pageCount={pageCount}
            onPage={setPage}
          />
        ) : null}
        {!loading && tab === 'data' ? (
          <DatabasePanel counts={tableCounts} onDiagnostics={shareDiagnostics} busy={busy} />
        ) : null}
      </ScrollView>

      <Modal
        visible={!!profileEdit}
        title="Modifier l’utilisateur"
        onClose={() => setProfileEdit(null)}
      >
        <Text style={styles.meta}>{profileEdit?.email}</Text>
        <Text style={styles.label}>Nom d’utilisateur</Text>
        <Input
          value={profileDraft.username}
          onChangeText={(value) => setProfileDraft((draft) => ({ ...draft, username: value }))}
          autoCapitalize="none"
        />
        <Text style={styles.label}>Rôle</Text>
        <ChipGroup
          options={CANONICAL_ROLES.map((role) => ({
            value: role,
            label: ROLE_LABELS[role] || role,
          }))}
          value={profileDraft.role}
          onChange={(role) => setProfileDraft((draft) => ({ ...draft, role }))}
        />
        <Btn title="Enregistrer" onPress={saveProfile} loading={busy} style={styles.modalAction} />
      </Modal>

      <Modal
        visible={!!passwordEdit}
        title="Réinitialiser le mot de passe"
        onClose={() => { setPasswordEdit(null); setNewPassword(''); }}
      >
        <Text style={styles.meta}>Compte : {passwordEdit?.username}</Text>
        <Text style={styles.label}>Nouveau mot de passe</Text>
        <Input
          value={newPassword}
          onChangeText={setNewPassword}
          secureTextEntry
          autoCapitalize="none"
          autoCorrect={false}
        />
        <Btn
          title="Réinitialiser"
          onPress={resetPassword}
          loading={busy}
          style={styles.modalAction}
        />
      </Modal>
    </>
  );
}

function Overview({ health, onDiagnostics, busy }) {
  return (
    <Card>
      <SectionTitle>État du service</SectionTitle>
      <KeyValue label="Statut" value={health?.status || '—'} />
      <KeyValue label="Latence" value={health?.latency != null ? `${health.latency} ms` : '—'} />
      <KeyValue label="Source" value={health?.served_by || '—'} />
      <KeyValue label="Requêtes" value={health?.requests != null ? String(health.requests) : '—'} />
      <KeyValue label="Rôle serveur" value={health?.context?.role || '—'} />
      <KeyValue label="Message" value={health?.message || '—'} />
      <Btn
        title="Partager le rapport de diagnostic"
        onPress={onDiagnostics}
        loading={busy}
        style={styles.actionButton}
      />
    </Card>
  );
}

function UsersPanel({
  users,
  query,
  setQuery,
  roleFilter,
  setRoleFilter,
  statusFilter,
  setStatusFilter,
  currentUser,
  onEdit,
  onResetPassword,
  onToggleActive,
  onDelete,
  onExport,
}) {
  return (
    <Card>
      <SectionTitle
        right={<Btn title="Exporter" variant="ghost" onPress={onExport} style={styles.smallButton} />}
      >
        Gestion des utilisateurs
      </SectionTitle>
      <Text style={styles.meta}>
        Modification, activation, désactivation, suppression et réinitialisation des mots de passe.
      </Text>
      <Input
        value={query}
        onChangeText={setQuery}
        placeholder="Rechercher un utilisateur"
        autoCapitalize="none"
        style={styles.filterInput}
      />
      <ChipGroup
        options={[
          { value: 'all', label: 'Tous les rôles' },
          ...CANONICAL_ROLES.map((role) => ({ value: role, label: ROLE_LABELS[role] || role })),
        ]}
        value={roleFilter}
        onChange={setRoleFilter}
      />
      <ChipGroup
        options={[
          { value: 'all', label: 'Tous les statuts' },
          { value: 'active', label: 'Actifs' },
          { value: 'inactive', label: 'Inactifs' },
        ]}
        value={statusFilter}
        onChange={setStatusFilter}
      />
      {users.length === 0 ? <Empty title="Aucun utilisateur trouvé." /> : null}
      {users.map((entry) => {
        const isCurrent = String(entry.id) === String(currentUser?.id);
        return (
          <View key={entry.id} style={styles.record}>
            <View style={styles.recordHeader}>
              <View style={styles.recordMain}>
                <Text style={styles.recordTitle}>{entry.username || '—'}</Text>
                <Text style={styles.meta}>{entry.email || '—'}</Text>
              </View>
              <Badge status={entry.active ? 'ACTIF' : 'INACTIF'} />
            </View>
            <KeyValue label="Rôle" value={ROLE_LABELS[entry.role] || entry.role || '—'} />
            <KeyValue label="Créé le" value={dateLabel(entry.created_at)} />
            <KeyValue label="Dernière connexion" value={dateLabel(entry.last_login)} />
            <View style={styles.actionRow}>
              <Btn title="Modifier" variant="ghost" onPress={() => onEdit(entry)} style={styles.rowButton} />
              <Btn title="Mot de passe" variant="ghost" onPress={() => onResetPassword(entry)} style={styles.rowButton} />
              <Btn
                title={entry.active ? 'Désactiver' : 'Activer'}
                variant={entry.active ? 'danger' : 'success'}
                onPress={() => onToggleActive(entry)}
                disabled={isCurrent}
                style={styles.rowButton}
              />
              <Btn
                title="Supprimer"
                variant="danger"
                onPress={() => onDelete(entry)}
                disabled={isCurrent}
                style={styles.rowButton}
              />
            </View>
          </View>
        );
      })}
    </Card>
  );
}

function RolesPanel() {
  return (
    <Card>
      <SectionTitle>Rôles et permissions</SectionTitle>
      <Text style={styles.meta}>
        Matrice canonique appliquée par l’application et les contrôles serveur.
      </Text>
      {CANONICAL_ROLES.map((role) => {
        const granted = new Set(getRolePermissions(role));
        return (
          <View key={role} style={styles.record}>
            <Text style={styles.recordTitle}>{ROLE_LABELS[role] || role}</Text>
            <Text style={styles.meta}>
              {granted.size} permission(s) sur {PERMISSIONS.length}
            </Text>
            {PERMISSIONS.map((permission) => (
              <View key={permission} style={styles.permissionRow}>
                <Text style={styles.permissionName}>{permission.replaceAll('_', ' ')}</Text>
                <Badge status={granted.has(permission) ? 'OUI' : 'NON'} />
              </View>
            ))}
          </View>
        );
      })}
      <Banner
        tone="info"
        title="Matrice en lecture seule"
        message="La matrice est définie par le code et les RPC du serveur; une modification locale ne changerait pas les droits réellement appliqués."
      />
    </Card>
  );
}

function ActivityPanel({
  result,
  filters,
  setFilters,
  onFilter,
  onCleanup,
  onDiagnostics,
  busy,
  page,
  pageCount,
  onPage,
}) {
  return (
    <Card>
      <SectionTitle>Journal d’activité système</SectionTitle>
      <View style={styles.filterGroup}>
        <Input
          value={filters.username}
          onChangeText={(username) => setFilters((current) => ({ ...current, username }))}
          placeholder="Nom d’utilisateur"
          style={styles.filterInput}
        />
        <Input
          value={filters.action}
          onChangeText={(action) => setFilters((current) => ({ ...current, action }))}
          placeholder="Action"
          style={styles.filterInput}
        />
        <Input
          value={filters.startDate}
          onChangeText={(startDate) => setFilters((current) => ({ ...current, startDate }))}
          placeholder="Du (AAAA-MM-JJ)"
          style={styles.filterInput}
        />
        <Input
          value={filters.endDate}
          onChangeText={(endDate) => setFilters((current) => ({ ...current, endDate }))}
          placeholder="Au (AAAA-MM-JJ)"
          style={styles.filterInput}
        />
      </View>
      <View style={styles.actionRow}>
        <Btn title="Filtrer" onPress={onFilter} style={styles.rowButton} />
        <Btn title="Nettoyer > 30 j" variant="danger" onPress={onCleanup} style={styles.rowButton} />
        <Btn title="Diagnostic" variant="ghost" onPress={onDiagnostics} loading={busy} style={styles.rowButton} />
      </View>
      <Text style={styles.meta}>{result.total} entrée(s) · page {page + 1}/{pageCount}</Text>
      {result.rows.length === 0 ? <Empty title="Aucun événement trouvé." /> : null}
      {result.rows.map((entry) => (
        <View key={entry.id} style={styles.record}>
          <Text style={styles.recordTitle}>{entry.action}</Text>
          <KeyValue label="Date" value={dateLabel(entry.created_at)} />
          <KeyValue label="Utilisateur" value={entry.username || '—'} />
          <KeyValue label="Détails" value={entry.details || '—'} />
          <KeyValue label="IP" value={entry.ip_address || '—'} />
        </View>
      ))}
      <Pagination page={page} pageCount={pageCount} onPage={onPage} />
    </Card>
  );
}

function SalesPanel({ result, filters, setFilters, onFilter, page, pageCount, onPage }) {
  const setField = (field, value) => setFilters((current) => ({ ...current, [field]: value }));
  return (
    <Card>
      <SectionTitle>Journal des ventes</SectionTitle>
      <View style={styles.filterGroup}>
        <Input value={filters.saleNumber} onChangeText={(value) => setField('saleNumber', value)} placeholder="N° vente" style={styles.filterInput} />
        <Input value={filters.username} onChangeText={(value) => setField('username', value)} placeholder="Caissier" style={styles.filterInput} />
        <Input value={filters.customerName} onChangeText={(value) => setField('customerName', value)} placeholder="Client" style={styles.filterInput} />
        <Input value={filters.startDate} onChangeText={(value) => setField('startDate', value)} placeholder="Du (AAAA-MM-JJ)" style={styles.filterInput} />
        <Input value={filters.endDate} onChangeText={(value) => setField('endDate', value)} placeholder="Au (AAAA-MM-JJ)" style={styles.filterInput} />
      </View>
      <ChipGroup
        options={[{ value: '', label: 'Toutes' }, ...SALE_ACTIONS.map((action) => ({ value: action, label: action }))]}
        value={filters.action}
        onChange={(action) => setField('action', action)}
      />
      <Btn title="Filtrer" onPress={onFilter} style={styles.actionButton} />
      <Text style={styles.meta}>{result.total} entrée(s) · page {page + 1}/{pageCount}</Text>
      {result.rows.length === 0 ? <Empty title="Aucune opération trouvée." /> : null}
      {result.rows.map((entry) => (
        <View key={entry.id} style={styles.record}>
          <View style={styles.recordHeader}>
            <Text style={styles.recordTitle}>{entry.sale_number || 'Vente'} · {entry.action}</Text>
            <Badge status={entry.user_role || '—'} />
          </View>
          <KeyValue label="Date" value={dateLabel(entry.created_at)} />
          <KeyValue label="Caissier" value={entry.username || '—'} />
          <KeyValue label="Client" value={entry.customer_name || 'Client général'} />
          <KeyValue label="Montant" value={`${Number(entry.total_amount || 0).toLocaleString('fr-FR')} FCFA`} />
          <KeyValue label="Paiement" value={entry.payment_method || '—'} />
          <KeyValue label="Détails" value={entry.details || '—'} />
        </View>
      ))}
      <Pagination page={page} pageCount={pageCount} onPage={onPage} />
    </Card>
  );
}

function DatabasePanel({ counts, onDiagnostics, busy }) {
  const total = counts.reduce((sum, entry) => sum + entry.count, 0);
  return (
    <Card>
      <SectionTitle>État de la base de données</SectionTitle>
      <Text style={styles.meta}>
        Comptages accessibles par l’API mobile (RLS). La restauration et l’optimisation nécessitent une connexion d’administration directe, indisponible dans l’application mobile.
      </Text>
      <KeyValue label="Tables contrôlées" value={String(counts.length)} />
      <KeyValue label="Enregistrements visibles" value={total.toLocaleString('fr-FR')} />
      {counts.map(({ table, count }) => (
        <KeyValue key={table} label={table} value={count.toLocaleString('fr-FR')} />
      ))}
      <Btn
        title="Partager le diagnostic"
        onPress={onDiagnostics}
        loading={busy}
        style={styles.actionButton}
      />
    </Card>
  );
}

function Pagination({ page, pageCount, onPage }) {
  if (pageCount <= 1) return null;
  return (
    <View style={styles.actionRow}>
      <Btn
        title="Précédent"
        variant="ghost"
        disabled={page <= 0}
        onPress={() => onPage(page - 1)}
        style={styles.rowButton}
      />
      <Text style={styles.pageLabel}>{page + 1} / {pageCount}</Text>
      <Btn
        title="Suivant"
        variant="ghost"
        disabled={page + 1 >= pageCount}
        onPress={() => onPage(page + 1)}
        style={styles.rowButton}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  content: { padding: sp(3), paddingBottom: sp(10), gap: sp(3) },
  meta: { fontSize: 13, color: colors.textMuted, marginTop: sp(1) },
  tabs: { marginTop: sp(2) },
  center: { alignItems: 'center', gap: sp(2), paddingVertical: sp(4) },
  title: { fontSize: 17, fontWeight: '800', color: colors.text },
  record: {
    borderTopColor: colors.border,
    borderTopWidth: 1,
    paddingTop: sp(2.5),
    marginTop: sp(2.5),
  },
  recordHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: sp(2) },
  recordMain: { flex: 1 },
  recordTitle: { color: colors.text, fontSize: 15, fontWeight: '700' },
  actionRow: { flexDirection: 'row', flexWrap: 'wrap', gap: sp(1.5), marginTop: sp(2) },
  rowButton: { flex: 1, minWidth: 105 },
  smallButton: { minWidth: 100, paddingHorizontal: sp(2) },
  actionButton: { marginTop: sp(2) },
  filterGroup: { gap: sp(1.5), marginBottom: sp(2) },
  filterInput: { marginVertical: sp(1) },
  label: { color: colors.textMuted, fontSize: 12, fontWeight: '700', marginTop: sp(2), marginBottom: sp(1) },
  modalAction: { marginTop: sp(3) },
  permissionRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: sp(1) },
  permissionName: { color: colors.text, fontSize: 13, textTransform: 'capitalize', flex: 1 },
  pageLabel: { color: colors.textMuted, fontWeight: '700', alignSelf: 'center', paddingHorizontal: sp(2) },
});
