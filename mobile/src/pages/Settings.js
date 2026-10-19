// ============================================================================
// Paramètres (mobile) — miroir de web/src/pages/Settings.jsx.
// Lecture seule : valeurs effectives (env) + rappel desktop/web pour modifier.
// ============================================================================
import { useState } from 'react';
import { Alert, ScrollView, StyleSheet, Text, View } from 'react-native';
import { getBillingInfo, getSettings, saveSettings } from '../api/settingsApi';
import { useAuth } from '../context/AuthContext';
import { config } from '../config';
import { colors, sp } from '../theme';
import { Banner, Btn, Card, Field, Input, KeyValue, SectionTitle } from '../components/ui';
import Icon from '../components/Icon';

export default function SettingsScreen() {
  const settings = getSettings();
  const billing = getBillingInfo();
  const { can } = useAuth();
  const [draft, setDraft] = useState(settings);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    try {
      setSaving(true);
      await saveSettings({
        company_name: draft.company_name, address: draft.address, phone: draft.phone,
        email: draft.email, currency: draft.currency, tax_rate: Number(draft.tax_rate) || 0,
        invoice_prefix: draft.invoice_prefix, proforma_prefix: draft.proforma_prefix,
        invoice_footer: draft.invoice_footer, ifu: draft.ifu, rccm: draft.rccm, bp: draft.bp,
      });
      Alert.alert('Parametres enregistres', 'Les informations de l entreprise sont a jour.');
    } catch (e) {
      Alert.alert('Enregistrement impossible', e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      {can('manage_settings') ? (
        <Card>
          <SectionTitle>Modifier les parametres</SectionTitle>
          <Field label="NOM"><Input value={String(draft.company_name || '')} onChangeText={(v) => setDraft({ ...draft, company_name: v })} /></Field>
          <Field label="ADRESSE"><Input value={String(draft.address || '')} onChangeText={(v) => setDraft({ ...draft, address: v })} /></Field>
          <Field label="TELEPHONE"><Input value={String(draft.phone || '')} onChangeText={(v) => setDraft({ ...draft, phone: v })} /></Field>
          <Field label="EMAIL"><Input value={String(draft.email || '')} onChangeText={(v) => setDraft({ ...draft, email: v })} autoCapitalize="none" keyboardType="email-address" /></Field>
          <Field label="DEVISE"><Input value={String(draft.currency || '')} onChangeText={(v) => setDraft({ ...draft, currency: v })} /></Field>
          <Field label="TVA (%)"><Input value={String(draft.tax_rate ?? 0)} onChangeText={(v) => setDraft({ ...draft, tax_rate: v })} keyboardType="decimal-pad" /></Field>
          <Field label="PREFIXE FACTURE"><Input value={String(draft.invoice_prefix || '')} onChangeText={(v) => setDraft({ ...draft, invoice_prefix: v })} /></Field>
          <Field label="PREFIXE PROFORMA"><Input value={String(draft.proforma_prefix || '')} onChangeText={(v) => setDraft({ ...draft, proforma_prefix: v })} /></Field>
          <Field label="PIED DE FACTURE"><Input value={String(draft.invoice_footer || '')} onChangeText={(v) => setDraft({ ...draft, invoice_footer: v })} multiline /></Field>
          <Btn title="Enregistrer" onPress={save} loading={saving} style={styles.saveBtn} />
        </Card>
      ) : null}

      <Card>
        <SectionTitle>Paramètres</SectionTitle>
        <Text style={styles.meta}>Entreprise et facturation (lecture seule sur mobile).</Text>
      </Card>

      <Card>
        <SectionTitle>Informations de l'entreprise</SectionTitle>
        <KeyValue label="Nom" value={settings.company_name || '—'} />
        <KeyValue label="Devise" value={settings.currency || '—'} />
        <KeyValue label="TVA" value={`${settings.tax_rate ?? 0} %`} />
        <KeyValue label="Préfixe facture" value={settings.invoice_prefix || '—'} />
        <KeyValue label="Préfixe proforma" value={settings.proforma_prefix || '—'} />
        <KeyValue label="Pied de facture" value={settings.invoice_footer || '—'} />
      </Card>

      <Card>
        <SectionTitle>Facturation</SectionTitle>
        <KeyValue label="IFU" value={billing.ifu || '—'} />
        <KeyValue label="RCCM" value={billing.rccm || '—'} />
        <KeyValue label="BP" value={billing.bp || '—'} />
      </Card>

      <Card>
        <SectionTitle>Source mobile (.env)</SectionTitle>
        <KeyValue label="Projet" value={config.supabaseUrl || 'non configuré'} />
        <KeyValue label="Schéma" value={config.supabaseSchema || 'public'} />
        <KeyValue label="Devise" value={config.currency} />
        <KeyValue label="TVA caisse" value={`${config.taxRate} %`} />
      </Card>

      <Banner
        tone="info"
        title="Modification réservée"
        message="Modifiez les paramètres depuis desktop ou web (table/JSON entreprise)."
        icon={<Icon name="settings" size={16} color={colors.primary} />}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  content: { padding: sp(3), paddingBottom: sp(10), gap: sp(3) },
  meta: { fontSize: 13, color: colors.textMuted, marginTop: sp(1) },
  saveBtn: { marginTop: sp(1) },
});
