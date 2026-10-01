// ============================================================================
// Onglets « Terrain » (mobile-only) — 4 écrans de terrain accessibles au pouce.
// Le module est imbriqué dans l'écran `Terrain` du drawer (RootDrawer.js) :
// le header natif est coupé, chaque onglet reçoit son chrome via withChrome()
// (TopBar + SyncBanner), exactement comme une page web dans <Layout>.
// ============================================================================
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { useCallback, useMemo } from 'react';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Icon from '../components/Icon';
import { withChrome } from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import CaisseScreen from '../screens/CaisseScreen';
import CompteScreen from '../screens/CompteScreen';
import InventaireScreen from '../screens/InventaireScreen';
import PaiementsScreen from '../screens/PaiementsScreen';
import { colors, sp } from '../theme';

const Tab = createBottomTabNavigator();

/**
 * Chaque onglet est conditionné par la MÊME permission que la garde des RPC
 * serveur : un caissier ne voit pas un écran dont l'usage lui serait refusé
 * au moment d'enregistrer.
 */
const TABS = [
  { name: 'Caisse', icon: 'sale', component: CaisseScreen, perms: ['create_sales'], sync: false },
  {
    name: 'Encaissement',
    icon: 'cash',
    component: PaiementsScreen,
    perms: ['create_sales', 'manage_treasury'],
  },
  { name: 'Inventaire', icon: 'stock', component: InventaireScreen, perms: ['view_stock'] },
  { name: 'Compte', icon: 'user', component: CompteScreen, perms: [] },
];

export default function MainTabs() {
  const { can } = useAuth();
  const insets = useSafeAreaInsets();

  // Écrans MÉMORISÉS : `withChrome()` fabrique un nouveau composant à chaque
  // appel ; sans mémoïsation, l'onglet actif serait démonté/remonté à chaque
  // rendu du navigateur (perte de la vente en cours).
  const visible = useMemo(
    () =>
      TABS.filter(
        (tab) => tab.perms.length === 0 || tab.perms.some((permission) => can(permission))
      ).map((tab) => ({
        ...tab,
        Screen: withChrome(tab.component, {
          title: tab.name,
          showSync: tab.sync !== false,
          // La barre d'onglets gère déjà l'encoche basse.
          bottomInset: false,
        }),
      })),
    [can]
  );

  const screenOptions = useCallback(
    ({ route }) => ({
      // Chrome monté par withChrome() : pas de header natif (double TopBar).
      headerShown: false,
      tabBarActiveTintColor: colors.primary,
      tabBarInactiveTintColor: colors.textLight,
      tabBarLabelStyle: { fontSize: 11, fontWeight: '700' },
      tabBarItemStyle: { paddingVertical: sp(1.5) },
      tabBarStyle: {
        backgroundColor: colors.card,
        borderTopColor: colors.border,
        borderTopWidth: 1,
        // L'inset bas DOIT être rejoué ici. React Navigation calcule bien
        // `paddingBottom: insets.bottom` (BottomTabBar.js) mais applique
        // `tabBarStyle` EN DERNIER, ce qui l'écrase, et un `height` numérique
        // court-circuite l'ajout de l'inset à la hauteur. Comme l'APK est
        // edge-to-edge (gradle.properties), sans ça les libellés passent sous
        // la barre système gestuelle ou les 3 boutons.
        height: 62 + insets.bottom,
        paddingBottom: sp(1.5) + insets.bottom,
        paddingTop: sp(1.5),
      },
      tabBarIcon: ({ color, focused }) => (
        <Icon
          name={(TABS.find((tab) => tab.name === route.name) || {}).icon || 'dashboard'}
          size={21}
          color={color}
          strokeWidth={focused ? 2.2 : 1.8}
        />
        ),
    }),
    [insets.bottom]
  );

  return (
    <Tab.Navigator screenOptions={screenOptions}>
      {visible.map((tab) => (
        <Tab.Screen key={tab.name} name={tab.name} component={tab.Screen} />
      ))}
    </Tab.Navigator>
  );
}
