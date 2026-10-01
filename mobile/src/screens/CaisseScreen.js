import { useCallback, useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { searchCustomers, searchProducts } from '../api/catalogApi';
import { createSale, isCreditPayment, listSalesToday } from '../api/salesApi';
import { listAccounts } from '../api/treasuryApi';
import {
  Badge,
  Banner,
  Btn,
  Card,
  ChipGroup,
  Empty,
  Field,
  Input,
  KeyValue,
  SectionTitle,
} from '../components/ui';
import { PulseOnChange, SuccessOverlay } from '../components/Feedback';
import { config } from '../config';
import { useAuth } from '../context/AuthContext';
import { useStores } from '../context/StoreContext';
import { formatMoney, toNumber } from '../lib/format';
import { colors, radius, sp } from '../theme';

/** Moyens de paiement. « CRÉDIT » est la valeur exacte attendue par le desktop. */
const PAYMENT_METHODS = [
  { value: 'CASH', label: 'Espèces' },
  { value: 'MOBILE_MONEY', label: 'Mobile Money' },
  { value: 'CARD', label: 'Carte' },
  { value: 'CRÉDIT', label: 'Crédit' },
];

/**
 * Écran Caisse — équivalent mobile de web/src/components/NewSaleModal.jsx :
 * recherche produit, panier, remise globale, moyen de paiement, monnaie rendue.
 *
 * L'enregistrement passe par la RPC `app_create_sale` : contrôle du stock,
 * numéro de facture, trésorerie et journal sont faits côté serveur, dans une
 * seule transaction.
 */
export default function CaisseScreen() {
  const { can } = useAuth();
  const { activeId, activeStore } = useStores();
  const canSell = can('create_sales');

  const [query, setQuery] = useState('');
  const [products, setProducts] = useState([]);
  const [searching, setSearching] = useState(false);
  const [lines, setLines] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [accountId, setAccountId] = useState(null);
  const [customerQuery, setCustomerQuery] = useState('');
  const [customers, setCustomers] = useState([]);
  const [customer, setCustomer] = useState(null);
  const [showCustomers, setShowCustomers] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState('CASH');
  const [discount, setDiscount] = useState('');
  const [amountPaid, setAmountPaid] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [validation, setValidation] = useState(null);
  const [stats, setStats] = useState({ count: 0, total: 0, due: 0 });
  const [refreshKey, setRefreshKey] = useState(0);

  const currency = config.currency;

  // --- Statistiques du jour (bandeau haut) --------------------------------
  const loadStats = useCallback(async () => {
    if (!canSell || activeId == null) return;
    try {
      const sales = await listSalesToday(activeId);
      setStats({
        count: sales.length,
        total: sales.reduce((sum, s) => sum + s.total_amount, 0),
        due: sales.reduce((sum, s) => sum + s.due, 0),
      });
    } catch (e) {
      // Bandeau secondaire : une erreur ici ne doit pas bloquer la caisse.
      setStats({ count: 0, total: 0, due: 0 });
    }
  }, [activeId, canSell]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  // --- Recherche produits (débounce 300 ms, côté serveur) ----------------
  useEffect(() => {
    if (!canSell) return undefined;
    let cancelled = false;
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const rows = await searchProducts({ storeId: activeId, query, limit: 20 });
        if (!cancelled) setProducts(rows);
      } catch (e) {
        if (!cancelled) {
          setFeedback({ tone: 'danger', title: 'Recherche impossible', message: e.message });
        }
      } finally {
        if (!cancelled) setSearching(false);
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query, activeId, canSell, refreshKey]);

  // --- Comptes de trésorerie (compte d'encaissement) ---------------------
  useEffect(() => {
    if (!canSell) return;
    (async () => {
      try {
        const rows = await listAccounts();
        setAccounts(rows);
        const preferred =
          rows.find((a) => a.is_default) ||
          rows.find((a) => a.account_type === 'CASH') ||
          rows[0];
        setAccountId(preferred ? preferred.id : null);
      } catch (e) {
        // Non bloquant : la RPC choisira elle-même le compte de caisse.
        setAccounts([]);
      }
    })();
  }, [canSell]);

  // --- Recherche clients (pour les ventes à crédit) ----------------------
  useEffect(() => {
    if (!showCustomers) return undefined;
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const rows = await searchCustomers({ query: customerQuery, limit: 15 });
        if (!cancelled) setCustomers(rows);
      } catch (e) {
        if (!cancelled) {
          setFeedback({ tone: 'danger', title: 'Clients indisponibles', message: e.message });
        }
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [customerQuery, showCustomers]);

  // --- Panier ------------------------------------------------------------
  const addToCart = (product) => {
    if (product.isOutOfStock) {
      setFeedback({
        tone: 'warning',
        title: 'Rupture de stock',
        message: `« ${product.name} » n'a plus de stock.`,
      });
      return;
    }
    const existing = lines.find((l) => l.product_id === product.id);
    if (existing) {
      if (existing.quantity + 1 > existing.max_qty) {
        setFeedback({
          tone: 'warning',
          title: 'Stock insuffisant',
          message: `Seulement ${existing.max_qty} unité(s) de « ${product.name} ».`,
        });
        return;
      }
      setLines(
        lines.map((l) =>
          l.product_id === product.id ? { ...l, quantity: l.quantity + 1 } : l
        )
      );
    } else {
      setLines([
        ...lines,
        {
          product_id: product.id,
          name: product.name,
          code: product.code,
          unit_price: Number(product.sale_price) || 0,
          quantity: 1,
          max_qty: product.quantity || 0,
        },
      ]);
    }
    setQuery('');
    setFeedback(null);
  };

  const changeQuantity = (productId, delta) => {
    const line = lines.find((l) => l.product_id === productId);
    if (!line) return;
    const next = line.quantity + delta;
    if (next < 1) return;
    if (next > line.max_qty) {
      setFeedback({
        tone: 'warning',
        title: 'Stock insuffisant',
        message: `Seulement ${line.max_qty} unité(s) de « ${line.name} ».`,
      });
      return;
    }
    setLines(lines.map((l) => (l.product_id === productId ? { ...l, quantity: next } : l)));
  };

  const changePrice = (productId, value) => {
    const price = Math.max(toNumber(value), 0);
    setLines(
      lines.map((l) => (l.product_id === productId ? { ...l, unit_price: price } : l))
    );
  };

  const removeLine = (productId) => setLines(lines.filter((l) => l.product_id !== productId));

  // --- Totaux (mêmes règles que le web : voir NewSaleModal.jsx) ------------
  // « CRÉDIT » : le montant saisi est un simple acompte (vide = vente à terme).
  // « CASH »    : le montant saisi est celui reçu (monnaie rendue s'il dépasse).
  // Les autres moyens (Mobile Money, carte) sont réputés immédiats.
  const subtotal = lines.reduce((sum, l) => sum + l.unit_price * l.quantity, 0);
  const discountValue = Math.min(Math.max(toNumber(discount), 0), subtotal);
  const taxable = subtotal - discountValue;
  const tax = (taxable * (config.taxRate || 0)) / 100;
  const total = taxable + tax;
  const credit = isCreditPayment(paymentMethod);
  const entered = Math.max(toNumber(amountPaid), 0);
  const paid = paymentMethod === 'CASH' || credit ? entered : total;
  const change = Math.max(paid - total, 0);
  const due = Math.max(total - paid, 0);
  const isDeferred = paymentMethod === 'CASH' || credit;

  const resetCart = () => {
    setLines([]);
    setDiscount('');
    setAmountPaid('');
    setNotes('');
    setCustomer(null);
    setCustomerQuery('');
    setShowCustomers(false);
    setPaymentMethod('CASH');
  };

  const save = async () => {
    if (!lines.length) {
      setFeedback({ tone: 'danger', title: 'Panier vide', message: 'Ajoutez au moins un produit.' });
      return;
    }
    if (paymentMethod === 'CASH' && paid > 0 && paid < total) {
      setFeedback({
        tone: 'danger',
        title: 'Montant insuffisant',
        message: 'Le montant reçu est inférieur au total.',
      });
      return;
    }
    if (credit && !customer) {
      setFeedback({
        tone: 'danger',
        title: 'Client requis',
        message: 'Une vente à crédit doit être rattachée à un client.',
      });
      return;
    }
    if (credit && paid > total) {
      setFeedback({
        tone: 'danger',
        title: 'Acompte trop élevé',
        message: "L'acompte ne peut pas dépasser le total de la vente.",
      });
      return;
    }

    setSaving(true);
    setFeedback(null);
    try {
      const result = await createSale({
        items: lines.map((l) => ({
          product_id: l.product_id,
          quantity: l.quantity,
          unit_price: l.unit_price,
        })),
        storeId: activeId,
        customerId: customer ? customer.id : null,
        discountAmount: discountValue,
        taxAmount: tax,
        paymentMethod,
        amountPaid: paid,
        notes,
        accountId,
      });

      const summary = {
        tone: 'success',
        title: `Vente ${result.sale_number} enregistrée`,
        message:
          result.change_amount > 0
            ? `Monnaie à rendre : ${formatMoney(result.change_amount, currency)}`
            : Number(result.due || 0) > 0
              ? `Vente à crédit. Reste dû : ${formatMoney(result.due, currency)}`
              : `Total encaissé : ${formatMoney(result.total_amount, currency)}`,
      };
      setFeedback(summary);
      // Confirmation animée (coche + carte qui « pop ») visible au comptoir.
      setValidation(summary);
      resetCart();
      setRefreshKey((v) => v + 1);
      loadStats();
    } catch (e) {
      setFeedback({ tone: 'danger', title: 'Vente non enregistrée', message: e.message });
    } finally {
      setSaving(false);
    }
  };

  if (!canSell) {
    return (
      <View style={styles.screen}>
        <ScrollView contentContainerStyle={styles.content}>
          <Banner
            tone="warning"
            title="Accès refusé"
            message={
              "Votre rôle ne permet pas d'encaisser des ventes " +
              '(permission « create_sales » absente de la matrice).'
            }
          />
        </ScrollView>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
    >
      <Card>
        <SectionTitle right={<Badge text={activeStore?.name || 'Magasin —'} tone="info" />}>
          Caisse du jour
        </SectionTitle>
        <View style={styles.statsRow}>
          <View style={styles.statBox}>
            <Text style={styles.statValue}>{stats.count}</Text>
            <Text style={styles.statLabel}>Ventes</Text>
          </View>
          <View style={styles.statBox}>
            <PulseOnChange value={stats.total}>
              <Text style={styles.statValue}>{formatMoney(stats.total, currency)}</Text>
            </PulseOnChange>
            <Text style={styles.statLabel}>Total</Text>
          </View>
          <View style={styles.statBox}>
            <Text style={styles.statValue}>{formatMoney(stats.due, currency)}</Text>
            <Text style={styles.statLabel}>À encaisser</Text>
          </View>
        </View>
      </Card>

      {feedback ? (
        <Banner tone={feedback.tone} title={feedback.title} message={feedback.message} />
      ) : null}

      <Card>
        <SectionTitle>1. Produits</SectionTitle>
        <Input
          value={query}
          onChangeText={setQuery}
          placeholder="Nom, code ou code-barres…"
          autoCapitalize="none"
          autoCorrect={false}
          returnKeyType="search"
        />
        {searching ? <Text style={styles.hint}>Recherche…</Text> : null}
        {!searching && products.length === 0 ? (
          <Empty
            title="Aucun produit trouvé"
            hint="Vérifiez le magasin actif ou élargissez la recherche."
          />
        ) : null}
        {products.map((p) => (
          <Pressable key={p.id} style={styles.productRow} onPress={() => addToCart(p)}>
            <View style={styles.grow}>
              <Text style={styles.productName} numberOfLines={1}>
                {p.name}
              </Text>
              <Text style={styles.productMeta}>
                {p.code} · {formatMoney(p.sale_price, currency)}
              </Text>
            </View>
            <Badge
              text={p.isOutOfStock ? 'Rupture' : `${p.quantity} u`}
              tone={p.isOutOfStock ? 'danger' : p.isLowStock ? 'warning' : 'success'}
            />
          </Pressable>
        ))}
      </Card>

      <Card>
        <SectionTitle right={<Badge text={`${lines.length} ligne(s)`} />}>2. Panier</SectionTitle>
        {lines.length === 0 ? (
          <Empty title="Panier vide" hint="Touchez un produit ci-dessus pour l'ajouter." />
        ) : null}

        {lines.map((l) => (
          <View key={l.product_id} style={styles.lineRow}>
            <View style={styles.grow}>
              <Text style={styles.productName} numberOfLines={1}>
                {l.name}
              </Text>
              <Text style={styles.productMeta}>Stock disponible : {l.max_qty}</Text>
              <View style={styles.lineControls}>
                <Pressable style={styles.qtyBtn} onPress={() => changeQuantity(l.product_id, -1)}>
                  <Text style={styles.qtyBtnText}>−</Text>
                </Pressable>
                <Text style={styles.qtyValue}>{l.quantity}</Text>
                <Pressable style={styles.qtyBtn} onPress={() => changeQuantity(l.product_id, +1)}>
                  <Text style={styles.qtyBtnText}>+</Text>
                </Pressable>
                <Input
                  style={styles.priceInput}
                  value={String(l.unit_price)}
                  onChangeText={(v) => changePrice(l.product_id, v)}
                  keyboardType="numeric"
                />
              </View>
            </View>
            <View style={styles.lineRight}>
              <Text style={styles.lineTotal}>
                {formatMoney(l.unit_price * l.quantity, currency)}
              </Text>
              <Pressable onPress={() => removeLine(l.product_id)}>
                <Text style={styles.removeText}>Retirer</Text>
              </Pressable>
            </View>
          </View>
        ))}
      </Card>

      <Card>
        <SectionTitle
          right={
            <Btn
              variant="ghost"
              title={showCustomers ? 'Fermer' : 'Choisir'}
              onPress={() => setShowCustomers((v) => !v)}
              style={styles.smallBtn}
            />
          }
        >
          3. Client
        </SectionTitle>
        <Text style={styles.customerName}>
          {customer ? customer.full_name : 'Client de passage'}
        </Text>
        {customer && Number(customer.balance) > 0 ? (
          <Text style={styles.productMeta}>
            Solde dû actuel : {formatMoney(customer.balance, currency)}
          </Text>
        ) : null}
        {showCustomers ? (
          <>
            <Input
              value={customerQuery}
              onChangeText={setCustomerQuery}
              placeholder="Nom, téléphone, société…"
              autoCorrect={false}
            />
            {customers.map((c) => (
              <Pressable
                key={c.id}
                style={styles.productRow}
                onPress={() => {
                  setCustomer(c);
                  setShowCustomers(false);
                }}
              >
                <View style={styles.grow}>
                  <Text style={styles.productName} numberOfLines={1}>
                    {c.full_name}
                  </Text>
                  <Text style={styles.productMeta}>{c.phone || c.mobile || c.code || ''}</Text>
                </View>
              </Pressable>
            ))}
            {customer ? (
              <Btn
                variant="ghost"
                title="Retirer le client"
                onPress={() => setCustomer(null)}
                style={styles.fullBtn}
              />
            ) : null}
          </>
        ) : null}
      </Card>

      <Card>
        <SectionTitle>4. Paiement</SectionTitle>
        <Field label="MOYEN DE PAIEMENT">
          <ChipGroup
            options={PAYMENT_METHODS}
            value={paymentMethod}
            onChange={setPaymentMethod}
          />
        </Field>

        {accounts.length > 0 ? (
          <Field label="COMPTE D'ENCAISSEMENT" hint="Trésorerie créditée par cette vente.">
            <ChipGroup
              options={accounts.map((a) => ({ value: a.id, label: a.name }))}
              value={accountId}
              onChange={setAccountId}
            />
          </Field>
        ) : null}

        <Field label="REMISE GLOBALE">
          <Input
            value={discount}
            onChangeText={setDiscount}
            keyboardType="numeric"
            placeholder="0"
          />
        </Field>

        {isDeferred ? (
          <Field
            label={credit ? 'ACOMPTE REÇU' : 'MONTANT REÇU'}
            hint={
              credit
                ? 'Laisser vide pour une vente à terme (reste dû enregistré sur le client).'
                : 'Laisser vide pour un paiement exact.'
            }
          >
            <Input
              value={amountPaid}
              onChangeText={setAmountPaid}
              keyboardType="numeric"
              placeholder={credit ? '0' : String(Math.round(total))}
            />
          </Field>
        ) : null}

        <Field label="NOTE (FACULTATIF)">
          <Input value={notes} onChangeText={setNotes} placeholder="Vente comptoir…" />
        </Field>

        <View style={styles.totals}>
          <KeyValue label="Sous-total" value={formatMoney(subtotal, currency)} />
          {discountValue > 0 ? (
            <KeyValue label="Remise" value={`- ${formatMoney(discountValue, currency)}`} />
          ) : null}
          {tax > 0 ? (
            <KeyValue label={`TVA (${config.taxRate} %)`} value={formatMoney(tax, currency)} />
          ) : null}
          <KeyValue label="TOTAL" value={formatMoney(total, currency)} strong />
          {change > 0 ? (
            <KeyValue label="Monnaie à rendre" value={formatMoney(change, currency)} strong />
          ) : null}
          {credit && lines.length > 0 ? (
            <KeyValue
              label={due > 0 ? 'Reste dû (crédit)' : 'Crédit soldé'}
              value={due > 0 ? formatMoney(due, currency) : 'Aucun'}
              strong
            />
          ) : null}
        </View>

        <Btn
          title={
            credit
              ? `Vendre à crédit ${due > 0 ? formatMoney(due, currency) : ''}`
              : `Encaisser ${total > 0 ? formatMoney(total, currency) : ''}`
          }
          variant={credit ? 'primary' : 'success'}
          onPress={save}
          loading={saving}
          disabled={lines.length === 0}
          style={styles.fullBtn}
        />
      </Card>

      {/* Confirmation animée : coche + carte qui « pop » après validation. */}
      <SuccessOverlay
        visible={!!validation}
        tone={validation?.tone || 'success'}
        title={validation?.title}
        message={validation?.message}
        onClose={() => setValidation(null)}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  content: { padding: sp(3), paddingBottom: sp(10) },
  statsRow: { flexDirection: 'row', gap: sp(2) },
  statBox: {
    flex: 1,
    backgroundColor: colors.bg,
    borderRadius: radius.md,
    padding: sp(2.5),
    alignItems: 'center',
  },
  statValue: { fontSize: 14, fontWeight: '800', color: colors.primary, textAlign: 'center' },
  statLabel: { fontSize: 11, color: colors.textMuted, marginTop: sp(0.5) },
  productRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: sp(2),
    paddingVertical: sp(2.5),
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  productName: { fontSize: 15, fontWeight: '600', color: colors.text },
  productMeta: { fontSize: 12, color: colors.textMuted, marginTop: sp(0.5) },
  lineRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: sp(2),
    paddingVertical: sp(2.5),
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  lineControls: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: sp(2),
    marginTop: sp(2),
  },
  qtyBtn: {
    width: 44,
    height: 44,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.fieldBorder,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.card,
  },
  qtyBtnText: { fontSize: 20, fontWeight: '800', color: colors.primary },
  qtyValue: { minWidth: 28, textAlign: 'center', fontSize: 16, fontWeight: '700' },
  priceInput: { flex: 1, minWidth: 90, paddingVertical: sp(1.5), textAlign: 'right' },
  lineRight: { alignItems: 'flex-end', gap: sp(1) },
  lineTotal: { fontSize: 14, fontWeight: '800', color: colors.primary },
  removeText: { fontSize: 12, color: colors.danger, fontWeight: '700' },
  customerName: { fontSize: 15, fontWeight: '600', color: colors.text },
  grow: { flex: 1, minWidth: 0 },
  hint: { fontSize: 12, color: colors.textLight, marginTop: sp(1.5) },
  smallBtn: { minHeight: 36, paddingHorizontal: sp(3) },
  fullBtn: { width: '100%', marginTop: sp(2) },
  totals: { marginTop: sp(2), marginBottom: sp(2) },
});
