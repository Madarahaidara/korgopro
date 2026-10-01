// ============================================================================
// Thème mobile — palette IDENTIQUE au desktop et au web.
// Source : web/src/index.css (:root) qui reproduit les feuilles QSS du desktop
// (main.qss, login.qss, dashboard.qss, stock_view.qss).
// ============================================================================

export const colors = {
  primary: '#2F4255',        // Bleu marine principal
  primaryDark: '#1B3A7A',    // Bleu marine foncé (sélection, header)
  primarySoft: '#dbeafe',    // Fond bleu léger
  accent: '#3A6B9F',         // Accent (hover)
  success: '#10b981',
  successDark: '#059669',
  danger: '#ef4444',
  dangerDark: '#dc2626',
  warning: '#f59e0b',
  info: '#8b5cf6',
  text: '#1e293b',
  textMuted: '#475569',
  textLight: '#94a3b8',
  border: '#e2e8f0',
  fieldBorder: '#cbd5e1',
  bg: '#f8fafc',
  card: '#ffffff',
  sidebar: '#2F4255',
  sidebarText: '#dbeafe',
};

export const radius = { sm: 6, md: 8, lg: 12, xl: 16 };

/** Espacement : 4 points par unité (4 -> 16 px). */
export const sp = (n) => n * 4;

/** Styles partagés (StyleSheet.create est fait dans theme/Styles.js). */
export const baseStyles = {
  screen: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  card: {
    backgroundColor: colors.card,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: sp(4),
  },
  title: {
    fontSize: 20,
    fontWeight: '800',
    color: colors.primary,
  },
  subtitle: {
    fontSize: 13,
    color: colors.textMuted,
  },
  label: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textMuted,
    marginBottom: sp(1),
    letterSpacing: 0.4,
  },
  input: {
    // fontSize >= 16 : évite le zoom automatique d'iOS et reste lisible en caisse.
    fontSize: 16,
    color: colors.text,
    backgroundColor: colors.card,
    borderColor: colors.fieldBorder,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: sp(3),
    paddingVertical: sp(2.5),
  },
  muted: {
    fontSize: 12,
    color: colors.textLight,
  },
};
