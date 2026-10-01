// ============================================================================
// Formatage des montants et des dates (mêmes conventions que le web :
// web/src/api/db.js -> formatMoney / formatDate).
// ============================================================================

/** Nombre depuis un texte saisi au clavier (accepte la virgule décimale). */
export function toNumber(value, fallback = 0) {
  if (typeof value === 'number') return Number.isFinite(value) ? value : fallback;
  const normalized = String(value ?? '').replace(/\s/g, '').replace(',', '.');
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : fallback;
}

/** Séparateur de milliers (espace insécable comme le desktop : 12 500 FCFA). */
function grouped(amount) {
  const rounded = Math.round(Number(amount) || 0);
  const sign = rounded < 0 ? '-' : '';
  return sign + String(Math.abs(rounded)).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}

/** Montant + devise. Les centimes ne sont affichés que s'ils existent. */
export function formatMoney(amount, currency = 'FCFA') {
  const value = Number(amount) || 0;
  const hasCents = Math.abs(value - Math.round(value)) > 0.005;
  const text = hasCents
    ? `${grouped(Math.trunc(value))},${String(Math.round(Math.abs(value % 1) * 100)).padStart(2, '0')}`
    : grouped(value);
  const clean = hasCents && value < 0 ? text.replace('--', '-') : text;
  return `${clean} ${currency}`.trim();
}

/** Montant sans devise (champs de saisie, tableaux compacts). */
export function formatNumber(amount) {
  return grouped(amount);
}

/** '2026-09-23T10:12:00Z' -> '23/09/2026'. */
export function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  return `${day}/${month}/${d.getFullYear()}`;
}

/** '2026-09-23T10:12:00Z' -> '23/09/2026 10:12'. */
export function formatDateTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `${formatDate(iso)} ${hh}:${mm}`;
}

/** Bornes du jour courant (pour les statistiques de caisse). */
export function todayBounds(reference = new Date()) {
  const start = new Date(reference.getFullYear(), reference.getMonth(), reference.getDate());
  const end = new Date(start.getTime() + 24 * 60 * 60 * 1000);
  return { start: start.toISOString(), end: end.toISOString() };
}
