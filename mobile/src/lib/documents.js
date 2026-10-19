import * as Print from 'expo-print';
import * as Sharing from 'expo-sharing';
import { getBillingInfo } from '../api/settingsApi';
import { formatDate, formatMoney } from './format';

const A4 = { width: 595, height: 842 };

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));
}

function documentHtml({ kind, number, date, dueDate, customer, items = [], subtotal, discount, tax, total, paid, due, status, notes, terms, currency }) {
  const company = getBillingInfo();
  const name = company.company_name || 'Korgo Pro';
  const companyDetails = [company.address, company.phone, company.email].filter(Boolean).map(escapeHtml).join(' · ');
  const legal = [company.bp && `BP ${company.bp}`, company.ifu && `IFU ${company.ifu}`, company.rccm && `RCCM ${company.rccm}`].filter(Boolean).map(escapeHtml).join(' · ');
  const rows = items.length
    ? items.map((item, index) => {
      const quantity = Number(item.quantity) || 0;
      const unitPrice = Number(item.unit_price) || 0;
      const lineTotal = Number(item.line_total ?? quantity * unitPrice) || 0;
      return `<tr><td>${index + 1}</td><td>${escapeHtml(item.description || item.products?.name || `Article ${item.product_id || ''}`)}</td><td class="number">${escapeHtml(quantity)}</td><td class="number">${escapeHtml(formatMoney(unitPrice, currency))}</td><td class="number">${escapeHtml(formatMoney(lineTotal, currency))}</td></tr>`;
    }).join('')
    : '<tr><td colspan="5" class="empty">Aucune ligne de détail disponible</td></tr>';
  const summary = [
    ['Sous-total', subtotal],
    ['Remise', -(Number(discount) || 0)],
    ['Taxes', tax],
    ['TOTAL GÉNÉRAL', total, true],
    ...(kind === 'FACTURE' ? [['Montant payé', paid], ['Reste dû', due, true]] : []),
  ].filter(([, value]) => value !== undefined && value !== null);
  const summaryRows = summary.map(([label, value, strong]) => `<tr class="${strong ? 'strong' : ''}"><td>${label}</td><td>${escapeHtml(formatMoney(value, currency))}</td></tr>`).join('');
  const docTitle = kind === 'PROFORMA' ? 'FACTURE PROFORMA' : 'FACTURE';

  return `<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
    @page { size:A4 portrait; margin:36mm 14mm 27mm; }
    * { box-sizing:border-box; } body { margin:0; color:#1b2935; font:10pt Arial,Helvetica,sans-serif; line-height:1.4; }
    .running-header { position:fixed; top:0; left:0; right:0; height:29mm; border-bottom:1px solid #aeb8c2; }
    .brand { font-size:17pt; font-weight:700; color:#17324d; } .meta { color:#526173; font-size:8.5pt; }
    .emission { position:absolute; top:0; right:0; text-align:right; }
    .doc-title { text-align:center; margin-top:2mm; font-size:14pt; font-weight:700; letter-spacing:.3px; }
    .doc-number { text-align:center; font-weight:700; }
    .running-footer { position:fixed; bottom:0; left:0; right:0; height:20mm; border-top:1px solid #aeb8c2; padding-top:2mm; color:#526173; font-size:7.5pt; }
    .customer { margin-bottom:7mm; } .label { color:#526173; font-size:8pt; font-weight:700; text-transform:uppercase; }
    .customer-name { font-size:12pt; font-weight:700; } .subject { margin:5mm 0; }
    table { width:100%; border-collapse:collapse; } thead { display:table-header-group; } tr { page-break-inside:avoid; }
    th { padding:7px 5px; background:#edf0f2; text-align:left; font-size:8pt; border-bottom:1px solid #8795a2; }
    td { padding:7px 5px; border-bottom:1px solid #d8e0e8; vertical-align:top; } .number { text-align:right; white-space:nowrap; }
    .empty { text-align:center; color:#64748b; padding:14px; } .summary { width:58%; margin:5mm 0 0 auto; }
    .summary td { padding:5px; } .summary td:last-child { text-align:right; white-space:nowrap; }
    .summary .strong td { background:#edf0f2; font-weight:700; border-top:1px solid #172b3a; }
    .notes { margin-top:6mm; white-space:pre-wrap; } .signature { margin:17mm 0 0 auto; width:48%; text-align:center; }
    .signature-line { height:18mm; border-bottom:1px solid #526173; margin-bottom:2mm; }
  </style></head><body>
    <header class="running-header"><div class="brand">${escapeHtml(name)}</div><div class="meta">${companyDetails}</div>${legal ? `<div class="meta">${legal}</div>` : ''}
      <div class="emission meta">Émis le ${escapeHtml(formatDate(date))}${dueDate ? `<br>Valable jusqu’au ${escapeHtml(formatDate(dueDate))}` : ''}</div>
      <div class="doc-title">${docTitle}</div><div class="doc-number">N° ${escapeHtml(number)}</div>
    </header>
    <footer class="running-footer">${escapeHtml(company.invoice_footer || 'Merci de votre confiance.')}${company.payment_terms ? ` · ${escapeHtml(company.payment_terms)}` : ''}</footer>
    <main>
      <section class="customer"><div class="label">Doit</div><div class="customer-name">${escapeHtml(customer?.full_name || customer?.customer_name || 'Client de passage')}</div>
        ${customer?.company ? `<div>${escapeHtml(customer.company)}</div>` : ''}${customer?.address ? `<div class="meta">${escapeHtml(customer.address)}</div>` : ''}
        ${customer?.phone ? `<div class="meta">Tél. ${escapeHtml(customer.phone)}</div>` : ''}${customer?.email ? `<div class="meta">${escapeHtml(customer.email)}</div>` : ''}</section>
      ${notes ? `<section class="subject"><strong>Objet :</strong> ${escapeHtml(notes)}</section>` : ''}
      <table><thead><tr><th style="width:7%">N°</th><th>Désignation</th><th class="number" style="width:12%">Qté</th><th class="number" style="width:20%">Prix unit.</th><th class="number" style="width:20%">Total</th></tr></thead><tbody>${rows}</tbody></table>
      <table class="summary"><tbody>${summaryRows}</tbody></table>
      ${terms ? `<section class="notes"><strong>Conditions</strong><br>${escapeHtml(terms)}</section>` : ''}
      ${kind === 'FACTURE' ? `<section class="notes meta">Statut : ${escapeHtml(status || '')} · Mode de paiement : ${escapeHtml(paid ? 'Paiement enregistré' : 'À payer')}</section>` : ''}
      <section class="signature"><strong>Le Responsable</strong><div class="signature-line"></div><div class="meta">Date, signature et cachet</div></section>
    </main></body></html>`;
}

export function invoiceHtml(sale) {
  const currency = sale.currency || getBillingInfo().currency || 'FCFA';
  const sourceCustomer = sale.customers || {};
  return documentHtml({
    kind: 'FACTURE', number: sale.sale_number, date: sale.sale_date,
    customer: {
      ...sourceCustomer,
      full_name: [sourceCustomer.first_name, sourceCustomer.last_name].filter(Boolean).join(' ') || sourceCustomer.company || sale.customer_name,
      address: sourceCustomer.address || sale.customer_address,
      phone: sourceCustomer.phone || sale.customer_phone,
      email: sourceCustomer.email || sale.customer_email,
    },
    items: sale.items || [], subtotal: sale.subtotal ?? sale.total_amount,
    discount: sale.discount_amount, tax: sale.tax_amount, total: sale.total_amount,
    paid: sale.amount_paid, due: sale.due, status: sale.statut || sale.payment_status,
    notes: sale.notes, currency,
  });
}

export function proformaHtml(proforma) {
  const currency = proforma.currency || getBillingInfo().currency || 'FCFA';
  return documentHtml({
    kind: 'PROFORMA', number: proforma.number || proforma.proforma_number,
    date: proforma.created_date, dueDate: proforma.valid_until, customer: proforma.customer,
    items: proforma.items || [], subtotal: proforma.subtotal, discount: proforma.discount_amount,
    tax: proforma.tax_amount, total: proforma.total_amount, notes: proforma.notes,
    terms: proforma.terms_and_conditions, status: proforma.status, currency,
  });
}

export async function printHtmlDocument(html) {
  return Print.printAsync({ html, height: A4.height, orientation: Print.Orientation.portrait });
}

export async function shareHtmlDocument(html, fileName) {
  const { uri } = await Print.printToFileAsync({ html, width: A4.width, height: A4.height });
  if (!(await Sharing.isAvailableAsync())) throw new Error('Le partage de fichiers est indisponible sur cet appareil.');
  await Sharing.shareAsync(uri, { mimeType: 'application/pdf', UTI: '.pdf', dialogTitle: fileName });
  return uri;
}
