// ============================================================================
// Animations de retour utilisateur (mobile) — API `Animated` du cœur React
// Native (react-native), avec `useNativeDriver` pour opacité / transformation.
//
// Aucune dépendance native supplémentaire n'est requise (pas de worklets ni de
// plugin Babel) : ces animations fonctionnent telles quelles dans l'APK terrain
// comme dans Expo Go.
//
//   * FadeSlideIn    : entrée douce (fondu + glissement) — utilisée par les
//                      bandeaux et les messages de validation/erreur ;
//   * AnimatedCheck  : pastille avec coche qui surgit en ressort ;
//   * SuccessOverlay : confirmation plein écran après une action validée
//                      (vente, encaissement, mouvement de stock, annulation) ;
//   * PulseOnChange  : pulsation discrète d'une valeur qui vient de changer.
// ============================================================================
import { useCallback, useEffect, useRef } from 'react';
import {
  Animated,
  Easing,
  Modal as RNModal,
  Pressable,
  StyleSheet,
  Text,
} from 'react-native';
import Icon from './Icon';
import { colors, sp } from '../theme';

/** Couleur de la pastille selon le ton du message. */
export const TONE_COLORS = {
  success: colors.success,
  danger: colors.danger,
  warning: colors.warning,
  info: colors.primary,
  primary: colors.primary,
};

/**
 * Entrée animée : fondu + glissement vertical (220 ms par défaut).
 * `trigger` relance l'animation quand le contenu change (nouveau message).
 */
export function FadeSlideIn({ children, style, fromY = -10, duration = 220, delay = 0, trigger }) {
  const progress = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    progress.setValue(0);
    const animation = Animated.sequence([
      Animated.delay(delay),
      Animated.timing(progress, {
        toValue: 1,
        duration,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: true,
      }),
    ]);
    animation.start();
    return () => animation.stop();
  }, [progress, duration, delay, trigger]);

  return (
    <Animated.View
      style={[
        style,
        {
          opacity: progress,
          transform: [
            {
              translateY: progress.interpolate({
                inputRange: [0, 1],
                outputRange: [fromY, 0],
              }),
            },
          ],
        },
      ]}
    >
      {children}
    </Animated.View>
  );
}

/**
 * Coche de validation animée : apparition en ressort (scale 0 -> 1) + fondu.
 * Utilisée seule (en-tête de bandeau) ou au centre du `SuccessOverlay`.
 */
export function AnimatedCheck({ size = 72, tone = 'success', icon = 'check', delay = 0, style }) {
  const pop = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    pop.setValue(0);
    const animation = Animated.sequence([
      Animated.delay(delay),
      Animated.spring(pop, { toValue: 1, useNativeDriver: true, speed: 12, bounciness: 14 }),
    ]);
    animation.start();
    return () => animation.stop();
  }, [pop, delay]);

  const background = TONE_COLORS[tone] || TONE_COLORS.success;

  return (
    <Animated.View
      style={[
        styles.check,
        {
          width: size,
          height: size,
          borderRadius: size / 2,
          backgroundColor: background,
          opacity: pop,
          transform: [{ scale: pop }],
        },
        style,
      ]}
    >
      <Icon name={icon} size={Math.round(size * 0.5)} color="#ffffff" strokeWidth={3} />
    </Animated.View>
  );
}

/**
 * Confirmation plein écran après une action validée : fond assombri, carte qui
 * « pop » (ressort) et coche animée. Se ferme au toucher ou automatiquement
 * après `autoHide` millisecondes — l'opérateur peut toucher l'écran pour
 * fermer immédiatement et enchaîner la vente suivante.
 */
export function SuccessOverlay({
  visible,
  title,
  message,
  tone = 'success',
  icon = 'check',
  autoHide = 1800,
  onClose,
}) {
  const fade = useRef(new Animated.Value(0)).current;
  const pop = useRef(new Animated.Value(0)).current;
  const closing = useRef(false);

  const hide = useCallback(() => {
    if (closing.current) return;
    closing.current = true;
    Animated.parallel([
      Animated.timing(fade, { toValue: 0, duration: 160, useNativeDriver: true }),
      Animated.timing(pop, { toValue: 0, duration: 140, useNativeDriver: true }),
    ]).start(() => {
      closing.current = false;
      if (onClose) onClose();
    });
  }, [fade, pop, onClose]);

  useEffect(() => {
    if (!visible) return undefined;
    closing.current = false;
    fade.setValue(0);
    pop.setValue(0);
    Animated.parallel([
      Animated.timing(fade, {
        toValue: 1,
        duration: 180,
        easing: Easing.out(Easing.quad),
        useNativeDriver: true,
      }),
      Animated.spring(pop, { toValue: 1, useNativeDriver: true, speed: 11, bounciness: 12 }),
    ]).start();
    const timer = setTimeout(hide, autoHide);
    return () => clearTimeout(timer);
  }, [visible, autoHide, fade, pop, hide]);

  if (!visible) return null;

  return (
    <RNModal visible transparent animationType="none" statusBarTranslucent onRequestClose={hide}>
      <Pressable style={styles.overlayPress} onPress={hide}>
        <Animated.View style={[styles.overlayBackdrop, { opacity: fade }]} />
        <Animated.View
          style={[
            styles.overlayCard,
            {
              opacity: pop,
              transform: [
                { scale: pop.interpolate({ inputRange: [0, 1], outputRange: [0.85, 1] }) },
                { translateY: pop.interpolate({ inputRange: [0, 1], outputRange: [18, 0] }) },
              ],
            },
          ]}
        >
          <AnimatedCheck size={74} tone={tone} icon={icon} delay={80} />
          {title ? <Text style={styles.overlayTitle}>{title}</Text> : null}
          {message ? <Text style={styles.overlayMessage}>{message}</Text> : null}
          <Text style={styles.overlayHint}>Touchez pour continuer</Text>
        </Animated.View>
      </Pressable>
    </RNModal>
  );
}

/** Pulsation discrète d'un bloc dont la valeur vient de changer (totaux…). */
export function PulseOnChange({ children, value, style, scaleTo = 1.06 }) {
  const pulse = useRef(new Animated.Value(1)).current;
  const mounted = useRef(false);

  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true;
      return undefined;
    }
    const animation = Animated.sequence([
      Animated.timing(pulse, { toValue: scaleTo, duration: 120, useNativeDriver: true }),
      Animated.spring(pulse, { toValue: 1, useNativeDriver: true, speed: 14, bounciness: 6 }),
    ]);
    animation.start();
    return () => animation.stop();
  }, [value, pulse, scaleTo]);

  return <Animated.View style={[style, { transform: [{ scale: pulse }] }]}>{children}</Animated.View>;
}

const styles = StyleSheet.create({
  check: { alignItems: 'center', justifyContent: 'center' },
  overlayPress: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: sp(6),
  },
  overlayBackdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(15, 23, 42, 0.55)',
  },
  overlayCard: {
    minWidth: 240,
    maxWidth: '100%',
    backgroundColor: colors.card,
    borderRadius: 16,
    paddingHorizontal: sp(6),
    paddingVertical: sp(7),
    alignItems: 'center',
    shadowColor: '#101828',
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.24,
    shadowRadius: 32,
    elevation: 10,
  },
  overlayTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: colors.text,
    textAlign: 'center',
    marginTop: sp(4),
  },
  overlayMessage: {
    fontSize: 13,
    lineHeight: 19,
    color: colors.textMuted,
    textAlign: 'center',
    marginTop: sp(1.5),
  },
  overlayHint: {
    fontSize: 11,
    color: colors.textLight,
    textAlign: 'center',
    marginTop: sp(4),
    letterSpacing: 0.4,
  },
});

export default SuccessOverlay;
