// ============================================================================
// Composants d'interface réutilisables (mobile) — conformes au design system web.
// ============================================================================
import React, { useRef } from 'react';
import {
  ActivityIndicator,
  Animated,
  Modal as RNModal,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import Icon from './Icon';
import { AnimatedCheck, FadeSlideIn } from './Feedback';
import { colors, radius, sp } from '../theme';

/** Conteneur d'écran (fond gris clair + padding homogène). */
export function Screen({ children, style }) {
  return <View style={[styles.screen, style]}>{children}</View>;
}

export function Card({ children, style }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

export function SectionTitle({ children, right, style }) {
  return (
    <View style={[styles.sectionTitle, style]}>
      {typeof children === 'string' ? (
        <Text style={styles.sectionTitleText}>{children}</Text>
      ) : (
        children
      )}
      {right}
    </View>
  );
}

export function Divider() {
  return <View style={styles.divider} />;
}

/** Champ de formulaire : libellé + contenu + aide éventuelle. */
export function Field({ label, hint, children }) {
  return (
    <View style={styles.field}>
      {label ? <Text style={styles.label}>{label}</Text> : null}
      {children}
      {hint ? <Text style={styles.hint}>{hint}</Text> : null}
    </View>
  );
}

/** Champ texte (clavier configurable). */
export function Input({ value, onChangeText, style, ...rest }) {
  return (
    <TextInput
      value={value}
      onChangeText={onChangeText}
      placeholderTextColor={colors.textLight}
      style={[styles.input, style]}
      {...rest}
    />
  );
}

const BUTTON_VARIANTS = {
  primary: { bg: colors.primary, text: '#ffffff', border: colors.primary },
  success: { bg: colors.success, text: '#ffffff', border: colors.success },
  danger: { bg: colors.card, text: colors.danger, border: '#f3c9c9' },
  ghost: { bg: colors.card, text: colors.text, border: colors.border },
  // .btn-logout (web) : fond bleu clair, texte et bordure bleu marine.
  logout: { bg: '#dbeafe', text: '#2F4255', border: '#2F4255' },
};

/**
 * Bouton conforme aux styles web (.btn, .btn-primary, .btn-success,
 * .btn-danger, .btn-sm). Micro-animation d'appui : légère compression puis
 * retour élastique (transform + native driver, sans impact sur la mise en page).
 */
export function Btn({ title, onPress, variant = 'primary', disabled, loading, style, textStyle }) {
  const theme = BUTTON_VARIANTS[variant] || BUTTON_VARIANTS.primary;
  const inactive = disabled || loading;
  const scale = useRef(new Animated.Value(1)).current;
  const bounce = (toValue, bounciness, speed) =>
    Animated.spring(scale, { toValue, useNativeDriver: true, speed, bounciness }).start();

  return (
    <Animated.View style={[styles.btnWrap, { transform: [{ scale }] }]}>
      <Pressable
        onPress={inactive ? undefined : onPress}
        onPressIn={inactive ? undefined : () => bounce(0.96, 0, 30)}
        onPressOut={inactive ? undefined : () => bounce(1, 10, 18)}
        style={({ pressed }) => [
          styles.btn,
          { backgroundColor: theme.bg, borderColor: theme.border },
          pressed && !inactive ? styles.btnPressed : null,
          inactive ? styles.btnDisabled : null,
          style,
        ]}
      >
        {loading ? (
          <ActivityIndicator color={theme.text} size="small" />
        ) : (
          <Text style={[styles.btnText, { color: theme.text }, textStyle]} numberOfLines={1}>
            {title}
          </Text>
        )}
      </Pressable>
    </Animated.View>
  );
}

/** Sélecteur en « puces » */
export function ChipGroup({ options, value, onChange }) {
  return (
    <View style={styles.chipRow}>
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <Pressable
            key={String(option.value)}
            onPress={() => onChange(option.value)}
            style={[styles.chip, selected ? styles.chipSelected : null]}
          >
            <Text style={[styles.chipText, selected ? styles.chipTextSelected : null]} numberOfLines={1}>
              {option.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

/** Badges strictement identiques à web/src/components/ui.jsx */
export function Badge({ text, status, tone }) {
  const val = String(text || status || '').toUpperCase();
  const success = ['ACTIF', 'PAID', 'PAYEE', 'COMPLETED', 'EMISE', 'ACCEPTEE', 'ACTIVE', 'EN_STOCK', 'RESOLU'];
  const danger = ['INACTIF', 'EXPIRED', 'REFUSEE', 'ANNULEE', 'RUPTURE', 'DESACTIVE', 'OUT_OF_STOCK', 'EN_RETARD', 'NON_PAYEE', 'IMPAYÉ'];
  const warning = ['EN_ATTENTE', 'BROUILLON', 'PENDING', 'PARTIELLEMENT', 'PARTIEL', 'ENVOYEE', 'LOW_STOCK', 'LOW'];
  const info = ['CONVERTIE', 'EN_ATTENTE_RECU', 'ADMIN', 'GESTIONNAIRE', 'CAISSIER'];

  let bg = '#eef0f3';
  let color = colors.textMuted;

  if (tone === 'success' || success.includes(val)) {
    bg = '#d1fae5';
    color = '#065f46';
  } else if (tone === 'danger' || danger.includes(val)) {
    bg = '#fee2e2';
    color = '#991b1b';
  } else if (tone === 'warning' || warning.includes(val)) {
    bg = '#fef3c7';
    color = '#92400e';
  } else if (tone === 'info' || info.includes(val)) {
    bg = '#ede9fe';
    color = '#6d28d9';
  } else if (tone === 'primary') {
    bg = colors.primarySoft;
    color = colors.primary;
  }

  return (
    <View style={[styles.badge, { backgroundColor: bg }]}>
      <Text style={[styles.badgeText, { color }]}>{text || status || '—'}</Text>
    </View>
  );
}

/** Message d'information / erreur conforme à web/src/index.css (.alert, .login-error) */
export function Banner({ tone = 'info', title, message, onAction, actionLabel, icon }) {
  const colorsByTone = {
    danger: { bg: '#fef2f2', border: '#fecaca', title: '#991b1b', text: '#dc2626' },
    warning: { bg: '#fffbeb', border: '#fde68a', title: '#92400e', text: '#b45309' },
    success: { bg: '#ecfdf5', border: '#a7f3d0', title: '#065f46', text: '#047857' },
    info: { bg: '#eff6ff', border: '#bfdbfe', title: '#1e40af', text: '#1d4ed8' },
  };
  const c = colorsByTone[tone] || colorsByTone.info;
  // Les messages de succès (action validée) reçoivent une coche animée ;
  // le bandeau entre en fondu + glissement à chaque nouveau message.
  const resolvedIcon = icon || (tone === 'success' ? <AnimatedCheck size={22} /> : null);

  return (
    <FadeSlideIn trigger={`${tone}|${title || ''}|${message || ''}`}>
      <View style={[styles.banner, { backgroundColor: c.bg, borderColor: c.border }]}>
        {resolvedIcon ? <View style={styles.bannerIcon}>{resolvedIcon}</View> : null}
        {title ? <Text style={[styles.bannerTitle, { color: c.title }]}>{title}</Text> : null}
        {message ? <Text style={[styles.bannerText, { color: c.text }]}>{message}</Text> : null}
        {onAction && actionLabel ? (
          <Btn title={actionLabel} onPress={onAction} variant="ghost" style={styles.bannerBtn} />
        ) : null}
      </View>
    </FadeSlideIn>
  );
}

export function Empty({ title, hint }) {
  return (
    <View style={styles.empty}>
      <Text style={styles.emptyTitle}>{title}</Text>
      {hint ? <Text style={styles.emptyHint}>{hint}</Text> : null}
    </View>
  );
}

export function Loading({ label = 'Chargement…' }) {
  return (
    <View style={styles.loading}>
      <ActivityIndicator color={colors.primary} size="small" />
      <Text style={styles.emptyHint}>{label}</Text>
    </View>
  );
}

/** Ligne clé/valeur compacte (totaux, récapitulatifs). */
export function KeyValue({ label, value, strong }) {
  return (
    <View style={styles.kv}>
      <Text style={[styles.kvLabel, strong ? styles.kvStrongLabel : null]}>{label}</Text>
      <Text style={[styles.kvValue, strong ? styles.kvStrongValue : null]}>{value}</Text>
    </View>
  );
}

/** Modale réutilisable conforme à web/src/components/ui.jsx (.modal) */
export function Modal({ visible, title, onClose, children }) {
  return (
    <RNModal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.modalOverlay}>
        <View style={styles.modalContent}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>{title}</Text>
            <Pressable onPress={onClose} style={styles.modalCloseBtn} hitSlop={8}>
              <Icon name="cancel" size={16} color={colors.textMuted} />
            </Pressable>
          </View>
          <View style={styles.modalBody}>{children}</View>
        </View>
      </View>
    </RNModal>
  );
}
/** Élément de liste standard avec icône, titre, sous-titre et action/badge à droite */
export function ListItem({ title, subtitle, meta, right, icon, onPress, active, style }) {
  const content = (
    <View style={[styles.listItem, active ? styles.listItemActive : null, style]}>
      {icon ? <View style={styles.listItemIcon}>{icon}</View> : null}
      <View style={styles.listItemContent}>
        <Text style={[styles.listItemTitle, active ? styles.listItemTitleActive : null]} numberOfLines={1}>
          {title}
        </Text>
        {subtitle ? <Text style={styles.listItemSubtitle} numberOfLines={1}>{subtitle}</Text> : null}
        {meta ? <Text style={styles.listItemMeta} numberOfLines={1}>{meta}</Text> : null}
      </View>
      {right ? <View style={styles.listItemRight}>{right}</View> : null}
    </View>
  );

  if (onPress) {
    return (
      <Pressable onPress={onPress} style={({ pressed }) => [pressed ? styles.listItemPressed : null]}>
        {content}
      </Pressable>
    );
  }
  return content;
}

/** Statistique sous forme de carte (.stat-card) */
export function Stat({ icon, label, value, color = colors.primary, style }) {
  return (
    <View style={[styles.statCard, style]}>
      {icon ? (
        <View style={[styles.statIcon, { backgroundColor: `${color}1f` }]}>
          {icon}
        </View>
      ) : null}
      <View style={styles.statContent}>
        <Text style={styles.statValue} numberOfLines={1}>{value}</Text>
        <Text style={styles.statLabel} numberOfLines={1}>{label}</Text>
      </View>
    </View>
  );
}

/** Alias miroir web : Stat == StatCard (web/components/ui.jsx Stat). */
export const StatCard = Stat;

/** Confirmation de suppression — miroir web ConfirmDelete. */
export function ConfirmDelete({ message = 'Confirmer la suppression ?', onConfirm, onCancel }) {
  return (
    <Modal visible title="Confirmation" onClose={onCancel}>
      <Text style={styles.confirmText}>{message}</Text>
      <View style={styles.confirmActions}>
        <Btn title="Annuler" variant="ghost" onPress={onCancel} style={styles.confirmBtn} />
        <Btn title="Supprimer" variant="danger" onPress={onConfirm} style={styles.confirmBtn} />
      </View>
    </Modal>
  );
}

/** Toast minimal (miroir web toast()) : bannière succès/error éphémère. */
let toastTimer = null;
export function toast(message, type = 'success') {
  if (toastTimer) {
    clearTimeout(toastTimer);
    toastTimer = null;
  }
  // Pas de DOM en natif : on log + on laisse les écrans afficher un Banner.
  // Conservé pour parité d'API avec web/components/ui.jsx.
  // eslint-disable-next-line no-console
  console.log(`[toast:${type}] ${message}`);
}




const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  card: {
    backgroundColor: colors.card,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: sp(3.5),
    marginBottom: sp(3),
    shadowColor: '#101828',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  sectionTitle: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: sp(2),
  },
  sectionTitleText: { fontSize: 15, fontWeight: '700', color: colors.primary },
  divider: { height: 1, backgroundColor: colors.border, marginVertical: sp(2.5) },
  field: { marginBottom: sp(3) },
  label: {
    fontSize: 11,
    fontWeight: '600',
    color: '#374151',
    marginBottom: sp(1.5),
    letterSpacing: 0.8,
    textTransform: 'uppercase',
  },
  hint: { fontSize: 12, color: colors.textLight, marginTop: sp(1) },
  input: {
    fontSize: 14,
    color: colors.text,
    backgroundColor: '#f9fafb',
    borderColor: '#e5e7eb',
    borderWidth: 2,
    borderRadius: 10,
    paddingHorizontal: sp(3.5),
    paddingVertical: sp(2.5),
  },
  btn: {
    minHeight: 42,
    paddingHorizontal: sp(3.5),
    borderRadius: 8,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnWrap: { alignSelf: 'stretch', justifyContent: 'center' },
  btnPressed: { opacity: 0.85 },
  btnDisabled: { opacity: 0.5 },
  btnText: { fontSize: 14, fontWeight: '600' },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: sp(2) },
  chip: {
    paddingHorizontal: sp(3),
    paddingVertical: sp(1.5),
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.fieldBorder,
    backgroundColor: colors.card,
  },
  chipSelected: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { fontSize: 13, fontWeight: '600', color: colors.textMuted },
  chipTextSelected: { color: '#ffffff' },
  badge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 999,
  },
  badgeText: { fontSize: 12, fontWeight: '700' },
  banner: {
    borderWidth: 1,
    borderRadius: 10,
    padding: sp(3),
    marginBottom: sp(3),
  },
  bannerIcon: { marginBottom: sp(1) },
  bannerTitle: { fontSize: 13, fontWeight: '700', marginBottom: sp(0.5) },
  bannerText: { fontSize: 13, lineHeight: 18 },
  bannerBtn: { marginTop: sp(2), minHeight: 36 },
  empty: { padding: sp(6), alignItems: 'center' },
  emptyTitle: { fontSize: 15, fontWeight: '700', color: colors.textMuted },
  emptyHint: {
    fontSize: 13,
    color: colors.textLight,
    marginTop: sp(1.5),
    textAlign: 'center',
  },
  loading: { padding: sp(6), alignItems: 'center', gap: sp(2) },
  kv: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: sp(1.5),
    gap: sp(3),
  },
  kvLabel: { fontSize: 13, color: colors.textMuted },
  kvValue: { fontSize: 13, fontWeight: '600', color: colors.text },
  kvStrongLabel: { fontSize: 14, fontWeight: '800', color: colors.text },
  kvStrongValue: { fontSize: 18, fontWeight: '800', color: colors.primary },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(15, 23, 42, 0.45)',
    justifyContent: 'center',
    padding: 20,
  },
  modalContent: {
    backgroundColor: '#ffffff',
    borderRadius: 14,
    maxHeight: '90%',
    overflow: 'hidden',
    shadowColor: '#101828',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.16,
    shadowRadius: 30,
    elevation: 8,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  modalTitle: { fontSize: 16, fontWeight: '700', color: colors.text },
  modalCloseBtn: {
    width: 30,
    height: 30,
    borderRadius: 8,
    backgroundColor: '#f3f4f6',
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalBody: { padding: 20 },
  listItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: sp(2.5),
    paddingVertical: sp(2.5),
    paddingHorizontal: sp(2),
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  listItemActive: { backgroundColor: colors.primarySoft, borderRadius: radius.md },
  listItemPressed: { opacity: 0.7 },
  listItemIcon: { justifyContent: 'center', alignItems: 'center' },
  listItemContent: { flex: 1, minWidth: 0 },
  listItemTitle: { fontSize: 14, fontWeight: '600', color: colors.text },
  listItemTitleActive: { color: colors.primary, fontWeight: '700' },
  listItemSubtitle: { fontSize: 12, color: colors.textMuted, marginTop: 2 },
  listItemMeta: { fontSize: 11, color: colors.textLight, marginTop: 1 },
  listItemRight: { alignItems: 'flex-end', justifyContent: 'center' },
  statCard: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: sp(3),
    flexDirection: 'row',
    alignItems: 'center',
    gap: sp(3),
  },
  statIcon: {
    width: 44,
    height: 44,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  statContent: { flex: 1, minWidth: 0 },
  statValue: { fontSize: 20, fontWeight: '800', color: colors.primary },
  statLabel: { fontSize: 12, fontWeight: '500', color: colors.textMuted, marginTop: 2 },
  confirmText: { fontSize: 14, color: colors.text, marginBottom: sp(3) },
  confirmActions: { flexDirection: 'row', gap: sp(2), justifyContent: 'flex-end' },
  confirmBtn: { minWidth: 110 },

});
