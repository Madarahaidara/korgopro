// ============================================================================
// Bandeau de synchronisation (mobile) — miroir de web SyncBanner.jsx.
// Mobile = lecture à la demande, pas de file d'écriture : le bandeau affiche
// le mode (Supabase / config manquante) + la latence du dernier ping.
// ============================================================================
import { useCallback, useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { isConfigured } from '../config';
import { ping } from '../api/supabase';
import { colors, sp } from '../theme';
import Icon from './Icon';

export default function SyncBanner() {
  const [state, setState] = useState({ ok: null, latency: null, message: '' });
  const [hidden, setHidden] = useState(false);

  const check = useCallback(async () => {
    if (!isConfigured()) {
      setState({ ok: false, latency: null, message: 'Supabase non configuré (mobile/.env).' });
      return;
    }
    const res = await ping().catch((e) => ({ ok: false, latency: 0, message: e.message }));
    setState(res);
  }, []);

  useEffect(() => {
    check();
  }, [check]);

  if (hidden) return null;
  const tone = !isConfigured() || state.ok === false ? 'warn' : state.ok ? 'ok' : 'idle';

  return (
    <View style={[styles.banner, tone === 'ok' ? styles.ok : tone === 'warn' ? styles.warn : styles.idle]}>
      <Icon name={tone === 'ok' ? 'check' : 'alert'} size={15} color={tone === 'ok' ? colors.successDark : colors.warning} />
      <View style={styles.grow}>
        <Text style={styles.title}>
          {tone === 'ok' ? 'Supabase — données synchronisées' : tone === 'warn' ? 'Supabase — vérifiez la connexion' : 'Supabase — vérification…'}
        </Text>
        <Text style={styles.meta}>
          {state.latency != null ? `${state.latency} ms` : ''}{state.message ? ` · ${state.message}` : ''}
        </Text>
      </View>
      <Pressable onPress={check} style={styles.btn}>
        <Text style={styles.btnText}>Synchroniser</Text>
      </Pressable>
      <Pressable onPress={() => setHidden(true)} hitSlop={8} style={styles.close}>
        <Icon name="cancel" size={15} color={colors.textMuted} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  // Le bandeau occupe la même gouttière que le contenu des écrans ; quand il est
  // masqué (croix) il libère complètement la place.
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: sp(2),
    borderWidth: 1,
    borderRadius: 10,
    padding: sp(2.5),
    marginHorizontal: sp(3),
    marginTop: sp(3),
  },
  ok: { backgroundColor: '#ecfdf5', borderColor: '#a7f3d0' },
  warn: { backgroundColor: '#fffbeb', borderColor: '#fde68a' },
  idle: { backgroundColor: '#f1f5f9', borderColor: colors.border },
  grow: { flex: 1, minWidth: 0 },
  title: { fontSize: 13, fontWeight: '700', color: colors.text },
  meta: { fontSize: 11, color: colors.textMuted, marginTop: 1 },
  btn: { borderWidth: 1, borderColor: colors.fieldBorder, borderRadius: 8, paddingHorizontal: sp(2.5), paddingVertical: sp(1.5), backgroundColor: colors.card },
  btnText: { fontSize: 12, fontWeight: '700', color: colors.primary },
  close: { padding: sp(1) },
});
