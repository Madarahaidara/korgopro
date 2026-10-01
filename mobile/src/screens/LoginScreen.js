import { useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import { KeyboardAvoidingView, Image, Platform, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Icon from '../components/Icon';
import { Banner, Btn, Field, Input } from '../components/ui';
import { MISSING_ENV_MESSAGE, isConfigured } from '../config';
import { useAuth } from '../context/AuthContext';
import { SessionConflictError, describeOtherSession } from '../api/sessionApi';
import { LOGO } from '../brand';
import { colors, sp } from '../theme';

const FEATURES = ['Gestion des ventes', 'Suivi de stock', 'Tresorerie', 'Proformas & devis'];

/**
 * Ecran de connexion — aligne 1:1 avec le design web (web/src/pages/Login.jsx) :
 * panneau bleu (logo + avantages) au-dessus du panneau blanc de formulaire.
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
        contentContainerStyle={[
          styles.content,
          { paddingTop: Math.max(insets.top, 20), paddingBottom: Math.max(insets.bottom, 20) },
        ]}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.cardWrap}>
          {/* Panneau bleu : logo + avantages (colonne gauche du web) */}
          <View style={styles.brandPanel}>
            <View style={styles.logo}>
              <Image source={LOGO} style={styles.logoImage} resizeMode="contain" />
            </View>
            <Text style={styles.brandTitle}>KORGO PRO</Text>
            <Text style={styles.brandSub}>Gestion d'entreprise tout-en-un</Text>

            <View style={styles.features}>
              {FEATURES.map((feature) => (
                <View style={styles.featureItem} key={feature}>
                  <View style={styles.featureCheck}>
                    <Icon name="check" size={12} color="#ffffff" />
                  </View>
                  <Text style={styles.featureText}>{feature}</Text>
                </View>
              ))}
            </View>
          </View>

          {/* Panneau blanc : formulaire (colonne droite du web) */}
          <View style={styles.formPanel}>
            <Text style={styles.formTitle}>Connexion</Text>
            <Text style={styles.formSubtitle}>Connectez-vous pour acceder a votre espace</Text>

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

            <Field label="EMAIL OU NOM D'UTILISATEUR">
              <Input
                value={identifiant}
                onChangeText={setIdentifiant}
                placeholder="ex. admin@korgo-pro.com"
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="email-address"
                returnKeyType="next"
              />
            </Field>

            <Field label="MOT DE PASSE">
              <Input
                value={password}
                onChangeText={setPassword}
                placeholder="••••••••"
                secureTextEntry
                autoCapitalize="none"
                returnKeyType="go"
                onSubmitEditing={submit}
              />
            </Field>

            <Btn
              title={busy ? 'Connexion…' : 'Se connecter'}
              onPress={submit}
              loading={busy}
              disabled={!configured}
              style={styles.submitBtn}
            />

            <View style={styles.divider} />
            <Text style={styles.hintText}>
              Compte Supabase Auth requis, synchronise avec la base Korgo Pro.
            </Text>
            <Text style={styles.versionText}>{'© ' + new Date().getFullYear() + ' Korgo Pro'}</Text>
          </View>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#eef2f7' },
  content: { padding: sp(4), flexGrow: 1, justifyContent: 'center' },
  cardWrap: {
    backgroundColor: '#ffffff',
    borderRadius: 20,
    overflow: 'hidden',
    shadowColor: '#101828',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.16,
    shadowRadius: 30,
    elevation: 6,
  },
  brandPanel: { backgroundColor: colors.primary, padding: sp(6), alignItems: 'center' },
  logo: {
    width: 76,
    height: 76,
    borderRadius: 20,
    // Fond blanc : le logo officiel est un K turquoise sur fond blanc.
    backgroundColor: '#ffffff',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: sp(3),
  },
  // K turquoise centré dans le carré blanc (cf. src/brand.js).
  logoImage: { width: 62, height: 62, borderRadius: 14 },
  brandTitle: { fontSize: 22, fontWeight: '800', letterSpacing: 2, color: '#ffffff' },
  brandSub: {
    color: 'rgba(255,255,255,0.75)',
    fontSize: 13,
    marginTop: sp(1),
    textAlign: 'center',
  },
  features: { marginTop: sp(4), width: '100%', gap: sp(2) },
  featureItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.95)',
    borderRadius: 8,
    paddingVertical: sp(2),
    paddingHorizontal: sp(3),
  },
  featureCheck: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: colors.success,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: sp(2.5),
  },
  featureText: { fontSize: 13, fontWeight: '600', color: '#111827' },
  formPanel: { padding: sp(6), backgroundColor: '#ffffff' },
  formTitle: { fontSize: 20, fontWeight: '700', color: '#111827' },
  formSubtitle: { color: '#6b7280', fontSize: 13, marginTop: 4, marginBottom: sp(4) },
  submitBtn: { backgroundColor: colors.primary, borderRadius: 10, paddingVertical: sp(3) },
  conflictText: { fontSize: 12, color: '#6b7280', textAlign: 'center', marginBottom: sp(3) },
  divider: { height: 1, backgroundColor: '#e5e7eb', marginVertical: sp(4) },
  hintText: { fontSize: 12, color: '#6b7280', textAlign: 'center', lineHeight: 17 },
  versionText: { fontSize: 11, color: '#9ca3af', textAlign: 'center', marginTop: sp(3) },
});

