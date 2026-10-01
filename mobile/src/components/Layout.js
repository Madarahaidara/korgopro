// ============================================================================
// Layout mobile — miroir exact de web/src/components/Layout.jsx.
//
//   Web    : <aside class="sidebar"> brand + nav </aside>
//            <div class="main"> <header class="topbar"> burger + titre +
//                                 magasin + utilisateur </header>
//                                 <SyncBanner/> <main>{children}</main> </div>
//   Mobile : <Drawer>  = sidebar  (navigation/RootDrawer.js, même NAV,
//                          mêmes permissions, même fond bleu marine)
//            <TopBar>  = .topbar  (burger = openDrawer, titre, magasin, user)
//            <SyncBanner/> + contenu
//
// `withChrome()` est l'équivalent de l'`<Outlet/>` wrapppé par Layout : c'est le
// SEUL endroit qui monte TopBar + SyncBanner (un écran = un chrome, pas deux).
// ============================================================================
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { DrawerActions } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import TopBar from './TopBar';
import SyncBanner from './SyncBanner';
import { useAuth } from '../context/AuthContext';
import { colors, sp } from '../theme';

/**
 * Ouvre le menu latéral : c'est le `.burger` du web. L'action remonte la
 * hiérarchie des navigateurs, elle fonctionne donc aussi depuis un onglet
 * imbriqué dans le drawer.
 */
export function openMenu(navigation) {
  try {
    navigation?.dispatch?.(DrawerActions.openDrawer());
  } catch {
    /* Écran hors drawer : aucun menu à ouvrir. */
  }
}

/** Chrome d'un écran : TopBar (.topbar) + SyncBanner + zone de contenu. */
export default function Layout({ navigation, title, showSync = true, bottomInset = true, children }) {
  const insets = useSafeAreaInsets();
  return (
    <View style={styles.root}>
      <TopBar title={title} onMenu={() => openMenu(navigation)} />
      {showSync ? <SyncBanner /> : null}
      {/* Les écrans des onglets sont déjà raccordés par la barre d'onglets. */}
      <View style={[styles.content, bottomInset ? { paddingBottom: insets.bottom } : null]}>
        {children}
      </View>
    </View>
  );
}

/**
 * Enveloppe un écran avec le chrome (TopBar + SyncBanner), exactement comme le
 * web enveloppe chaque page dans <Layout>. Le `title` alimente .topbar-title.
 */
export function withChrome(Component, { title, showSync = true, bottomInset = true } = {}) {
  function Chrome(props) {
    return (
      <Layout
        navigation={props.navigation}
        title={title}
        showSync={showSync}
        bottomInset={bottomInset}
      >
        <Component {...props} />
      </Layout>
    );
  }
  Chrome.displayName = `Chrome(${Component.displayName || Component.name || 'Screen'})`;
  return Chrome;
}

/** .brand de la sidebar (identique au web : logo K + nom société + sous-titre). */
export function Brand() {
  const { settings } = useAuth();
  return (
    <View style={styles.brand}>
      <View style={styles.brandLogo}>
        <Text style={styles.brandLogoText}>K</Text>
      </View>
      <View style={styles.brandTexts}>
        <Text style={styles.brandName} numberOfLines={1}>
          {settings?.company_name || 'Korgo Pro'}
        </Text>
        <Text style={styles.brandSub}>Gestion terrain</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  content: { flex: 1 },
  // .brand : padding 18/16, bordure basse blanche translucide, logo #3B82F6.
  brand: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: sp(2.5),
    paddingVertical: sp(4.5),
    paddingHorizontal: sp(4),
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.08)',
  },
  brandLogo: {
    width: 38,
    height: 38,
    borderRadius: 10,
    backgroundColor: '#3B82F6',
    alignItems: 'center',
    justifyContent: 'center',
  },
  brandLogoText: { color: '#fff', fontSize: 20, fontWeight: '800' },
  brandTexts: { flex: 1, minWidth: 0 },
  brandName: { color: '#fff', fontSize: 15, fontWeight: '800' },
  brandSub: { fontSize: 11, color: colors.sidebarText, marginTop: 1 },
});

