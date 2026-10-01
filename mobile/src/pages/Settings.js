// ============================================================================
// Paramètres (mobile) — miroir de web/src/pages/Settings.jsx.
// Lecture seule : valeurs effectives (env) + rappel desktop/web pour modifier.
// ============================================================================
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { getBillingInfo, getSettings } from '../api/settingsApi';
import { config } from '../config';
import { colors, sp } from '../theme';
import { Banner, Card, KeyValue, SectionTitle } from '../components/ui';
import Icon from '../components/Icon';

export default function SettingsScreen() {
  const settings = getSettings();
  const billing = getBillingInfo();

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
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
});
