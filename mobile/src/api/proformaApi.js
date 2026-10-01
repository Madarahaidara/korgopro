// ============================================================================
// Proformas : lecture Supabase. Miroir de web/src/api/proformaApi.js.
// Écritures : RLS admin-only -> stubs explicites (pas de RPC mobile dédiée).
// ============================================================================
import { requireClient, run } from './supabase';

export const PROFORMA_STATUS = [
  'BROUILLON',
  'EN_ATTENTE',
  'ENVOYEE',
  'ACCEPTEE',
  'REFUSEE',
  'EXPIREE',
  'CONVERTIE',
];

const COLUMNS =
  'id,proforma_number,customer_id,created_by,created_date,valid_until,subtotal,' +
  'discount_percent,discount_amount,tax_percent,tax_amount,total_amount,status,' +
  'notes,terms_and_conditions,currency,converted_to_sale_id,' +
  'customers(first_name,last_name,company)';

function enrich(row) {
  const c = row.customers || null;
  return {
    ...row,
    number: row.proforma_number,
    customer: c
      ? { full_name: [c.first_name, c.last_name].filter(Boolean).join(' ') || c.company || 'Client' }
      : null,
    items: [],
  };
}

export async function listProformas({ limit = 60 } = {}) {
  const client = requireClient();
  const rows = await run(
    client.from('proforma_invoices').select(COLUMNS).order('created_date', { ascending: false }).limit(limit)
  );
  return rows.map(enrich);
}

export async function getProforma(id) {
  const client = requireClient();
  const rows = await run(
    client.from('proforma_invoices').select(COLUMNS).eq('id', Number(id)).limit(1)
  );
  if (!rows.length) return null;
  const items = await run(
    client.from('proforma_invoice_items')
      .select('id,proforma_id,product_id,description,quantity,unit_price,discount_percent,discount_amount,line_total')
      .eq('proforma_id', Number(id))
      .order('id', { ascending: true })
  );
  return { ...enrich(rows[0]), items };
}

function blocked(label) {
  throw new Error(`${label} : réservé admin/desktop-web (RLS). Lecture seule sur mobile.`);
}

export async function createProforma() { blocked('createProforma'); }
export async function setProformaStatus() { blocked('setProformaStatus'); }
export async function convertProformaToSale() { blocked('convertProformaToSale (utilisez la caisse)'); }
