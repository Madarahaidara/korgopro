import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { colors, sp } from '../theme';
import { printHtmlDocument, shareHtmlDocument } from '../lib/documents';
import { Banner, Btn } from './ui';

export default function DocumentActions({ html, fileName }) {
  const [action, setAction] = useState(null);
  const [error, setError] = useState('');

  const run = async (name, task) => {
    setAction(name);
    setError('');
    try {
      await task();
    } catch (e) {
      setError(e?.message || 'Le document n’a pas pu être généré.');
    } finally {
      setAction(null);
    }
  };

  if (!html) return null;

  return (
    <View style={styles.block}>
      {error ? <Banner tone="danger" title="Document indisponible" message={error} /> : null}
      <View style={styles.actions}>
        <Btn title={action === 'print' ? 'Préparation…' : 'Imprimer'} loading={action === 'print'} disabled={!!action} onPress={() => run('print', () => printHtmlDocument(html))} style={styles.button} />
        <Btn title={action === 'share' ? 'Création PDF…' : 'PDF / Partager'} variant="ghost" loading={action === 'share'} disabled={!!action} onPress={() => run('share', () => shareHtmlDocument(html, fileName))} style={styles.button} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  block: { marginTop: sp(2), paddingTop: sp(2), borderTopWidth: 1, borderTopColor: colors.border, gap: sp(2) },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: sp(2) },
  button: { flexGrow: 1, flexBasis: 140 },
});
