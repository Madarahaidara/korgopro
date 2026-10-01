import { useCallback, useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import {
  addInventoryMovement,
  getProduct,
  listInventoryMovements,
  listStockAlerts,
  searchProducts,
} from '../api/catalogApi';
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
  Loading,
  SectionTitle,
} from '../components/ui';
import { SuccessOverlay } from '../components/Feedback';
import { config } from '../config';
import { useAuth } from '../context/AuthContext';
import { useStores } from '../context/StoreContext';
import { formatDateTime, formatMoney, toNumber } from '../lib/format';
import { colors, sp } from '../theme';

/** Types de mouvement (identiques au dialogue desktop NewMovementDialog). */
const MOVEMENT_TYPES = [
  { value: 'IN', label: 'Entrée' },
  { value: 'OUT', label: 'Sortie' },
  { value: 'ADJUST', label: 'Ajustement +' },
  { value: 'LOSS', label: 'Perte' },
];

/** Raisons proposées par le desktop (stock_view.py). */
const REASONS = [
  'Achat fournisseur',
  'Vente client',
  'Transfert',
  'Inventaire',
  'Dons/Cadeaux',
  'Échantillons',
  'Détérioration',
  'Autre',
];

const MOVEMENT_LABELS = {
  IN: 'Entrée',
  OUT: 'Sortie',
  ADJUST: 'Ajustement',
  LOSS: 'Perte',
  RETURN: 'Retour',
};

/**
 * Écran Inventaire (terrain) — consultation du stock + mouvements.
 *
 * Équivalent mobile de ui/views/stock_view.py (NewMovementDialog) :
 *   * IN / ADJUST  -> quantité ajoutée ;
 *   * OUT / LOSS   -> quantité retirée (refusée si stock insuffisant) ;
 *   * chaque opération crée une ligne `inventory_movements` et met à jour
 *     products.quantity, côté serveur (RPC app_stock_movement).
 */
export default function InventaireScreen() {
  const { can } = useAuth();
  const { activeId, activeStore } = useStores();
  const canView = can('view_stock');
  const canManage = can('manage_stock');

  const [mode, setMode] = useState('search');
  const [query, setQuery] = useState('');
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [movements, setMovements] = useState([]);
  const [type, setType] = useState('IN');
  const [quantity, setQuantity] = useState('');
  const [unitCost, setUnitCost] = useState('');
  const [reason, setReason] = useState(REASONS[0]);
  const [reference, setReference] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [validation, setValidation] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const currency = config.currency;

  // --- Liste des produits (recherche ou alertes) -------------------------
  useEffect(() => {
    if (!canView) return undefined;
    let cancelled = false;
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const rows =
          mode === 'alerts'
            ? await listStockAlerts({ storeId: activeId, limit: 200 })
            : await searchProducts({ storeId: activeId, query, limit: 40 });
        if (!cancelled) setProducts(rows);
      } catch (e) {
        if (!cancelled) {
          setFeedback({ tone: 'danger', title: 'Chargement impossible', message: e.message });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query, mode, activeId, canView, refreshKey]);

  // --- Détail du produit sélectionné ------------------------------------
  const loadDetail = useCallback(
    async (productId) => {
      try {
        const [fresh, history] = await Promise.all([
          getProduct(productId),
          listInventoryMovements(productId, 8),
        ]);
        if (fresh) setSelected(fresh);
        setMovements(history);
      } catch (e) {
        setFeedback({ tone: 'danger', title: 'Détail indisponible', message: e.message });
      }
    },
    []
  );

  useEffect(() => {
    if (selected?.id) loadDetail(selected.id);
  }, [selected?.id, loadDetail]);

  const pick = (product) => {
    setSelected(product);
    setQuantity('');
    setUnitCost(String(Math.round(product.purchase_price) || ''));
    setReference('');
    setNotes('');
    setFeedback(null);
  };

  // --- Enregistrement d'un mouvement -------------------------------------
  const submit = async () => {
    if (!selected) return;
    const value = Math.abs(toNumber(quantity));
    if (value <= 0) {
      setFeedback({ tone: 'danger', title: 'Quantité invalide', message: 'Saisissez une quantité supérieure à 0.' });
      return;
    }

    setSaving(true);
    setFeedback(null);
    try {
      const result = await addInventoryMovement({
        productId: selected.id,
        type,
        quantity: value,
        reason,
        unitCost: type === 'IN' || type === 'ADJUST' ? toNumber(unitCost) : null,
        reference: reference || null,
        notes: notes || null,
        storeId: activeId,
      });

      const summary = {
        tone: 'success',
        title: `${MOVEMENT_LABELS[type] || type} enregistrée`,
        message: `Nouveau stock de « ${result.product_name} » : ${result.new_quantity}`,
      };
      setFeedback(summary);
      // Confirmation animée (coche + carte qui « pop ») côté terrain.
      setValidation(summary);
      setQuantity('');
      setNotes('');
      setReference('');
      setRefreshKey((v) => v + 1);
      await loadDetail(selected.id);
    } catch (e) {
      setFeedback({ tone: 'danger', title: 'Mouvement refusé', message: e.message });
    } finally {
      setSaving(false);
    }
  };

  if (!canView) {
    return (
      <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
        <Banner
          tone="warning"
          title="Accès refusé"
          message="Votre rôle ne donne pas accès au stock (permission « view_stock »)."
        />
      </ScrollView>
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
          Stock du magasin
        </SectionTitle>
        <ChipGroup
          options={[
            { value: 'search', label: 'Recherche' },
            { value: 'alerts', label: 'Alertes stock' },
          ]}
          value={mode}
          onChange={(v) => {
            setMode(v);
            setProducts([]);
          }}
        />
        {mode === 'search' ? (
          <Input
            style={styles.search}
            value={query}
            onChangeText={setQuery}
            placeholder="Nom, code ou code-barres…"
            autoCapitalize="none"
            autoCorrect={false}
            returnKeyType="search"
          />
        ) : (
          <Text style={styles.hint}>
            Produits dont la quantité est inférieure ou égale au seuil minimum.
          </Text>
        )}
      </Card>

      {feedback ? (
        <Banner tone={feedback.tone} title={feedback.title} message={feedback.message} />
      ) : null}

      {selected ? (
        <Card>
          <SectionTitle
            right={
              <Btn
                variant="ghost"
                title="Fermer"
                onPress={() => setSelected(null)}
                style={styles.smallBtn}
              />
            }
          >
            {selected.name}
          </SectionTitle>
          <KeyValue label="Code" value={selected.code || '—'} />
          <KeyValue label="Stock" value={`${selected.quantity} unité(s)`} strong />
          <KeyValue label="Seuil minimum" value={String(selected.min_stock ?? '—')} />
          <KeyValue label="Prix d'achat" value={formatMoney(selected.purchase_price, currency)} />
          <KeyValue label="Prix de vente" value={formatMoney(selected.sale_price, currency)} />
          <KeyValue label="Valeur du stock" value={formatMoney(selected.stockValue, currency)} />
          <KeyValue label="Emplacement" value={selected.location || '—'} />

          {!canManage ? (
            <Banner
              tone="info"
              title="Consultation seule"
              message="Votre rôle ne permet pas de modifier le stock (permission « manage_stock »)."
            />
          ) : (
            <>
              <Field label="TYPE DE MOUVEMENT">
                <ChipGroup options={MOVEMENT_TYPES} value={type} onChange={setType} />
              </Field>
              <Field
                label="QUANTITÉ"
                hint={
                  type === 'IN' || type === 'ADJUST'
                    ? 'Ajoutée au stock existant.'
                    : 'Retirée du stock (refusée si insuffisant).'
                }
              >
                <Input
                  value={quantity}
                  onChangeText={setQuantity}
                  keyboardType="numeric"
                  placeholder="0"
                />
              </Field>
              {type === 'IN' || type === 'ADJUST' ? (
                <Field label="COÛT UNITAIRE" hint="Laisser vide pour reprendre le prix d'achat.">
                  <Input
                    value={unitCost}
                    onChangeText={setUnitCost}
                    keyboardType="numeric"
                    placeholder={String(Math.round(selected.purchase_price) || 0)}
                  />
                </Field>
              ) : null}
              <Field label="RAISON">
                <ChipGroup
                  options={REASONS.map((r) => ({ value: r, label: r }))}
                  value={reason}
                  onChange={setReason}
                />
              </Field>
              <Field label="RÉFÉRENCE (FACULTATIF)">
                <Input
                  value={reference}
                  onChangeText={setReference}
                  placeholder="BL n°, facture…"
                />
              </Field>
              <Field label="NOTE (FACULTATIF)">
                <Input
                  value={notes}
                  onChangeText={setNotes}
                  placeholder="Précision sur le mouvement"
                />
              </Field>
              <Btn
                title="Enregistrer le mouvement"
                variant="success"
                onPress={submit}
                loading={saving}
                style={styles.fullBtn}
              />
            </>
          )}

          <SectionTitle style={styles.historyTitle}>Derniers mouvements</SectionTitle>
          {movements.length === 0 ? (
            <Empty title="Aucun mouvement" hint="Ce produit n'a pas encore d'historique." />
          ) : null}
          {movements.map((m) => (
            <View key={m.id} style={styles.movementRow}>
              <View style={styles.grow}>
                <Text style={styles.movementTitle}>
                  {MOVEMENT_LABELS[m.movement_type] || m.movement_type} · {m.quantity} u
                </Text>
                <Text style={styles.movementMeta}>
                  {formatDateTime(m.date)} · {m.reason || '—'}
                </Text>
              </View>
              {m.total_value ? (
                <Text style={styles.movementValue}>{formatMoney(m.total_value, currency)}</Text>
              ) : null}
            </View>
          ))}
        </Card>
      ) : null}

      <Card>
        <SectionTitle>{mode === 'alerts' ? 'Produits en alerte' : 'Produits'}</SectionTitle>
        {loading ? <Loading label="Chargement du stock…" /> : null}
        {!loading && products.length === 0 ? (
          <Empty
            title={mode === 'alerts' ? 'Aucune alerte' : 'Aucun produit trouvé'}
            hint={
              mode === 'alerts'
                ? 'Tous les produits sont au-dessus de leur seuil minimum.'
                : 'Vérifiez le magasin actif ou élargissez la recherche.'
            }
          />
        ) : null}
        {products.map((p) => (
          <Pressable key={p.id} style={styles.productRow} onPress={() => pick(p)}>
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
  search: { marginTop: sp(3) },
  hint: { fontSize: 12, color: colors.textLight, marginTop: sp(2) },
  historyTitle: { marginTop: sp(4) },
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
  movementRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: sp(2),
    paddingVertical: sp(2),
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  movementTitle: { fontSize: 13, fontWeight: '600', color: colors.text },
  movementMeta: { fontSize: 11, color: colors.textMuted, marginTop: sp(0.5) },
  movementValue: { fontSize: 13, fontWeight: '700', color: colors.primary },
  grow: { flex: 1, minWidth: 0 },
  smallBtn: { minHeight: 36, paddingHorizontal: sp(3) },
  fullBtn: { width: '100%', marginTop: sp(2) },
});
