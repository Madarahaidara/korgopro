import { useRef, useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import {
  KeyboardAvoidingView, Image, Platform, ScrollView, StyleSheet, Text, View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Banner, Btn, Field, Input } from '../components/ui';
import { MISSING_ENV_MESSAGE, isConfigured } from '../config';
import { useAuth } from '../context/AuthContext';
import { SessionConflictError, describeOtherSession } from '../api/sessionApi';
import { useKeyboardScroll } from '../lib/keyboardScroll';
import { LOGO } from '../brand';
import { colors, sp } from '../theme';

/**
 * Écran de connexion mobile : logo, identifiants et accès au compte.
 */
export default function LoginScreen() {
  const insets = useSafeAreaInsets();
  const { signIn } = useAuth();
  const [identifiant, setIdentifiant] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  // Session unique : un autre appareil est deja connecte a ce compte.
  const [conflict, setConflict] = useState(null);
  // Clavier : le hook mesure le champ focus et le remonte au-dessus du clavier
  // (Android edge-to-edge / adjustResize — KeyboardAvoidingView ne suffit pas).
  const { scrollRef, keyboardHeight, onScroll, scrollToField } = useKeyboardScroll();
  // Refs des champs : mesure + scroll vers le champ focusé.
  const identifiantRef = useRef(null);
  const passwordRef = useRef(null);
  const configured = isConfigured();

  const connect = async (options) => {
    setError(null);
    setConflict(null);
    setBusy(true);
    try {
      await signIn(identifiant, password, options);
      setPassword('');
    } catch (e) {
      if (e instanceof SessionConflictError || e?.code === 'SESSION_ACTIVE') {
        // Compte deja ouvert ailleurs : on propose de reprendre la main.
        setConflict({ message: e.message, other: e.other });
      } else {
        setError(e.message || 'Connexion impossible.');
      }
    } finally {
      setBusy(false);
    }
  };

  const submit = async () => {
    if (busy) return;
    await connect({ force: false });
  };

  // L'utilisateur assume de fermer la session de l'autre appareil.
  const takeOver = async () => {
    if (busy) return;
    await connect({ force: true });
  };

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <StatusBar style="light" />
      <ScrollView
        ref={scrollRef}
        onScroll={onScroll}
        scrollEventThrottle={16}
        contentContainerStyle={[
          styles.content,
          {
            paddingTop: Math.max(insets.top, 20),
            paddingBottom: Math.max(insets.bottom, 20) + keyboardHeight,
          },
        ]}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.cardWrap}>
          <View style={styles.brandPanel}>
            <Image source={LOGO} style={styles.logoImage} resizeMode="contain" />
            <Text style={styles.brandTitle}>Korgo Pro</Text>
          </View>
          <View style={styles.formPanel}>
            <Text style={styles.formTitle}>Connexion</Text>
            <Text style={styles.formSubtitle}>Accédez à votre compte</Text>

            {!configured ? (
              <Banner tone="danger" title="Configuration requise" message={MISSING_ENV_MESSAGE} />
            ) : null}
            {error ? <Banner tone="danger" title="Connexion refusee" message={error} /> : null}

            {/* Session unique : un autre appareil est deja connecte a ce compte. */}
            {conflict ? (
              <>
                <Banner tone="warning" title="Deja connecte ailleurs" message={conflict.message} />
                <Text style={styles.conflictText}>
                  Session en cours : {describeOtherSession(conflict.other)}
                </Text>
                <Btn
                  title={busy ? 'Deconnexion de l\u2019autre appareil\u2026' : 'Deconnecter l\u2019autre appareil et se connecter'}
                  onPress={takeOver}
                  loading={busy}
                  disabled={!configured}
                  style={styles.submitBtn}
                />
              </>
            ) : null}

            <Field label="IDENTIFIANT">
              <Input
                ref={identifiantRef}
                value={identifiant}
                onChangeText={setIdentifiant}
                placeholder="ex. admin@korgo-pro.com"
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="email-address"
                returnKeyType="next"
                onFocus={() => scrollToField(identifiantRef)}
              />
            </Field>

            <Field label="MOT DE PASSE">
              <Input
                ref={passwordRef}
                value={password}
                onChangeText={setPassword}
                placeholder="••••••••"
                secureTextEntry
                autoCapitalize="none"
                returnKeyType="go"
                onSubmitEditing={submit}
                onFocus={() => scrollToField(passwordRef)}
              />
            </Field>

            <Btn
              title={busy ? 'Connexion…' : 'Se connecter'}
              onPress={submit}
              loading={busy}
              disabled={!configured}
              style={styles.submitBtn}
            />

          </View>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  // Pas de `justifyContent: 'center'` ici : centrer le contenu d'un ScrollView
  // empêche le défilement automatique vers le champ focused quand le clavier
  // s'ouvre (champs masqués). flexGrow:1 garde le fond plein écran.
  content: { padding: sp(5), flexGrow: 1 },
  cardWrap: {
    backgroundColor: '#ffffff',
    borderRadius: 16,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: colors.border,
    shadowColor: '#172b3a',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 12,
    elevation: 3,
  },
  brandPanel: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: sp(2), paddingTop: sp(5) },
  logoImage: { width: 42, height: 42, borderRadius: 10 },
  brandTitle: { fontSize: 20, fontWeight: '800', color: colors.primary },
  formPanel: { padding: sp(5), paddingTop: sp(3), backgroundColor: '#ffffff', gap: sp(1) },
  formTitle: { fontSize: 20, fontWeight: '700', color: colors.text },
  formSubtitle: { color: colors.textMuted, fontSize: 13, marginTop: 2, marginBottom: sp(2) },
  submitBtn: { backgroundColor: colors.primary, borderRadius: 10, paddingVertical: sp(3) },
  conflictText: { fontSize: 12, color: '#6b7280', textAlign: 'center', marginBottom: sp(3) },
});

