// ============================================================================
// Navigation racine (mobile) — miroir de web/src/App.jsx + Layout.jsx du web.
//
//   web/src/App.jsx             -> Protected (session + permission) => withGuard()
//   Layout.jsx <aside sidebar>  -> tiroir latéral : même NAV, mêmes permissions
//   Layout.jsx <div class=main> -> withChrome() : TopBar + SyncBanner + écran
//   (mobile only)               -> onglets du bas « Terrain » : caisse de terrain
//
// Le header natif est désactivé partout : le chrome est monté UNE seule fois par
// withChrome() (sinon le TopBar du tiroir et celui des onglets s'empilent).
// ============================================================================
import { createDrawerNavigator, DrawerContentScrollView } from '@react-navigation/drawer';
import { useCallback, useMemo } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import Icon from '../components/Icon';
import { Brand, withChrome } from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { colors, sp } from '../theme';
import MainTabs from './MainTabs';
import AdminScreen from '../pages/Admin';
import CustomersScreen from '../pages/Customers';
import DashboardScreen from '../pages/Dashboard';
import InvoicesScreen from '../pages/Invoices';
import ProformasScreen from '../pages/Proformas';
import SalesScreen from '../pages/Sales';
import SettingsScreen from '../pages/Settings';
import StockScreen from '../pages/Stock';
import TreasuryScreen from '../pages/Treasury';

const Drawer = createDrawerNavigator();

/**
 * NAV — libellés, icônes et permissions repris à l'identique de la constante
 * NAV de web/src/components/Layout.jsx (vocabulaire « module » du web, traduit
 * vers le vocabulaire fin par MODULE_TO_FINE dans context/AuthContext.js).
 */
export const NAV = [
  { name: 'Accueil', label: 'Dashboard', icon: 'dashboard', perm: 'dashboard', component: DashboardScreen },
  { name: 'Ventes', label: 'Vente', icon: 'sale', perm: 'sales', component: SalesScreen },
  { name: 'Factures', label: 'Registre factures', icon: 'receipt', perm: 'invoices', component: InvoicesScreen },
  { name: 'Proformas', label: 'Document', icon: 'document', perm: 'proformas', component: ProformasScreen },
  { name: 'Stock', label: 'Stock', icon: 'stock', perm: 'stock', component: StockScreen },
  { name: 'Tresorerie', label: 'Trésorerie', icon: 'treasury', perm: 'treasury', component: TreasuryScreen },
  { name: 'Clients', label: 'Clients', icon: 'user', perm: 'customers', component: CustomersScreen },
  { name: 'Administration', label: 'Admin', icon: 'admin', perm: 'admin', component: AdminScreen },
  { name: 'Parametres', label: 'Paramètres', icon: 'settings', perm: 'settings', component: SettingsScreen },
];

/** Module mobile-only : les 4 onglets de terrain (caisse, encaissement…). */
export const TERRAIN = { name: 'Terrain', label: 'Terrain (caisse)', icon: 'sale', perm: null };

/** Entrées réellement visibles pour l'utilisateur connecté (comme `items` du web). */
export function useNavEntries() {
  const { can } = useAuth();
  return [TERRAIN, ...NAV.filter((entry) => can(entry.perm))];
}

/** Écran « Accès refusé » — même texte que la garde de web/src/App.jsx. */
function Denied() {
  return (
    <View style={styles.denied}>
      <Icon name="lock" size={40} color={colors.textLight} />
      <Text style={styles.deniedTitle}>Accès refusé</Text>
      <Text style={styles.deniedText}>Votre rôle ne vous permet pas d'accéder à ce module.</Text>
    </View>
  );
}

/**
 * Équivalent mobile de <Protected perm="…"> (web/src/App.jsx).
 * Le chrome reste monté autour (contrairement au web) : sur mobile il faut
 * pouvoir rouvrir le menu pour changer de module.
 */
function withGuard(Component, perm) {
  function Guarded(props) {
    const { user, can } = useAuth();
    if (!user) return <Denied />;
    if (perm && !can(perm)) return <Denied />;
    return <Component {...props} />;
  }
  Guarded.displayName = `Guard(${Component.displayName || Component.name || 'Screen'})`;
  return Guarded;
}

/** .nav-link de la sidebar web : fond sidebar, texte #dbeafe, actif #1B3A7A. */
function NavLink({ icon, label, focused, onPress }) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.navLink,
        focused ? styles.navLinkActive : null,
        pressed ? styles.navLinkPressed : null,
      ]}
    >
      <Icon name={icon} size={19} color={focused ? '#fff' : colors.sidebarText} />
      <Text style={[styles.navLabel, focused ? styles.navLabelActive : null]} numberOfLines={1}>
        {label}
      </Text>
    </Pressable>
  );
}

/** Contenu du tiroir = .sidebar du web : brand + nav + pied (utilisateur). */
function DrawerContent({ navigation, state }) {
  const { user, roleLabel } = useAuth();
  const entries = useNavEntries();
  const focusedName = state.routes[state.index]?.name;

  return (
    <DrawerContentScrollView
      style={styles.drawerBody}
      contentContainerStyle={styles.nav}
      indicatorStyle="white"
    >
      <Brand />
      {entries.map((entry) => (
        <NavLink
          key={entry.name}
          icon={entry.icon}
          label={entry.label}
          focused={focusedName === entry.name}
          onPress={() => {
            navigation.navigate(entry.name);
            navigation.closeDrawer?.();
          }}
        />
      ))}
      <View style={styles.drawerFooter}>
        <Text style={styles.footerName} numberOfLines={1}>
          {user?.username || '—'}
        </Text>
        <Text style={styles.footerRole} numberOfLines={1}>
          {roleLabel || user?.role || ''}
        </Text>
      </View>
    </DrawerContentScrollView>
  );
}

export default function RootDrawer() {
  const { can } = useAuth();
  // Les écrans sont MÉMORISÉS : construire `withChrome(...)` à chaque rendu
  // créerait un nouveau type de composant, ce qui remonterait l'écran à chaque
  // rendu du drawer (perte du formulaire de vente en cours).
  const screens = useMemo(
    () =>
      NAV.filter((entry) => can(entry.perm)).map((entry) => ({
        name: entry.name,
        Component: withChrome(withGuard(entry.component, entry.perm), { title: entry.label }),
      })),
    [can]
  );
  const renderDrawer = useCallback((props) => <DrawerContent {...props} />, []);

  return (
    <Drawer.Navigator
      initialRouteName={TERRAIN.name}
      drawerContent={renderDrawer}
      screenOptions={{
        headerShown: false,
        drawerType: 'front',
        drawerPosition: 'left',
        swipeEdgeWidth: 42,
        drawerStyle: { backgroundColor: colors.sidebar, width: 288 },
        sceneStyle: { backgroundColor: colors.bg },
      }}
    >
      <Drawer.Screen name={TERRAIN.name} component={MainTabs} />
      {screens.map(({ name, Component }) => (
        <Drawer.Screen key={name} name={name} component={Component} />
      ))}
    </Drawer.Navigator>
  );
}


const styles = StyleSheet.create({
  denied: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: sp(2),
    padding: sp(6),
    backgroundColor: colors.bg,
  },
  deniedTitle: { fontSize: 17, fontWeight: '800', color: colors.text },
  deniedText: { fontSize: 13, color: colors.textMuted, textAlign: 'center' },
  drawerBody: { backgroundColor: colors.sidebar },
  // .nav : padding 12/10, gap 2px.
  nav: { paddingVertical: sp(3), paddingHorizontal: sp(2.5), paddingBottom: sp(8) },
  // .nav-link : padding 10/12, radius 6, poids 500, 14px, couleur #dbeafe.
  navLink: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: sp(2.5),
    paddingHorizontal: sp(3),
    paddingVertical: sp(2.5),
    borderRadius: 6,
    borderWidth: 1,
    borderColor: 'transparent',
    marginVertical: 1,
  },
  // .nav-link.active : background var(--sidebar-active) #1B3A7A, texte blanc.
  navLinkActive: { backgroundColor: colors.primaryDark, borderColor: colors.accent },
  navLinkPressed: { backgroundColor: 'rgba(255,255,255,0.10)' },
  navLabel: { fontSize: 14, fontWeight: '500', color: colors.sidebarText, flex: 1 },
  navLabelActive: { color: '#fff', fontWeight: '700' },
  drawerFooter: {
    marginTop: 'auto',
    paddingVertical: sp(3),
    paddingHorizontal: sp(4),
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.08)',
  },
  footerName: { color: '#fff', fontSize: 13, fontWeight: '700' },
  footerRole: { color: colors.sidebarText, fontSize: 11, marginTop: 2 },
});

