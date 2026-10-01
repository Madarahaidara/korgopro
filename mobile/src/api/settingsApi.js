// ============================================================================
// Paramètres entreprise (mobile). Miroir de web/src/api/settingsApi.js.
//
// Pas de table `settings` exposée en Supabase : les valeurs viennent de
// mobile/.env (devise/TVA) + lecture du magasin actif. Lecture seule.
// ============================================================================
import { config } from '../config';

const DEFAULTS = {
  company_name: 'Korgo Pro',
  currency: 'FCFA',
  tax_rate: 0,
  invoice_prefix: 'FAC',
  proforma_prefix: 'PRO',
  invoice_footer: 'Merci de votre confiance.',
};

/** Paramètres effectifs (env + défauts web-compatibles). */
export function getSettings() {
  return {
    ...DEFAULTS,
    company_name: 'Korgo Pro',
    currency: config.currency || DEFAULTS.currency,
    tax_rate: Number(config.taxRate) || 0,
  };
}

export function saveSettings() {
  throw new Error('saveSettings : paramètres modifiables depuis desktop/web uniquement.');
}

export function getBillingInfo() {
  const s = getSettings();
  return { ...s, ifu: '', rccm: '', bp: '' };
}

export async function listActivityLogs() {
  return [];
}

export async function logActivity() {
  // No-op mobile : journal réservé admin (RLS).
}
