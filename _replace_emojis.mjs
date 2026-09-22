// Script de migration : remplace les emojis par des icônes SVG inline
// (<Icon ... />) dans tous les .jsx de web/src, contextuellement.
// Usage : node _replace_emojis.mjs   (à la racine du projet)
import fs from 'fs';
import path from 'path';

const ROOT = 'web/src';
const ICON_IMPORT = { default: "import Icon from './components/Icon';" };

const MAP = {
  '🔒': 'lock', '🖥': 'monitor', '🛰': 'globe', '👥': 'users', '📜': 'list',
  '💾': 'hardDrive', '🧹': 'broom', '🗄': 'hardDrive', '⬇': 'export',
  '⬆': 'import', '⏱': 'clock', '🕐': 'clock', '✅': 'checkCircle', '⚡': 'zap',
  '🏦': 'treasury', '💵': 'cash', '💰': 'wallet', '📱': 'phone', '🛒': 'sale',
  '📈': 'chart', '📊': 'chart', '⚠': 'alert', '🔄': 'refresh', '🧾': 'receipt',
  '📦': 'stock', '🏛': 'treasury', '🏢': 'building', '🛡': 'admin',
  '✏': 'edit', '🗑': 'delete', '✕': 'cancel', '✓': 'check', '→': 'arrowRight',
  '👋': null, // supprimé (pas d'icône équivalente)
};

// Un emoji = 1 codepoint (+ variation selector éventuel)
const EMOJI_RE = /([\u{1F000}-\u{1FAFF}\u{2190}-\u{2BFF}\u{2600}-\u{27BF}])\uFE0F?/gu;

function nameOf(match) {
  return MAP[match.replace(/\uFE0F/g, '')];
}

function iconJSX(name, size, extra) {
  const style = extra ? `, ${extra}` : '';
  return `<Icon name="${name}" size={${size}} style={{ verticalAlign: '-2px'${style} }} />`;
}

function transformLine(line) {
  if (!EMOJI_RE.test(line)) return line;
  EMOJI_RE.lastIndex = 0;

  // 1) Prop icon="emoji" (Stat) → icône composant
  if (/icon="/.test(line)) {
    line = line.replace(/icon="([^"]*)"/g, (m, inner) => {
      const n = nameOf(inner);
      return n ? `icon={<Icon name="${n}" size={22} />}` : m;
    });
  }
  // 2) Chaînes label: '...' → on retire l'emoji
  if (/label: '/.test(line)) {
    line = line.replace(EMOJI_RE, (m) => (nameOf(m) ? '' : m)).replace(/'\s+/g, "'");
  }
  // 3) Attribut placeholder="..." → on retire l'emoji
  if (/placeholder="/.test(line)) {
    line = line.replace(/placeholder="([^"]*)"/g, (m, inner) => {
      const cleaned = inner.replace(EMOJI_RE, '').replace(/^\s+/, '');
      return `placeholder="${cleaned}"`;
    });
  }
  // 4) Template literal (texte, pas de JSX) → on retire l'emoji
  if (line.includes('`')) {
    line = line.replace(/`[^`]*`/g, (m) => m.replace(EMOJI_RE, (e) => (nameOf(e) ? '' : e)));
  }
  // 5) Option de select → texte seul
  if (/<option[^>]*>/.test(line)) {
    line = line.replace(/(<option[^>]*>)[^\w{]*/g, '$1');
  }
  // 6) Titres admin-block-title → icône inline 18
  if (/admin-block-title/.test(line)) {
    line = line.replace(EMOJI_RE, (m) => {
      const n = nameOf(m);
      return n ? iconJSX(n, 18) : '';
    });
  }
  // 7) Grande icône décorative fontSize: 34
  if (/fontSize: 34/.test(line)) {
    line = line.replace(EMOJI_RE, (m) => {
      const n = nameOf(m);
      return n ? `<Icon name="${n}" size={40} />` : '';
    });
  }
  // 8) Icône seule entre deux balises (>emoji</button|span>)
  line = line.replace(/>([^<>{}\n]*)</g, (m, inner) => {
    const trimmed = inner.trim();
    const n = trimmed && EMOJI_RE.test(trimmed) ? nameOf(trimmed) : null;
    if (!n) return m;
    return `><Icon name="${n}" size={14} />`;
  });
  // 9) Reste : texte JSX → icône inline 16
  line = line.replace(EMOJI_RE, (m) => {
    const n = nameOf(m);
    return n ? iconJSX(n, 16) : '';
  });
  return line;
}

function walk(dir, out = []) {
  for (const f of fs.readdirSync(dir)) {
    const p = path.join(dir, f);
    if (fs.statSync(p).isDirectory()) walk(p, out);
    else if (f.endsWith('.jsx') && f !== 'Icon.jsx') out.push(p);
  }
  return out;
}

let changed = 0;
for (const file of walk(ROOT)) {
  const original = fs.readFileSync(file, 'utf8');
  const lines = original.split('\n').map(transformLine);
  let text = lines.join('\n');

  if (text !== original) {
    // Ajoute l'import si nécessaire
    if (!/import\s+Icon\s+from/.test(text)) {
      const rel = file.includes('components') ? "'./Icon'" : "'../components/Icon'";
      const lines2 = text.split('\n');
      const lastImport = lines2.reduce(
        (acc, l, i) => (l.startsWith('import ') ? i : acc), -1);
      lines2.splice(lastImport + 1, 0, `import Icon from ${rel};`);
      text = lines2.join('\n');
    }
    fs.writeFileSync(file, text, 'utf8');
    changed++;
    console.log(`[OK] ${file}`);
  }
}
console.log(`\n${changed} fichier(s) modifié(s).`);
