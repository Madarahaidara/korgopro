// ============================================================================
// Données de démonstration
// ============================================================================
import { db, ensureStores } from './db';

export function seedDatabase() {
  const d = ensureStores(db.data);

  if (!(d.suppliers || []).length) {
    d.suppliers = [
      { id: 1, code: 'FRN-0001', name: 'Distri Central SA', contact_person: 'Jean Mensah', email: 'contact@districentral.com', city: 'Cotonou', country: 'Bénin', active: true },
      { id: 2, code: 'FRN-0002', name: 'Fournitures Afrique', contact_person: 'Aïcha Soumaila', email: 'ventes@fournitures-afrique.com', city: 'Cotonou', country: 'Bénin', active: true },
      { id: 3, code: 'FRN-0003', name: 'Tech Import SARL', contact_person: 'Karim Diallo', email: 'info@techimport.com', city: 'Abomey-Calavi', country: 'Bénin', active: true },
    ];
  }

  if (!(d.products || []).length) {
    d.products = [
      { id: 1, code: 'PRD-0001', name: 'Riz parfumé 25kg', category: 'ALIMENTATION', quantity: 120, min_stock: 20, max_stock: 300, purchase_price: 14000, sale_price: 16500, supplier_id: 1, active: true },
      { id: 2, code: 'PRD-0002', name: 'Huile végétale 5L', category: 'ALIMENTATION', quantity: 45, min_stock: 15, max_stock: 150, purchase_price: 5000, sale_price: 6200, supplier_id: 1, active: true },
      { id: 3, code: 'PRD-0003', name: 'Eau minérale 1,5L', category: 'BOISSON', quantity: 300, min_stock: 50, max_stock: 600, purchase_price: 1800, sale_price: 2200, supplier_id: 2, active: true },
      { id: 4, code: 'PRD-0004', name: 'Lait concentré sucré', category: 'ALIMENTATION', quantity: 8, min_stock: 20, max_stock: 200, purchase_price: 850, sale_price: 1000, supplier_id: 2, active: true },
      { id: 5, code: 'PRD-0005', name: 'Smartphone Android', category: 'ELECTRONIQUE', quantity: 0, min_stock: 5, max_stock: 30, purchase_price: 55000, sale_price: 75000, supplier_id: 3, active: true },
      { id: 6, code: 'PRD-0006', name: 'Savon de toilette', category: 'COSMETIQUE', quantity: 90, min_stock: 25, max_stock: 200, purchase_price: 2100, sale_price: 2800, supplier_id: 2, active: true },
    ];
  }

if (!(d.customers || []).length) {
    d.customers = [
      { id: 1, code: 'CLI-0001', first_name: 'Awa', last_name: 'Dossou', company: 'Restaurant Chez Awa', email: 'awa@chezawa.com', phone: '+229 04 44 44 44', city: 'Cotonou', country: 'Bénin', customer_type: 'WHOLESALE', credit_limit: 500000, loyalty_points: 120, active: true },
      { id: 2, code: 'CLI-0002', first_name: 'Paul', last_name: 'Kpadonou', company: '', email: 'paul.k@mail.com', phone: '+229 05 55 55 55', city: 'Porto-Novo', country: 'Bénin', customer_type: 'RETAIL', credit_limit: 0, loyalty_points: 45, active: true },
      { id: 3, code: 'CLI-0003', first_name: 'Fatou', last_name: 'Ouedraogo', company: 'Superette Fatou', email: 'fatou@superette.com', phone: '+229 06 66 66 66', city: 'Cotonou', country: 'Bénin', customer_type: 'CORPORATE', credit_limit: 1000000, loyalty_points: 300, active: true },
    ];
  }

  if (!(d.treasuryAccounts || []).length) {
    d.treasuryAccounts = [
      { id: 1, name: 'Caisse principale', account_type: 'CASH', currency: 'FCFA', initial_balance: 0, current_balance: 350000, is_default: true, notes: 'Caisse du magasin' },
      { id: 2, name: 'Compte bancaire BOA', account_type: 'BANK', currency: 'FCFA', initial_balance: 0, current_balance: 2500000, bank_name: 'BOA', account_number: 'BOA-000123456789' },
      { id: 3, name: 'MTN Mobile Money', account_type: 'MOBILE_MONEY', currency: 'FCFA', initial_balance: 0, current_balance: 120000, phone_number: '+229 97 00 00 00' },
    ];
  }

  if (!(d.sales || []).length) {
    const now = Date.now();
    const sale = (num, daysAgo, customer_id, total) => {
      d.sales.push({
        id: num,
        number: `FAC-${String(num).padStart(4, '0')}`,
        customer_id,
        cashier_id: 3,
        sale_date: new Date(now - daysAgo * 86400000).toISOString(),
        subtotal: total,
        discount_amount: 0,
        tax_amount: 0,
        total_amount: total,
        amount_paid: total,
        change_amount: 0,
        payment_method: 'CASH',
        payment_status: 'PAID',
        sale_status: 'COMPLETED',
        type_document: 'FACTURE',
        statut: 'EMISE',
        currency: 'FCFA',
        items: [],
      });
    };
    sale(1, 6, 1, 16500);
    sale(2, 6, null, 2200);
    sale(3, 5, 2, 6200);
    sale(4, 4, null, 33000);
    sale(5, 4, 3, 150000);
    sale(6, 3, null, 2800);
    sale(7, 2, 1, 75000);
    sale(8, 2, null, 4400);
    sale(9, 1, null, 16500);
    sale(10, 1, 2, 6200);
  }

  if (!(d.proformas || []).length) {
    const now = Date.now();
    d.proformas = [
      { id: 1, number: 'PRO-0001', customer_id: 3, created_by: 2, created_date: new Date(now - 3 * 86400000).toISOString(), valid_until: new Date(now + 12 * 86400000).toISOString(), subtotal: 90000, discount_percent: 5, discount_amount: 4500, tax_percent: 20, tax_amount: 17100, total_amount: 102600, status: 'EN_ATTENTE', currency: 'FCFA', items: [] },
      { id: 2, number: 'PRO-0002', customer_id: 1, created_by: 2, created_date: new Date(now - 1 * 86400000).toISOString(), valid_until: new Date(now + 15 * 86400000).toISOString(), subtotal: 33000, discount_percent: 0, discount_amount: 0, tax_percent: 20, tax_amount: 6600, total_amount: 39600, status: 'BROUILLON', currency: 'FCFA', items: [] },
    ];
  }

  if (!(d.treasuryMovements || []).length && d.sales.length) {
    d.sales.forEach((s) => {
      d.treasuryMovements.push({
        id: s.id,
        account_id: 1,
        movement_type: 'IN',
        amount: s.total_amount,
        date: s.sale_date,
        reference: s.number,
        description: `Vente ${s.number}`,
        category: 'Ventes',
        reference_type: 'SALE',
        reference_id: s.id,
      });
    });
  }

  if (!(d.activityLogs || []).length) {
    d.activityLogs = [
      { id: 1, user: 'admin', action: 'Initialisation de la base de démonstration', timestamp: new Date().toISOString() },
    ];
  }
  // Rattache les entités créées par le seed au magasin principal.
  ensureStores(d);
  db.persist();
  return d;
}