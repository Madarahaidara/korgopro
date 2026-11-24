import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  addOrganizationMember, canManageAllDatabase, cleanupOrganizationActivityLogs,
  exportAllOrganizationsData, inviteOrganizationMember, listActivityLogs,
  listOrganizationDatabaseTables, listOrganizationMembers,
  listOrganizationRolePermissions, listSaleLogs, readOrganizationDatabaseTable,
  removeOrganizationMember, resetOrganizationRolePermissions,
  restoreAllOrganizationsData, saveOrganizationRolePermissions,
  sendOrganizationMemberPasswordReset, updateOrganizationMember,
} from '../api/businessApi';
import { useBusinessData } from '../api/useBusinessData';
import {
  ActionButton, DataTable, InlineMessage, Modal, PageHeader, Panel, StatusBadge, Tabs,
} from '../components/erp';
import { formatMoney } from '../data/demoData';
import { useAuth } from '../context/AuthContext';

const adminTabs = ['Utilisateurs', 'Rôles & permissions', 'Journal système', 'Journal des ventes', 'Base de données'];
const PAGE_SIZE = 25;
const LOG_LIMIT = 1000;
const BACKUP_FORMAT = 'korgo-pro-supabase-backup';
const RESTORE_CONFIRMATION = 'REMPLACER TOUTES LES ENTREPRISES';
const roleDescriptions = {
  ADMIN: 'Administration complète de l’entreprise',
  GESTIONNAIRE: 'Gestion des ventes, stocks, trésorerie et rapports',
  SUPERVISEUR: 'Consultation et contrôle des opérations',
  ASSISTANT: 'Ventes, pro formas et gestion des clients',
  CAISSIER: 'Caisse, pro formas, trésorerie et clients',
};
const roles = Object.keys(roleDescriptions);
const editableRoles = roles.filter((role) => role !== 'ADMIN');
const protectedPermissions = new Set(['manage_users', 'manage_database']);
const permissionLabels = {
  view_dashboard: 'Tableau de bord',
  view_sales: 'Consulter les ventes',
  create_sales: 'Encaisser (caisse)',
  cancel_sales: 'Annuler une vente',
  view_invoice_register: 'Registre des factures',
  manage_proformas: 'Devis / proformas',
  view_stock: 'Consulter le stock',
  manage_stock: 'Gérer le stock',
  manage_stores: 'Gérer les magasins',
  view_treasury: 'Consulter la trésorerie',
  manage_treasury: 'Gérer la trésorerie',
  manage_customers: 'Gérer les clients',
  view_reports: 'Rapports et statistiques',
  access_admin: 'Administration',
  manage_users: 'Gérer les utilisateurs',
  manage_database: 'Base de données',
  manage_settings: 'Paramètres',
  export_data: 'Export de données',
  view_audit_logs: 'Journaux d’audit',
  apply_discount: 'Appliquer une remise',
};

function matchesDateRange(value, from, to) {
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return !from && !to;
  const start = from ? new Date(`${from}T00:00:00`).getTime() : -Infinity;
  const end = to ? new Date(`${to}T23:59:59.999`).getTime() : Infinity;
  return timestamp >= start && timestamp <= end;
}

function PageNavigation({ page, rowCount, onChange }) {
  const pageCount = Math.max(1, Math.ceil(rowCount / PAGE_SIZE));
  const first = rowCount ? page * PAGE_SIZE + 1 : 0;
  const last = Math.min((page + 1) * PAGE_SIZE, rowCount);
  return (
    <div className="erp-pagination">
      <span>{first}–{last} sur {rowCount}</span>
      <button type="button" className="erp-button erp-button-secondary" disabled={page === 0} onClick={() => onChange(page - 1)}>Précédent</button>
      <span>Page {page + 1}/{pageCount}</span>
      <button type="button" className="erp-button erp-button-secondary" disabled={page + 1 >= pageCount} onClick={() => onChange(page + 1)}>Suivant</button>
    </div>
  );
}

function toCsvCell(value) {
  return `"${String(value ?? '').replaceAll('"', '""')}"`;
}

function downloadJson(data, filename) {
  const url = URL.createObjectURL(new Blob(
    [JSON.stringify(data, null, 2)],
    { type: 'application/json;charset=utf-8' },
  ));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function backupRowCount(backup) {
  return Object.values(backup?.tables || {}).reduce(
    (total, rows) => total + (Array.isArray(rows) ? rows.length : 0),
    0,
  );
}

function displayDatabaseValue(value) {
  if (value == null) return '';
  return typeof value === 'object' ? JSON.stringify(value) : String(value);
}

function membershipStatus(member) {
  if (member.profile_active === false) return 'Profil inactif';
  return (member.member_active ?? member.active) ? 'Actif' : 'Suspendu';
}

export default function Admin() {
  const { organizationId, selectedOrganization, settings, user: currentUser } = useAuth();
  const organizationPermissions = selectedOrganization?.permissions || [];
  const canManageUsers = organizationPermissions.includes('manage_users');
  const canViewAuditLogs = organizationPermissions.includes('view_audit_logs');
  const canManageDatabase = organizationPermissions.includes('manage_database');
  const load = useCallback(async () => {
    const [users, logs] = await Promise.all([
      listOrganizationMembers(organizationId),
      canViewAuditLogs
        ? Promise.all([
          listActivityLogs(organizationId, LOG_LIMIT),
          listSaleLogs(organizationId, LOG_LIMIT),
        ])
        : Promise.resolve([[], []]),
    ]);
    const [activity, sales] = logs;
    return {
      users: users.map((member) => ({
        ...member,
        name: member.username || member.email,
        status: membershipStatus(member),
        lastSeen: member.last_login ? new Date(member.last_login).toLocaleString('fr-FR') : 'Jamais',
      })),
      activity,
      sales,
    };
  }, [canViewAuditLogs, organizationId]);
  const { data, loading, error: loadError, refresh } = useBusinessData(load);
  const [tab, setTab] = useState(adminTabs[0]);
  const [query, setQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('Tous');
  const [statusFilter, setStatusFilter] = useState('Tous');
  const [memberPage, setMemberPage] = useState(0);
  const [activityQuery, setActivityQuery] = useState('');
  const [activityAction, setActivityAction] = useState('Tous');
  const [activityFrom, setActivityFrom] = useState('');
  const [activityTo, setActivityTo] = useState('');
  const [activityPage, setActivityPage] = useState(0);
  const [saleQuery, setSaleQuery] = useState('');
  const [saleAction, setSaleAction] = useState('Tous');
  const [saleFrom, setSaleFrom] = useState('');
  const [saleTo, setSaleTo] = useState('');
  const [salePage, setSalePage] = useState(0);
  const [showUser, setShowUser] = useState(false);
  const [showInvite, setShowInvite] = useState(false);
  const [editingMember, setEditingMember] = useState(null);
  const [memberDraft, setMemberDraft] = useState({ role: 'CAISSIER', active: true });
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);
  const [newUser, setNewUser] = useState({ email: '', role: 'CAISSIER' });
  const [inviteDraft, setInviteDraft] = useState({ email: '', username: '', role: 'CAISSIER' });
  const [memberActionBusy, setMemberActionBusy] = useState('');
  const [permissionRows, setPermissionRows] = useState([]);
  const [permissionBaseline, setPermissionBaseline] = useState('');
  const [permissionsLoading, setPermissionsLoading] = useState(false);
  const [permissionsError, setPermissionsError] = useState('');
  const [permissionsSaving, setPermissionsSaving] = useState(false);
  const [permissionNotice, setPermissionNotice] = useState('');
  const [showCleanupConfirm, setShowCleanupConfirm] = useState(false);
  const [cleanupError, setCleanupError] = useState('');
  const restoreFileRef = useRef(null);
  const [globalDatabaseAccess, setGlobalDatabaseAccess] = useState(false);
  const [globalDatabaseLoading, setGlobalDatabaseLoading] = useState(false);
  const [globalDatabaseError, setGlobalDatabaseError] = useState('');
  const [databaseError, setDatabaseError] = useState('');
  const [databaseNotice, setDatabaseNotice] = useState('');
  const [databaseBusy, setDatabaseBusy] = useState('');
  const [selectedBackup, setSelectedBackup] = useState(null);
  const [showRestoreConfirm, setShowRestoreConfirm] = useState(false);
  const [safetyBackupDownloaded, setSafetyBackupDownloaded] = useState(false);
  const [safetyBackupConfirmed, setSafetyBackupConfirmed] = useState(false);
  const [restorePhrase, setRestorePhrase] = useState('');
  const [databaseTables, setDatabaseTables] = useState([]);
  const [databaseTableName, setDatabaseTableName] = useState('');
  const [databaseTableRows, setDatabaseTableRows] = useState([]);
  const [databaseTableOffset, setDatabaseTableOffset] = useState(0);
  const [databaseTableHasMore, setDatabaseTableHasMore] = useState(false);
  const [databaseTableLoaded, setDatabaseTableLoaded] = useState(false);
  const [databaseTableLimit, setDatabaseTableLimit] = useState(100);
  const [databaseTableLoading, setDatabaseTableLoading] = useState(false);
  const [databaseTableError, setDatabaseTableError] = useState('');
  const [databaseTablesLoading, setDatabaseTablesLoading] = useState(false);
  const [databaseTablesError, setDatabaseTablesError] = useState('');

  const users = data?.users || [];
  const visibleUsers = useMemo(() => users.filter((member) => (
    (roleFilter === 'Tous' || member.role === roleFilter)
    && (statusFilter === 'Tous' || member.status === statusFilter)
    && `${member.name} ${member.email} ${member.role}`.toLowerCase().includes(query.toLowerCase())
  )), [query, roleFilter, statusFilter, users]);
  const memberPageRows = visibleUsers.slice(memberPage * PAGE_SIZE, (memberPage + 1) * PAGE_SIZE);
  const databaseTableColumns = useMemo(() => (
    databaseTableRows.length
      ? Object.keys(databaseTableRows[0]).map((key) => ({
        key,
        label: key,
        render: (value) => displayDatabaseValue(value),
      }))
      : []
  ), [databaseTableRows]);
  const canExport = organizationPermissions.includes('export_data');

  useEffect(() => {
    if (tab !== 'Base de données') return undefined;
    let active = true;
    setGlobalDatabaseLoading(true);
    setGlobalDatabaseAccess(false);
    setGlobalDatabaseError('');
    canManageAllDatabase()
      .then((allowed) => {
        if (active) setGlobalDatabaseAccess(allowed);
      })
      .catch((failure) => {
        if (active) {
          setGlobalDatabaseAccess(false);
          setGlobalDatabaseError(failure.message || 'Impossible de vérifier les droits globaux.');
        }
      })
      .finally(() => {
        if (active) setGlobalDatabaseLoading(false);
      });
    return () => {
      active = false;
    };
  }, [organizationId, tab]);

  useEffect(() => {
    if (tab !== 'Rôles & permissions') return undefined;
    let active = true;
    setPermissionsLoading(true);
    setPermissionRows([]);
    setPermissionBaseline('');
    setPermissionNotice('');
    setPermissionsError('');
    (canManageUsers ? listOrganizationRolePermissions(organizationId) : Promise.resolve([]))
      .then((rows) => {
        if (!active) return;
        setPermissionRows(rows);
        setPermissionBaseline(JSON.stringify(rows));
      })
      .catch((failure) => {
        if (active) setPermissionsError(failure.message || 'Impossible de charger les permissions.');
      })
      .finally(() => {
        if (active) setPermissionsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [canManageUsers, organizationId, tab]);

  useEffect(() => {
    if (tab !== 'Base de données' || !canManageDatabase) return undefined;
    let active = true;
    setDatabaseTablesLoading(true);
    setDatabaseTables([]);
    setDatabaseTableName('');
    setDatabaseTableRows([]);
    setDatabaseTableOffset(0);
    setDatabaseTableHasMore(false);
    setDatabaseTableLoaded(false);
    setDatabaseTablesError('');
    listOrganizationDatabaseTables(organizationId)
      .then((tables) => {
        if (!active) return;
        setDatabaseTables(tables);
        setDatabaseTableName((current) => tables.includes(current) ? current : (tables[0] || ''));
        setDatabaseTableRows([]);
        setDatabaseTableOffset(0);
        setDatabaseTableHasMore(false);
        setDatabaseTableLoaded(false);
      })
      .catch((failure) => {
        if (active) setDatabaseTablesError(failure.message || 'Impossible de lister les tables métier.');
      })
      .finally(() => {
        if (active) setDatabaseTablesLoading(false);
      });
    return () => {
      active = false;
    };
  }, [canManageDatabase, organizationId, tab]);

  const refreshAdminData = async (successMessage = '') => {
    setNotice('');
    try {
      await refresh();
      if (successMessage) setNotice(successMessage);
    } catch (failure) {
      setNotice(successMessage
        ? `${successMessage} Actualisation impossible : ${failure.message || 'erreur Supabase.'}`
        : `Actualisation impossible : ${failure.message || 'erreur Supabase.'}`);
    }
  };

  const activityRows = useMemo(() => (data?.activity || []).map((row) => ({
    ...row,
    date: row.created_at ? new Date(row.created_at).toLocaleString('fr-FR') : '—',
    user: row.username || 'Système',
    result: 'Enregistré',
  })), [data?.activity]);
  const filteredActivityRows = useMemo(() => activityRows.filter((row) => (
    (activityAction === 'Tous' || row.action === activityAction)
    && `${row.user} ${row.action}`.toLowerCase().includes(activityQuery.toLowerCase())
    && matchesDateRange(row.created_at, activityFrom, activityTo)
  )), [activityAction, activityFrom, activityQuery, activityRows, activityTo]);
  const activityPageRows = filteredActivityRows.slice(activityPage * PAGE_SIZE, (activityPage + 1) * PAGE_SIZE);
  const activityActions = [...new Set(activityRows.map((row) => row.action).filter(Boolean))].sort();

  const saleRows = useMemo(() => (data?.sales || []).map((row) => ({
    ...row,
    date: row.created_at ? new Date(row.created_at).toLocaleString('fr-FR') : '—',
    customer: row.customer_name || 'Client de passage',
    amount: Number(row.total_amount) || 0,
    status: row.action,
  })), [data?.sales]);
  const filteredSaleRows = useMemo(() => saleRows.filter((row) => (
    (saleAction === 'Tous' || row.action === saleAction)
    && `${row.sale_number} ${row.customer} ${row.username} ${row.action}`.toLowerCase().includes(saleQuery.toLowerCase())
    && matchesDateRange(row.created_at, saleFrom, saleTo)
  )), [saleAction, saleFrom, saleQuery, saleRows, saleTo]);
  const salePageRows = filteredSaleRows.slice(salePage * PAGE_SIZE, (salePage + 1) * PAGE_SIZE);
  const saleActions = [...new Set(saleRows.map((row) => row.action).filter(Boolean))].sort();

  const openMemberEditor = (member) => {
    setNotice('');
    setEditingMember(member);
    setMemberDraft({
      role: member.role,
      active: Boolean(member.member_active ?? member.active),
    });
  };

  const saveMember = async (event) => {
    event.preventDefault();
    if (!editingMember) return;
    setSaving(true);
    setNotice('');
    try {
      const result = await updateOrganizationMember(
        organizationId, editingMember.email, memberDraft.role, memberDraft.active,
      );
      setEditingMember(null);
      setMemberPage(0);
      await refreshAdminData(result.message || 'Membre mis à jour.');
    } catch (failure) {
      setNotice(failure.message || 'Le membre n’a pas pu être mis à jour.');
    } finally {
      setSaving(false);
    }
  };

  const addUser = async (event) => {
    event.preventDefault();
    setSaving(true);
    setNotice('');
    try {
      const result = await addOrganizationMember(organizationId, newUser.email, newUser.role);
      setShowUser(false);
      setNewUser({ email: '', role: 'CAISSIER' });
      setMemberPage(0);
      await refreshAdminData(result.message || 'Membre ajouté à l’entreprise.');
    } catch (failure) {
      setNotice(failure.message || 'Le membre n’a pas pu être ajouté.');
    } finally {
      setSaving(false);
    }
  };

  const inviteUser = async (event) => {
    event.preventDefault();
    setSaving(true);
    setNotice('');
    try {
      const result = await inviteOrganizationMember(
        organizationId, inviteDraft.email, inviteDraft.username, inviteDraft.role,
      );
      setShowInvite(false);
      setInviteDraft({ email: '', username: '', role: 'CAISSIER' });
      setMemberPage(0);
      await refreshAdminData(result.message || 'Invitation envoyée.');
    } catch (failure) {
      setNotice(failure.message || 'L’invitation n’a pas pu être envoyée.');
    } finally {
      setSaving(false);
    }
  };

  const resetMemberPassword = async (member) => {
    if (!window.confirm(`Envoyer un lien de réinitialisation à ${member.email} ?`)) return;
    setMemberActionBusy(member.email);
    setNotice('');
    try {
      const result = await sendOrganizationMemberPasswordReset(organizationId, member.email);
      setNotice(result.message || 'Courriel de réinitialisation envoyé.');
    } catch (failure) {
      setNotice(failure.message || 'Le courriel de réinitialisation n’a pas pu être envoyé.');
    } finally {
      setMemberActionBusy('');
    }
  };

  const removeMember = async (member) => {
    if (!window.confirm(
      `Retirer ${member.email} de ${selectedOrganization?.name || 'cette entreprise'} ?\n\n`
      + 'Son compte Supabase Auth et ses accès aux autres entreprises seront conservés.',
    )) return;
    setMemberActionBusy(member.email);
    setNotice('');
    try {
      const result = await removeOrganizationMember(organizationId, member.email);
      setMemberPage(0);
      await refreshAdminData(result.message || 'Accès retiré de cette entreprise.');
    } catch (failure) {
      setNotice(failure.message || 'Le membre n’a pas pu être retiré.');
    } finally {
      setMemberActionBusy('');
    }
  };

  const updatePermission = (permission, role, enabled) => {
    setPermissionRows((rows) => rows.map((row) => (
      row.permission === permission ? { ...row, [role]: enabled } : row
    )));
    setPermissionNotice('');
  };

  const savePermissions = async () => {
    const permissions = permissionRows.flatMap((row) => editableRoles.map((role) => ({
      role,
      permission: row.permission,
      enabled: Boolean(row[role]),
    })));
    setPermissionsSaving(true);
    setPermissionsError('');
    setPermissionNotice('');
    try {
      const result = await saveOrganizationRolePermissions(organizationId, permissions);
      const current = await listOrganizationRolePermissions(organizationId);
      setPermissionRows(current);
      setPermissionBaseline(JSON.stringify(current));
      setPermissionNotice(result.message || 'Permissions enregistrées.');
      await refreshAdminData();
    } catch (failure) {
      setPermissionsError(failure.message || 'Les permissions n’ont pas pu être enregistrées.');
    } finally {
      setPermissionsSaving(false);
    }
  };

  const resetPermissions = async () => {
    if (!window.confirm('Réinitialiser les permissions de cette entreprise aux valeurs par défaut ?')) return;
    setPermissionsSaving(true);
    setPermissionsError('');
    setPermissionNotice('');
    try {
      const result = await resetOrganizationRolePermissions(organizationId);
      const current = await listOrganizationRolePermissions(organizationId);
      setPermissionRows(current);
      setPermissionBaseline(JSON.stringify(current));
      setPermissionNotice(result.message || 'Permissions réinitialisées.');
      await refreshAdminData();
    } catch (failure) {
      setPermissionsError(failure.message || 'Les permissions n’ont pas pu être réinitialisées.');
    } finally {
      setPermissionsSaving(false);
    }
  };

  const loadDatabaseTable = async (offset = 0, append = false) => {
    if (!databaseTableName) return;
    setDatabaseTableLoading(true);
    setDatabaseTableError('');
    try {
      const rows = await readOrganizationDatabaseTable(
        organizationId, databaseTableName, databaseTableLimit, offset,
      );
      setDatabaseTableRows((current) => append ? [...current, ...rows] : rows);
      setDatabaseTableOffset(offset + rows.length);
      setDatabaseTableHasMore(rows.length === databaseTableLimit);
      setDatabaseTableLoaded(true);
    } catch (failure) {
      setDatabaseTableError(failure.message || 'Impossible de charger cette table.');
    } finally {
      setDatabaseTableLoading(false);
    }
  };

  const cleanupOldLogs = async () => {
    setMemberActionBusy('cleanup');
    setCleanupError('');
    setNotice('');
    try {
      const result = await cleanupOrganizationActivityLogs(organizationId);
      setShowCleanupConfirm(false);
      await refreshAdminData(`Journaux nettoyés : ${result.deleted_count ?? 0} supprimé(s).`);
    } catch (failure) {
      setCleanupError(failure.message || 'Le nettoyage des journaux a échoué.');
    } finally {
      setMemberActionBusy('');
    }
  };

  const exportMembers = () => {
    const rows = [
      ['Utilisateur', 'Email', 'Rôle', 'Statut', 'Dernière activité'],
      ...visibleUsers.map((member) => [
        member.name, member.email, member.role, member.status, member.lastSeen,
      ]),
    ];
    const csv = `\uFEFF${rows.map((row) => row.map(toCsvCell).join(';')).join('\r\n')}`;
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `membres-${selectedOrganization?.code || 'entreprise'}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const exportAllData = async () => {
    setDatabaseError('');
    setDatabaseNotice('');
    setDatabaseBusy('export');
    try {
      const backup = await exportAllOrganizationsData();
      const filename = `korgo-sauvegarde-${new Date().toISOString().replaceAll(':', '-')}.json`;
      downloadJson(backup, filename);
      setDatabaseNotice(
        `Sauvegarde téléchargée : ${backup.organizations.length} entreprise(s), ${backupRowCount(backup)} ligne(s).`,
      );
    } catch (failure) {
      setDatabaseError(failure.message || 'La sauvegarde n’a pas pu être créée.');
    } finally {
      setDatabaseBusy('');
    }
  };

  const loadRestoreFile = async (event) => {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = '';
    if (!file) return;
    setDatabaseError('');
    setDatabaseNotice('');
    setSelectedBackup(null);
    try {
      const backup = JSON.parse(await file.text());
      if (
        backup?.format !== BACKUP_FORMAT
        || backup?.version !== 1
        || !Array.isArray(backup.organizations)
        || !backup.tables
        || typeof backup.tables !== 'object'
        || Array.isArray(backup.tables)
      ) {
        throw new Error('Ce fichier n’est pas une sauvegarde Supabase Korgo Pro valide.');
      }
      setSelectedBackup({ filename: file.name, data: backup });
    } catch (failure) {
      setDatabaseError(failure.message || 'Le fichier de sauvegarde est invalide.');
    }
  };

  const prepareRestore = () => {
    if (!selectedBackup) return;
    setDatabaseError('');
    setSafetyBackupDownloaded(false);
    setSafetyBackupConfirmed(false);
    setRestorePhrase('');
    setShowRestoreConfirm(true);
  };

  const downloadSafetyBackup = async () => {
    setDatabaseError('');
    setDatabaseBusy('safety');
    try {
      const backup = await exportAllOrganizationsData();
      const filename = `korgo-avant-restauration-${new Date().toISOString().replaceAll(':', '-')}.json`;
      downloadJson(backup, filename);
      setSafetyBackupDownloaded(true);
      setSafetyBackupConfirmed(false);
      setDatabaseNotice('La sauvegarde de sécurité a été téléchargée. Vérifiez le fichier avant de poursuivre.');
    } catch (failure) {
      setDatabaseError(failure.message || 'La sauvegarde de sécurité n’a pas pu être créée.');
    } finally {
      setDatabaseBusy('');
    }
  };

  const restoreAllData = async () => {
    if (!selectedBackup || !safetyBackupConfirmed || restorePhrase !== RESTORE_CONFIRMATION) return;
    setDatabaseError('');
    setDatabaseNotice('');
    setDatabaseBusy('restore');
    try {
      const result = await restoreAllOrganizationsData(selectedBackup.data);
      setDatabaseNotice(
        `${result.message || 'Restauration terminée.'} ${result.row_count ?? 0} ligne(s) restaurée(s).`,
      );
      setSelectedBackup(null);
      setShowRestoreConfirm(false);
      await refreshAdminData();
    } catch (failure) {
      setDatabaseError(failure.message || 'La restauration a échoué. Aucune modification partielle n’a été conservée.');
    } finally {
      setDatabaseBusy('');
    }
  };

  if (loading && !data) return <div className="erp-standalone" role="status">Chargement de l’administration…</div>;
  if (!data) return <InlineMessage tone="error">{loadError || 'Impossible de charger l’administration.'}</InlineMessage>;

  const noticeIsSuccess = !notice.includes('Actualisation impossible') && [
    'Membre ajouté', 'Membre mis à jour', 'Invitation', 'Courriel de réinitialisation',
    'Accès retiré', 'Journaux nettoyés',
  ].some((prefix) => notice.startsWith(prefix));
  const currentEmail = String(currentUser?.email || '').toLowerCase();

  return (
    <div className="erp-page">
      <PageHeader
        title="Administration"
        subtitle={`Accès et journaux de ${selectedOrganization?.name || 'l’entreprise active'}.`}
        action={<>
          {tab === 'Utilisateurs' && canManageUsers && <>
            <ActionButton variant="secondary" onClick={() => { setNotice(''); setShowUser(true); }}>Associer un compte existant</ActionButton>
            <ActionButton onClick={() => { setNotice(''); setShowInvite(true); }}>＋ Inviter un utilisateur</ActionButton>
          </>}
          <ActionButton variant="secondary" onClick={() => refreshAdminData()}>Rafraîchir</ActionButton>
        </>}
      />
      {loadError && <InlineMessage tone="error">{loadError}</InlineMessage>}
      {notice && <InlineMessage tone={noticeIsSuccess ? 'success' : 'error'}>{notice}</InlineMessage>}
      <div className="erp-admin-summary">
        <div><strong>{users.length}</strong><span>Membres</span></div>
        <div><strong>{users.filter((member) => member.status === 'Actif').length}</strong><span>Actifs</span></div>
        <div><strong>{new Set(users.map((member) => member.role)).size}</strong><span>Rôles présents</span></div>
        <div><strong>{activityRows.length + saleRows.length}</strong><span>Événements chargés</span></div>
      </div>
      <Panel className="erp-tab-panel">
        <Tabs items={adminTabs} value={tab} onChange={setTab} />
        {tab === 'Utilisateurs' && <>
          <div className="erp-list-toolbar">
            <input
              className="erp-control"
              placeholder="Rechercher un nom, email ou rôle…"
              value={query}
              onChange={(event) => { setQuery(event.target.value); setMemberPage(0); }}
            />
            <select className="erp-control" aria-label="Filtrer par rôle" value={roleFilter} onChange={(event) => { setRoleFilter(event.target.value); setMemberPage(0); }}>
              <option value="Tous">Tous les rôles</option>
              {roles.map((role) => <option key={role}>{role}</option>)}
            </select>
            <select className="erp-control" aria-label="Filtrer par statut" value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value); setMemberPage(0); }}>
              {['Tous', 'Actif', 'Suspendu', 'Profil inactif'].map((status) => <option key={status}>{status}</option>)}
            </select>
            {canExport && <ActionButton variant="secondary" onClick={exportMembers}>Exporter CSV</ActionButton>}
            <span className="erp-toolbar-count">{visibleUsers.length} membre(s)</span>
          </div>
          <DataTable columns={[
            { key: 'name', label: 'Utilisateur', render: (name, member) => <span className="erp-person"><span className="erp-avatar">{(name || 'U')[0].toUpperCase()}</span><span><strong>{name}</strong><small>{member.email}</small></span></span> },
            { key: 'role', label: 'Rôle', render: (value) => <StatusBadge>{value}</StatusBadge> },
            { key: 'status', label: 'Statut', render: (value) => <StatusBadge>{value}</StatusBadge> },
            { key: 'lastSeen', label: 'Dernière activité' },
            {
              key: 'action',
              label: '',
              render: (_, member) => {
                const isCurrentUser = String(member.email || '').toLowerCase() === currentEmail;
                return canManageUsers
                  ? <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    <button className="erp-table-action" type="button" disabled={isCurrentUser || memberActionBusy === member.email} onClick={() => openMemberEditor(member)}>Modifier</button>
                    <button className="erp-table-action" type="button" disabled={isCurrentUser || memberActionBusy === member.email || !member.member_active || member.profile_active === false} onClick={() => resetMemberPassword(member)}>Réinitialiser</button>
                    <button className="erp-table-action erp-text-danger" type="button" disabled={isCurrentUser || memberActionBusy === member.email} onClick={() => removeMember(member)}>Retirer</button>
                  </div>
                  : <span className="erp-table-dash">—</span>;
              },
            },
          ]} rows={memberPageRows} />
          <PageNavigation page={memberPage} rowCount={visibleUsers.length} onChange={setMemberPage} />
        </>}
        {tab === 'Rôles & permissions' && <>
          <div className="erp-panel-intro">
            <h3>Permissions par rôle — {selectedOrganization?.name}</h3>
            <p>
              Les changements s’appliquent uniquement à cette entreprise et sont vérifiés par Supabase.
              ADMIN conserve tous les droits; gérer les utilisateurs et la base reste réservé à ADMIN.
            </p>
          </div>
          {permissionsError && <InlineMessage tone="danger">{permissionsError}</InlineMessage>}
          {permissionNotice && <InlineMessage tone="success">{permissionNotice}</InlineMessage>}
          {permissionsLoading && <InlineMessage>Chargement de la matrice…</InlineMessage>}
          {!canManageUsers && <InlineMessage>Seul un administrateur peut modifier la matrice des permissions.</InlineMessage>}
          {permissionRows.length > 0 && <>
            <div className="erp-list-toolbar">
              <ActionButton
                variant="secondary"
                onClick={resetPermissions}
                disabled={!canManageUsers || permissionsLoading || permissionsSaving}
              >
                Réinitialiser aux valeurs par défaut
              </ActionButton>
              <ActionButton
                onClick={savePermissions}
                disabled={
                  !canManageUsers
                  || permissionsLoading
                  || permissionsSaving
                  || permissionBaseline === JSON.stringify(permissionRows)
                }
              >
                {permissionsSaving ? 'Enregistrement…' : 'Enregistrer les permissions'}
              </ActionButton>
            </div>
            <DataTable
              columns={[
                { key: 'label', label: 'Permission' },
                ...roles.map((role) => ({
                  key: role,
                  label: role,
                  render: (enabled, row) => <input
                    type="checkbox"
                    aria-label={`${role} — ${row.label}`}
                    checked={Boolean(enabled)}
                    disabled={
                      !canManageUsers
                      || permissionsLoading
                      || permissionsSaving
                      || role === 'ADMIN'
                      || protectedPermissions.has(row.permission)
                    }
                    onChange={(event) => updatePermission(row.permission, role, event.target.checked)}
                  />,
                })),
              ]}
              rows={permissionRows.map((row) => ({
                ...row,
                id: row.permission,
                label: permissionLabels[row.permission] || row.permission,
              }))}
            />
          </>}
          <div className="erp-panel-intro"><h3>Rôles de l’entreprise</h3></div>
          <DataTable columns={[
            { key: 'role', label: 'Rôle' },
            { key: 'count', label: 'Membres', render: (_, row) => users.filter((member) => member.role === row.role).length },
            { key: 'description', label: 'Description' },
          ]} rows={roles.map((role) => ({ id: role, role, description: roleDescriptions[role] }))} />
        </>}
        {tab === 'Journal système' && <>
          {!canViewAuditLogs && <InlineMessage>La permission « Journaux d’audit » est nécessaire pour consulter ce journal.</InlineMessage>}
          <div className="erp-list-toolbar">
            <input className="erp-control" placeholder="Rechercher un utilisateur ou une action…" value={activityQuery} onChange={(event) => { setActivityQuery(event.target.value); setActivityPage(0); }} />
            <select className="erp-control" aria-label="Filtrer les actions système" value={activityAction} onChange={(event) => { setActivityAction(event.target.value); setActivityPage(0); }}>
              <option value="Tous">Toutes les actions</option>
              {activityActions.map((action) => <option key={action}>{action}</option>)}
            </select>
            <label className="erp-field"><span>Du</span><input type="date" value={activityFrom} onChange={(event) => { setActivityFrom(event.target.value); setActivityPage(0); }} /></label>
            <label className="erp-field"><span>Au</span><input type="date" value={activityTo} onChange={(event) => { setActivityTo(event.target.value); setActivityPage(0); }} /></label>
            {canManageDatabase && <ActionButton variant="danger" onClick={() => { setCleanupError(''); setShowCleanupConfirm(true); }}>Nettoyer les journaux &gt; 30 jours</ActionButton>}
          </div>
          <DataTable columns={[
            { key: 'date', label: 'Date' }, { key: 'user', label: 'Utilisateur' }, { key: 'action', label: 'Action' },
            { key: 'result', label: 'Résultat', render: (value) => <StatusBadge>{value}</StatusBadge> },
          ]} rows={activityPageRows} />
          <PageNavigation page={activityPage} rowCount={filteredActivityRows.length} onChange={setActivityPage} />
          <p className="erp-helper">Recherche parmi les {LOG_LIMIT} événements les plus récents chargés.</p>
        </>}
        {tab === 'Journal des ventes' && <>
          {!canViewAuditLogs && <InlineMessage>La permission « Journaux d’audit » est nécessaire pour consulter ce journal.</InlineMessage>}
          <div className="erp-list-toolbar">
            <input className="erp-control" placeholder="N° vente, client, utilisateur ou action…" value={saleQuery} onChange={(event) => { setSaleQuery(event.target.value); setSalePage(0); }} />
            <select className="erp-control" aria-label="Filtrer les actions de vente" value={saleAction} onChange={(event) => { setSaleAction(event.target.value); setSalePage(0); }}>
              <option value="Tous">Toutes les actions</option>
              {saleActions.map((action) => <option key={action}>{action}</option>)}
            </select>
            <label className="erp-field"><span>Du</span><input type="date" value={saleFrom} onChange={(event) => { setSaleFrom(event.target.value); setSalePage(0); }} /></label>
            <label className="erp-field"><span>Au</span><input type="date" value={saleTo} onChange={(event) => { setSaleTo(event.target.value); setSalePage(0); }} /></label>
          </div>
          <DataTable columns={[
            { key: 'sale_number', label: 'N° Vente' }, { key: 'date', label: 'Date' }, { key: 'customer', label: 'Client' },
            { key: 'amount', label: 'Montant', render: (value) => formatMoney(value, settings.currency) }, { key: 'status', label: 'Action', render: (value) => <StatusBadge>{value}</StatusBadge> },
          ]} rows={salePageRows} />
          <PageNavigation page={salePage} rowCount={filteredSaleRows.length} onChange={setSalePage} />
          <p className="erp-helper">Recherche parmi les {LOG_LIMIT} événements les plus récents chargés.</p>
        </>}
        {tab === 'Base de données' && <>
          {databaseError && <InlineMessage tone="danger">{databaseError}</InlineMessage>}
          {databaseNotice && <InlineMessage tone="success">{databaseNotice}</InlineMessage>}
          {globalDatabaseLoading && <InlineMessage>Vérification des droits d’administration globale…</InlineMessage>}
          {globalDatabaseError && <InlineMessage tone="danger">
            {globalDatabaseError} Vérifiez que les fonctions de sauvegarde sont déployées depuis
            {' '}supabase_tauri_business.sql.
          </InlineMessage>}
          {!globalDatabaseLoading && !globalDatabaseError && !globalDatabaseAccess && (
            <InlineMessage tone="danger">
              La sauvegarde et la restauration globales exigent un rôle ADMIN actif dans chaque entreprise du projet.
            </InlineMessage>
          )}
          {globalDatabaseAccess && <>
            <div className="erp-database-note">
              <span>✓</span>
              <div>
                <strong>Sauvegarde globale Supabase</strong>
                <p>
                  Le fichier inclut les données métier de toutes les entreprises, actives ou non.
                  Seuls les identifiants, codes, noms et statuts d’entreprise sont inclus pour vérifier le projet cible.
                  Les comptes Auth, profils, appartenances, fiches complètes d’entreprise et journaux système ne sont pas remplacés.
                </p>
                <p>
                  L’export et la restauration verrouillent temporairement les écritures métier pour garantir
                  un fichier cohérent. La restauration remplace les données métier de toutes les entreprises.
                </p>
              </div>
            </div>
            <div className="erp-list-toolbar">
              <ActionButton onClick={exportAllData} disabled={Boolean(databaseBusy)}>
                {databaseBusy === 'export' ? 'Création…' : 'Télécharger une sauvegarde'}
              </ActionButton>
              <input
                ref={restoreFileRef}
                type="file"
                accept="application/json,.json"
                hidden
                onChange={loadRestoreFile}
              />
              <ActionButton
                variant="secondary"
                onClick={() => restoreFileRef.current?.click()}
                disabled={Boolean(databaseBusy)}
              >
                Choisir une sauvegarde à restaurer
              </ActionButton>
              {selectedBackup && (
                <span className="erp-toolbar-count">
                  {selectedBackup.filename} · {selectedBackup.data.organizations.length} entreprise(s) · {backupRowCount(selectedBackup.data)} ligne(s)
                </span>
              )}
              {selectedBackup && (
                <ActionButton
                  variant="danger"
                  onClick={prepareRestore}
                  disabled={Boolean(databaseBusy)}
                >
                  Préparer la restauration
                </ActionButton>
              )}
            </div>
          </>}
          {canManageDatabase ? <>
            <div className="erp-panel-intro">
              <h3>Explorer les données de l’entreprise active</h3>
              <p>Consultation en lecture seule des tables autorisées, limitée à l’entreprise active et à 200 lignes par page. Les requêtes SQL libres ne sont pas disponibles.</p>
            </div>
            {databaseTablesError && <InlineMessage tone="danger">{databaseTablesError}</InlineMessage>}
            {databaseTableError && <InlineMessage tone="danger">{databaseTableError}</InlineMessage>}
            {databaseTablesLoading
              ? <InlineMessage>Chargement des tables autorisées…</InlineMessage>
              : databaseTables.length > 0 && <div className="erp-list-toolbar">
                <select
                  className="erp-control"
                  aria-label="Table métier à consulter"
                  value={databaseTableName}
                  onChange={(event) => {
                    setDatabaseTableName(event.target.value);
                    setDatabaseTableRows([]);
                    setDatabaseTableOffset(0);
                    setDatabaseTableHasMore(false);
                    setDatabaseTableLoaded(false);
                    setDatabaseTableError('');
                  }}
                >
                  {databaseTables.map((table) => <option key={table} value={table}>{table}</option>)}
                </select>
                <select
                  className="erp-control"
                  aria-label="Nombre de lignes par page"
                  value={databaseTableLimit}
                  onChange={(event) => {
                    setDatabaseTableLimit(Number(event.target.value));
                    setDatabaseTableRows([]);
                    setDatabaseTableOffset(0);
                    setDatabaseTableHasMore(false);
                    setDatabaseTableLoaded(false);
                  }}
                >
                  {[50, 100, 200].map((limit) => <option key={limit} value={limit}>{limit} lignes</option>)}
                </select>
                <ActionButton
                  onClick={() => loadDatabaseTable(0)}
                  disabled={databaseTableLoading || !databaseTableName}
                >
                  {databaseTableLoading ? 'Chargement…' : 'Charger la table'}
                </ActionButton>
                <span className="erp-toolbar-count">{databaseTableRows.length} ligne(s) chargée(s)</span>
              </div>}
            {!databaseTablesLoading && !databaseTablesError && databaseTables.length === 0 && <InlineMessage>Aucune table métier autorisée pour cette entreprise.</InlineMessage>}
            {databaseTableLoaded && databaseTableRows.length > 0 && <DataTable
              columns={databaseTableColumns}
              rows={databaseTableRows.map((row, index) => ({ ...row, id: row.id || `${databaseTableOffset}-${index}` }))}
            />}
            {databaseTableLoaded && databaseTableRows.length === 0 && <InlineMessage>Aucune ligne trouvée pour cette table.</InlineMessage>}
            {databaseTableHasMore && <div className="erp-list-toolbar">
              <ActionButton
                variant="secondary"
                onClick={() => loadDatabaseTable(databaseTableOffset, true)}
                disabled={databaseTableLoading}
              >
                {databaseTableLoading ? 'Chargement…' : 'Charger la page suivante'}
              </ActionButton>
            </div>}
          </> : <InlineMessage>La consultation des tables nécessite le droit Base de données dans l’entreprise active.</InlineMessage>}
        </>}
      </Panel>
      {showUser && <Modal title="Associer un membre existant" onClose={() => setShowUser(false)} footer={<><ActionButton variant="secondary" onClick={() => setShowUser(false)}>Annuler</ActionButton><ActionButton onClick={() => document.getElementById('user-form').requestSubmit()} disabled={saving}>{saving ? 'Enregistrement…' : 'Associer'}</ActionButton></>}>
        <form id="user-form" className="erp-form-grid" onSubmit={addUser}>
          <label className="erp-field erp-field-span"><span>Adresse e-mail du compte Supabase existant</span><input type="email" value={newUser.email} onChange={(event) => setNewUser({ ...newUser, email: event.target.value })} required /></label>
          <label className="erp-field erp-field-span"><span>Rôle dans cette entreprise</span><select value={newUser.role} onChange={(event) => setNewUser({ ...newUser, role: event.target.value })}>{roles.map((role) => <option key={role}>{role}</option>)}</select></label>
          <p className="erp-field-span erp-helper">Cette action associe un compte Auth existant. Elle ne crée pas de compte et ne transmet aucun mot de passe.</p>
        </form>
      </Modal>}
      {showInvite && <Modal title="Inviter un utilisateur" onClose={() => { if (!saving) setShowInvite(false); }} footer={<><ActionButton variant="secondary" onClick={() => setShowInvite(false)} disabled={saving}>Annuler</ActionButton><ActionButton onClick={() => document.getElementById('invite-form').requestSubmit()} disabled={saving}>{saving ? 'Envoi…' : 'Envoyer l’invitation'}</ActionButton></>}>
        <form id="invite-form" className="erp-form-grid" onSubmit={inviteUser}>
          <label className="erp-field erp-field-span"><span>Adresse e-mail</span><input type="email" autoComplete="email" value={inviteDraft.email} onChange={(event) => setInviteDraft({ ...inviteDraft, email: event.target.value })} required /></label>
          <label className="erp-field erp-field-span"><span>Nom d’utilisateur</span><input value={inviteDraft.username} onChange={(event) => setInviteDraft({ ...inviteDraft, username: event.target.value })} required /></label>
          <label className="erp-field erp-field-span"><span>Rôle dans cette entreprise</span><select value={inviteDraft.role} onChange={(event) => setInviteDraft({ ...inviteDraft, role: event.target.value })}>{editableRoles.map((role) => <option key={role}>{role}</option>)}</select></label>
          <p className="erp-field-span erp-helper">Supabase enverra un courriel d’invitation. Aucun mot de passe n’est créé ou communiqué dans l’application.</p>
        </form>
      </Modal>}
      {editingMember && <Modal title={`Modifier ${editingMember.name}`} onClose={() => setEditingMember(null)} footer={<><ActionButton variant="secondary" onClick={() => setEditingMember(null)}>Annuler</ActionButton><ActionButton onClick={() => document.getElementById('member-form').requestSubmit()} disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</ActionButton></>}>
        <form id="member-form" className="erp-form-grid" onSubmit={saveMember}>
          <p className="erp-field-span erp-modal-copy">{editingMember.email}</p>
          <label className="erp-field erp-field-span"><span>Rôle dans cette entreprise</span><select value={memberDraft.role} onChange={(event) => setMemberDraft({ ...memberDraft, role: event.target.value })}>{roles.map((role) => <option key={role}>{role}</option>)}</select></label>
          <label className="erp-field erp-field-span">
            <span>Accès à l’entreprise</span>
            <span><input type="checkbox" checked={memberDraft.active} disabled={editingMember.profile_active === false} onChange={(event) => setMemberDraft({ ...memberDraft, active: event.target.checked })} /> Membre actif</span>
          </label>
          {editingMember.profile_active === false && <p className="erp-field-span erp-helper">Le profil applicatif est inactif; réactivez-le dans le processus Auth avant de rétablir cet accès.</p>}
        </form>
      </Modal>}
      {showCleanupConfirm && <Modal
        title="Nettoyer les anciens journaux"
        onClose={() => { if (memberActionBusy !== 'cleanup') setShowCleanupConfirm(false); }}
        footer={<>
          <ActionButton variant="secondary" onClick={() => setShowCleanupConfirm(false)} disabled={memberActionBusy === 'cleanup'}>Annuler</ActionButton>
          <ActionButton variant="danger" onClick={cleanupOldLogs} disabled={memberActionBusy === 'cleanup'}>
            {memberActionBusy === 'cleanup' ? 'Nettoyage…' : 'Supprimer les journaux anciens'}
          </ActionButton>
        </>}
      >
        {cleanupError && <InlineMessage tone="danger">{cleanupError}</InlineMessage>}
        <InlineMessage tone="danger">
          Les journaux système de plus de 30 jours de l’entreprise active seront supprimés définitivement.
          Cette action ne touche pas aux journaux de vente ni aux autres entreprises.
        </InlineMessage>
      </Modal>}
      {showRestoreConfirm && selectedBackup && <Modal
        title="Confirmer le remplacement global"
        onClose={() => { if (databaseBusy !== 'restore') setShowRestoreConfirm(false); }}
        footer={<>
          <ActionButton variant="secondary" onClick={() => setShowRestoreConfirm(false)} disabled={databaseBusy === 'restore'}>Annuler</ActionButton>
          <ActionButton
            variant="danger"
            onClick={restoreAllData}
            disabled={
              databaseBusy !== ''
              || !safetyBackupConfirmed
              || restorePhrase !== RESTORE_CONFIRMATION
            }
          >
            {databaseBusy === 'restore' ? 'Restauration…' : 'Remplacer toutes les entreprises'}
          </ActionButton>
        </>}
      >
        {databaseError && <InlineMessage tone="danger">{databaseError}</InlineMessage>}
        <InlineMessage tone="danger">
          Cette opération remplace les données métier de toutes les entreprises. Les comptes, appartenances,
          fiches d’entreprise et journaux système resteront intacts. Le serveur vérifiera que le fichier provient
          du même ensemble d’entreprises et correspond au schéma actuel.
        </InlineMessage>
        <p className="erp-modal-copy">
          Fichier : {selectedBackup.filename}<br />
          Entreprises : {selectedBackup.data.organizations.length}<br />
          Lignes : {backupRowCount(selectedBackup.data)}
        </p>
        <div className="erp-form-grid">
          <ActionButton
            variant="secondary"
            onClick={downloadSafetyBackup}
            disabled={Boolean(databaseBusy)}
          >
            {databaseBusy === 'safety' ? 'Création de la sauvegarde…' : 'Télécharger une sauvegarde de sécurité'}
          </ActionButton>
          {safetyBackupDownloaded && <label className="erp-field erp-field-span">
            <span>
              <input
                type="checkbox"
                checked={safetyBackupConfirmed}
                onChange={(event) => setSafetyBackupConfirmed(event.target.checked)}
              /> J’ai vérifié que la sauvegarde de sécurité est bien téléchargée.
            </span>
          </label>}
          <label className="erp-field erp-field-span">
            <span>Pour confirmer, tapez : {RESTORE_CONFIRMATION}</span>
            <input
              value={restorePhrase}
              onChange={(event) => setRestorePhrase(event.target.value)}
              autoComplete="off"
              disabled={databaseBusy === 'restore'}
            />
          </label>
        </div>
      </Modal>}
    </div>
  );
}
