// ============================================================================
// Barre supérieure mobile — reproduit .topbar de web/src/index.css et le
// header de web/src/components/Layout.jsx : titre + magasin actif (sélecteur),
// avatar/nom/rôle de l'utilisateur et bouton de déconnexion.
// ============================================================================
import { useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Icon from './Icon';
import { Btn, Modal } from './ui';
import { useAuth } from '../context/AuthContext';
import { useStores } from '../context/StoreContext';
import { colors, sp } from '../theme';

export default function TopBar({ title, onMenu }) {
  const insets = useSafeAreaInsets();
  const { user, roleLabel, signOut, settings } = useAuth();
  const { stores, activeId, activeStore, selectStore, refreshStores, loading } = useStores();
  const [pickerOpen, setPickerOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const visibleStores = stores.filter((store) => store.active !== false);
  const initial = (user?.username?.[0] || 'K').toUpperCase();

  const confirmLogout = () => {
    Alert.alert('Déconnexion', 'Quitter la session en cours ?', [
      { text: 'Annuler', style: 'cancel' },
      {
        text: 'Se déconnecter',
        style: 'destructive',
        onPress: async () => {
          setBusy(true);
          try {
            await signOut();
          } finally {
            setBusy(false);
          }
        },
      },
    ]);
  };

  return (
    <View style={[styles.bar, { paddingTop: insets.top + sp(2) }]}>
      {/* Ligne 1 : burger (.burger) + titre + utilisateur (.topbar-user) */}
      <View style={styles.row}>
        <View style={styles.left}>
          {onMenu ? (
            <Pressable
              onPress={onMenu}
              hitSlop={10}
              style={({ pressed }) => [styles.burger, pressed ? styles.burgerPressed : null]}
              accessibilityRole="button"
              accessibilityLabel="Ouvrir le menu"
            >
              <Icon name="menu" size={22} color={colors.text} />
            </Pressable>
          ) : null}
          <Text style={styles.title} numberOfLines={1}>Korgo Pro</Text>
          {title ? (
            <Text style={styles.sub} numberOfLines={1}>
              {'· ' + title}
            </Text>
          ) : null}
        </View>
        <View style={styles.userBlock}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{initial}</Text>
          </View>
          <View>
            <Text style={styles.userName} numberOfLines={1}>
              {user?.username || '—'}
            </Text>
            <Text style={styles.userRole} numberOfLines={1}>
              {roleLabel || user?.role || ''}
            </Text>
          </View>
        </View>
      </View>

      {/* Ligne 2 : sélecteur de magasin + déconnexion */}
      <View style={styles.row}>
        <Pressable style={styles.select} onPress={() => setPickerOpen(true)}>
          <Icon name="store" size={15} color={colors.primary} />
          <Text style={styles.selectText} numberOfLines={1}>
            {activeStore?.name || 'Choisir un magasin'}
          </Text>
          <Icon name="chevronDown" size={14} color={colors.textMuted} />
        </Pressable>
        <Btn
          title="Déconnexion"
          variant="logout"
          onPress={confirmLogout}
          loading={busy}
          style={styles.logout}
        />
      </View>

      <Modal visible={pickerOpen} title="Magasin actif" onClose={() => setPickerOpen(false)}>
        <ScrollView style={styles.pickerList}>
          {visibleStores.length === 0 ? (
            <Text style={styles.storeMeta}>Aucun magasin disponible.</Text>
          ) : null}
          {visibleStores.map((store) => {
            const selected = store.id === activeId;
            return (
              <Pressable
                key={String(store.id)}
                style={[styles.storeRow, selected ? styles.storeRowActive : null]}
                onPress={() => {
                  selectStore(store.id);
                  setPickerOpen(false);
                }}
              >
                <View style={styles.grow}>
                  <Text style={[styles.storeName, selected ? styles.storeNameActive : null]}>
                    {store.name}
                  </Text>
                  {store.address ? <Text style={styles.storeMeta}>{store.address}</Text> : null}
                </View>
                {selected ? <Icon name="check" size={16} color={colors.success} /> : null}
              </Pressable>
            );
          })}
        </ScrollView>
        <Btn
          variant="ghost"
          title="Rafraîchir la liste"
          onPress={refreshStores}
          loading={loading}
          style={styles.refreshBtn}
        />
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  // .topbar : fond blanc, bordure basse, padding 12/16.
  bar: {
    backgroundColor: colors.card,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    paddingHorizontal: sp(4),
    paddingBottom: sp(2.5),
    gap: sp(2),
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: sp(2.5),
  },
  left: { flexDirection: 'row', alignItems: 'center', gap: sp(1.5), flexShrink: 1 },
  // .burger : carré cliquable du menu latéral (sidebar réduite sur mobile).
  burger: {
    width: 34,
    height: 34,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: sp(1),
  },
  burgerPressed: { backgroundColor: colors.primarySoft },
  // .topbar-title : 800 / 15px — .topbar-sub : 500, gris.
  title: { fontSize: 15, fontWeight: '800', color: colors.text },
  sub: { fontSize: 13, fontWeight: '500', color: colors.textMuted, flexShrink: 1 },
  userBlock: { flexDirection: 'row', alignItems: 'center', gap: sp(2) },
  // .avatar : 34px rond, fond primary-soft, texte primary, 800.
  avatar: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: { fontSize: 14, fontWeight: '800', color: colors.primary },
  // .user-name / .user-role
  userName: { fontSize: 13, fontWeight: '700', color: colors.text },
  userRole: { fontSize: 11, color: colors.textMuted },
  // .select : champ compact de sélection du magasin actif.
  select: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: sp(2),
    borderWidth: 1,
    borderColor: colors.fieldBorder,
    backgroundColor: '#f9fafb',
    borderRadius: 8,
    paddingHorizontal: sp(3),
    paddingVertical: sp(2),
  },
  selectText: { flex: 1, fontSize: 13, fontWeight: '600', color: colors.text },
  logout: { minHeight: 36, paddingHorizontal: sp(4) },
  pickerList: { maxHeight: 300, marginBottom: sp(2) },
  storeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: sp(2),
    paddingVertical: sp(2.5),
    paddingHorizontal: sp(2),
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  storeRowActive: { backgroundColor: colors.primarySoft, borderRadius: 8 },
  grow: { flex: 1, minWidth: 0 },
  storeName: { fontSize: 14, fontWeight: '600', color: colors.text },
  storeNameActive: { color: colors.primary, fontWeight: '800' },
  storeMeta: { fontSize: 12, color: colors.textMuted, marginTop: 2 },
  refreshBtn: { minHeight: 38 },
});

