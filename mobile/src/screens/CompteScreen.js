import { useEffect, useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { mobileContext } from '../api/systemApi';
import {
  Badge,
  Banner,
  Btn,
  Card,
  ChipGroup,
  Field,
  Loading,
  SectionTitle,
} from '../components/ui';
import { config } from '../config';
import { useAuth } from '../context/AuthContext';
import { useStores } from '../context/StoreContext';
import { PERMISSIONS } from '../lib/permissions';
import { colors, sp } from '../theme';

/**
 * Écran Compte — identité, magasin actif, droits et diagnostic.
 *
 * Les droits sont affichés DEUX FOIS :
 *   * « calculés sur le téléphone » (src/lib/permissions.js, copie de
 *     core/permissions.py) : ils déterminent quels écrans sont visibles ;
 *   * « accordés par le serveur » (RPC app_mobile_context -> app_security.can) :
 *     ce sont eux qui décident réellement des écritures.
 * Un écart entre les deux indique que la matrice SQL doit être mise à jour.
 */
export default function CompteScreen() {
  const { user, roleLabel, permissions, signOut } = useAuth();
  const { stores, activeId, selectStore, refreshStores, loading } = useStores();
  const [server, setServer] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const ctx = await mobileContext();
        if (!cancelled) setServer(ctx);
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const serverPermissions = server?.permissions || null;
  const divergences = serverPermissions
    ? PERMISSIONS.filter(
        (key) => permissions.includes(key) !== serverPermissions.includes(key)
      )
    : [];

  const logout = async () => {
    setBusy(true);
    try {
      await signOut();
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Card>
        <SectionTitle right={<Badge text={roleLabel || user?.role || '—'} tone="info" />}>
          Mon compte
        </SectionTitle>
        <Text style={styles.name}>{user?.username || '—'}</Text>
        <Text style={styles.meta}>{user?.email || ''}</Text>
        <Text style={styles.meta}>Identifiant interne : #{user?.id ?? '—'}</Text>

        {user?.must_change_password ? (
          <Banner
            tone="warning"
            title="Mot de passe à changer"
            message="Ce compte doit changer son mot de passe depuis la version desktop ou web."
          />
        ) : null}

        <Btn
          title="Se déconnecter"
          variant="danger"
          onPress={logout}
          loading={busy}
          style={styles.fullBtn}
        />
      </Card>

      <Card>
        <SectionTitle
          right={
            <Btn
              variant="ghost"
              title="Rafraîchir"
              onPress={refreshStores}
              loading={loading}
              style={styles.smallBtn}
            />
          }
        >
          Magasin actif
        </SectionTitle>
        {stores.length === 0 ? (
          <Text style={styles.meta}>Aucun magasin disponible.</Text>
        ) : (
          <ChipGroup
            options={stores.map((s) => ({ value: s.id, label: s.name }))}
            value={activeId}
            onChange={selectStore}
          />
        )}
        <Text style={styles.hint}>
          Toutes les ventes, l'inventaire et les encaissements sont rattachés à ce magasin.
        </Text>
      </Card>

      {error ? <Banner tone="danger" title="Diagnostic indisponible" message={error} /> : null}

      <Card>
        <SectionTitle>Permissions</SectionTitle>
        {!server ? <Loading label="Lecture des droits serveur…" /> : null}
        {divergences.length > 0 ? (
          <Banner
            tone="warning"
            title="Matrice à synchroniser"
            message={
              `Écart détecté sur : ${divergences.join(', ')}. Mettez à jour ` +
              'supabase_mobile_rpc.sql (app_security.can) ET core/permissions.py.'
            }
          />
        ) : null}
        {PERMISSIONS.map((key) => {
          const local = permissions.includes(key);
          const remote = serverPermissions ? serverPermissions.includes(key) : null;
          return (
            <View key={key} style={styles.permRow}>
              <Text style={styles.permLabel}>{key}</Text>
              <View style={styles.permBadges}>
                <Badge
                  text={local ? 'terminal : oui' : 'terminal : non'}
                  tone={local ? 'success' : 'neutral'}
                />
                {remote === null ? null : (
                  <Badge
                    text={remote ? 'serveur : oui' : 'serveur : non'}
                    tone={remote ? 'success' : 'danger'}
                  />
                )}
              </View>
            </View>
          );
        })}
      </Card>

      <Card>
        <SectionTitle>Diagnostic</SectionTitle>
        <Field label="PROJET SUPABASE">
          <Text style={styles.meta}>{config.supabaseUrl || 'non configuré'}</Text>
        </Field>
        <Field label="DEVISE / TVA">
          <Text style={styles.meta}>
            {config.currency} · TVA {config.taxRate} %
          </Text>
        </Field>
        <Field label="RÔLE VU PAR LE SERVEUR">
          <Text style={styles.meta}>{server?.role || '—'}</Text>
        </Field>
        <Text style={styles.hint}>
          Les écritures (vente, encaissement, mouvement de stock) passent par les RPC
          `app_create_sale`, `app_register_payment` et `app_stock_movement`
          (fichier supabase_mobile_rpc.sql). Si elles renvoient une erreur 42501,
          exécutez ce fichier dans Supabase.
        </Text>
      </Card>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  content: { padding: sp(3), paddingBottom: sp(10) },
  name: { fontSize: 18, fontWeight: '800', color: colors.primary },
  meta: { fontSize: 13, color: colors.textMuted, marginTop: sp(1) },
  hint: { fontSize: 12, color: colors.textLight, marginTop: sp(2), lineHeight: 17 },
  fullBtn: { width: '100%', marginTop: sp(3) },
  smallBtn: { minHeight: 36, paddingHorizontal: sp(3) },
  permRow: {
    paddingVertical: sp(2),
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  permLabel: { fontSize: 13, fontWeight: '600', color: colors.text },
  permBadges: { flexDirection: 'row', flexWrap: 'wrap', gap: sp(2), marginTop: sp(1.5) },
});
