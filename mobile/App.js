import 'react-native-gesture-handler';
import 'react-native-reanimated';
import { DefaultTheme, NavigationContainer } from '@react-navigation/native';
import { StatusBar } from 'expo-status-bar';
import { ActivityIndicator, Image, StyleSheet, Text, View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AuthProvider, useAuth } from './src/context/AuthContext';
import { StoreProvider } from './src/context/StoreContext';
import RootDrawer from './src/navigation/RootDrawer';
import LoginScreen from './src/screens/LoginScreen';
import { LOGO } from './src/brand';
import { colors } from './src/theme';

/** Thème de navigation aligné sur la palette desktop/web. */
const navigationTheme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    primary: colors.primary,
    background: colors.bg,
    card: colors.card,
    text: colors.text,
    border: colors.border,
  },
};

/** Écran d'attente pendant la restauration de la session Supabase. */
function BootScreen() {
  return (
    <View style={styles.boot}>
      <View style={styles.bootLogo}>
        <Image source={LOGO} style={styles.bootLogoImage} resizeMode="contain" />
      </View>
      <Text style={styles.bootTitle}>KORGO PRO</Text>
      <Text style={styles.bootMessage}>Restauration de la session…</Text>
      <ActivityIndicator color="#fff" />
    </View>
  );
}

/** Aiguillage : session restaurée -> drawer (9 modules) + onglets, sinon connexion. */
function Root() {
  const { user, restoring } = useAuth();
  if (restoring) return <BootScreen />;
  return user ? <RootDrawer /> : <LoginScreen />;
}

/**
 * Point d'entrée de l'application mobile.
 *
 * Ordre des fournisseurs : SafeAreaProvider (encoches) -> AuthProvider
 * (session Supabase) -> StoreProvider (magasins, dépend de la session) ->
 * NavigationContainer.
 */
export default function App() {
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <StoreProvider>
          <NavigationContainer theme={navigationTheme}>
            <StatusBar style="dark" />
            <Root />
          </NavigationContainer>
        </StoreProvider>
      </AuthProvider>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  boot: {
    flex: 1,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
  },
  bootLogo: {
    width: 72,
    height: 72,
    borderRadius: 18,
    backgroundColor: '#ffffff',
    alignItems: 'center',
    justifyContent: 'center',
  },
  // Logo officiel (K turquoise) — même source que le desktop : assets/logo.png
  // est régénéré par `_sync_logo.py` à partir de ui/icons/logo.ico.
  bootLogoImage: { width: 60, height: 60, borderRadius: 10 },
  bootTitle: { color: '#fff', fontSize: 18, fontWeight: '800', letterSpacing: 3 },
  bootMessage: { color: 'rgba(255,255,255,0.75)', fontSize: 13 },
});
