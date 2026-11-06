#!/usr/bin/env node
/**
 * Tests unitaires des fonctions de validation métier de la couche vente mobile.
 *
 * Cibles : src/api/salesApi.js
 *   - isCreditPayment(method)
 *   - saleDue(sale)
 *   - computeLine(line)
 *
 * Ces fonctions sont TESTABLES sans framework car elles n'ont pas de dépendance
 * réseau ni React Native : c'est la seule couche mobile testable sans emulator.
 *
 * Exécution : node scripts/test-mobile-sales-validation.mjs
 *
 * RÈGLE D'OR : le code testé doit correspondre au code source de production.
 * Toute divergence = une FAIL.
 */

const failures = [];
let passed = 0;

function check(label, condition, detail = '') {
  if (condition) {
    passed += 1;
    console.log(`  ✅ PASS  ${label}`);
  } else {
    failures.push(label);
    console.log(`  ❌ FAIL  ${label}${detail ? `  (${detail})` : ''}`);
  }
}

/** === isCreditPayment === */

function isCreditPayment(method) {
  const value = String(method || '').toUpperCase();
  return value === 'CRÉDIT' || value === 'CREDIT' || value === 'A_TERME';
}

const testIsCreditPayment = [
  { input: 'CRÉDIT', expected: true, label: 'CRÉDIT' },
  { input: 'CREDIT', expected: true, label: 'CREDIT' },
  { input: 'A_TERME', expected: true, label: 'A_TERME' },
  { input: 'CASH', expected: false, label: 'CASH' },
  { input: 'MOBILE_MONEY', expected: false, label: 'MOBILE_MONEY' },
  { input: 'CARD', expected: false, label: 'CARD' },
  { input: 'CRÉDIT ', expected: false, label: 'CRÉDIT avec espace (pas de trim — la fonction ne trimme pas)' },
  { input: '     ', expected: false, label: 'espace vide' },
  { input: '', expected: false, label: 'vide' },
];

console.log('\n[1] isCreditPayment(method) — retourne true pour les méthodes différées');
for (const t of testIsCreditPayment) {
  check(t.label, isCreditPayment(t.input) === t.expected,
    `got ${isCreditPayment(t.input)}, expected ${t.expected}`);
}

/** === saleDue === */

function saleDue(sale) {
  return Math.max(
    Number(sale?.total_amount || 0) - Number(sale?.amount_paid || 0),
    0
  );
}

const testSaleDue = [
  { sale: { total_amount: 100, amount_paid: 40 }, expected: 60, label: 'partiel: due = total - paid' },
  { sale: { total_amount: 100, amount_paid: 100 }, expected: 0, label: 'soldé' },
  { sale: { total_amount: 100, amount_paid: 150 }, expected: 0, label: 'surpayé (clamp à 0)' },
  { sale: { total_amount: 0, amount_paid: 0 }, expected: 0, label: 'vente nulle' },
  { sale: null, expected: 0, label: 'sale null' },
  { sale: {}, expected: 0, label: 'sale vide' },
  { sale: { total_amount: 99.99, amount_paid: 99.99 }, expected: 0, label: 'float exact (99.99)' },
  { sale: { total_amount: 100.005, amount_paid: 50 }, expected: 50.005, label: 'float général' },
];

console.log('\n[2] saleDue(sale) — reste dû = max(total - paid, 0)');
for (const t of testSaleDue) {
  check(t.label, Math.abs(saleDue(t.sale) - t.expected) < 1e-9,
    `got ${saleDue(t.sale)}, expected ${t.expected}`);
}

/** === computeLine === */

function computeLine(line) {
  const unitPrice = Number(line.unit_price) || 0;
  const quantity = Number(line.quantity) || 0;
  const discountPercent = Number(line.discount_percent) || 0;
  const lineSubtotal = unitPrice * quantity;
  const discountAmount = Number(line.discount_amount) || 0 + (lineSubtotal * discountPercent) / 100;
  const lineTotal = lineSubtotal - discountAmount;
  return { lineSubtotal, discount_amount: discountAmount, line_total: lineTotal };
}

const testComputeLine = [
  { line: { unit_price: 100, quantity: 2, discount_percent: 0, discount_amount: 0 }, expected: { lineSubtotal: 200, discount_amount: 0, line_total: 200 }, label: 'sans réduction' },
  { line: { unit_price: 100, quantity: 2, discount_percent: 10, discount_amount: 0 }, expected: { lineSubtotal: 200, discount_amount: 20, line_total: 180 }, label: '10% de réduction' },
  { line: { unit_price: 100, quantity: 3, discount_amount: 5, discount_percent: 0 }, expected: { lineSubtotal: 300, discount_amount: 5, line_total: 295 }, label: 'montant réduction fixe' },
  { line: { unit_price: 0, quantity: 5, discount_percent: 0, discount_amount: 0 }, expected: { lineSubtotal: 0, discount_amount: 0, line_total: 0 }, label: 'prix 0' },
  { line: { unit_price: 50, quantity: 0, discount_percent: 0, discount_amount: 0 }, expected: { lineSubtotal: 0, discount_amount: 0, line_total: 0 }, label: 'quantité 0' },
  { line: {}, expected: { lineSubtotal: 0, discount_amount: 0, line_total: 0 }, label: 'ligne vide' },
];

console.log('\n[3] computeLine(line) — sous-total, remise, total de la ligne');
for (const t of testComputeLine) {
  const result = computeLine(t.line);
  const ok = Math.abs(result.lineSubtotal - t.expected.lineSubtotal) < 1e-9
    && Math.abs(result.discount_amount - t.expected.discount_amount) < 1e-9
    && Math.abs(result.line_total - t.expected.line_total) < 1e-9;
  check(t.label, ok, `got ${JSON.stringify(result)}, expected ${JSON.stringify(t.expected)}`);
}

/** === Résumé === */

console.log(`\n${'='.repeat(40)}`);
console.log(`Tests ${passed + failures.length} — PASSÉS: ${passed} — ÉCHECS: ${failures.length}`);
if (failures.length > 0) {
  console.log('❌ Échecs :');
  failures.forEach(f => console.log(`   - ${f}`));
}
process.exit(failures.length === 0 ? 0 : 1);
