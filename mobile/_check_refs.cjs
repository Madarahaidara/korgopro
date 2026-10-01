// Vérifie les références aux jeux de valeurs : icônes (Icon.js) et palette (theme.js).
const fs = require('fs');
const path = require('path');

const SRC = path.join(__dirname, 'src');
const files = [];
(function walk(t) {
  fs.statSync(t).isDirectory()
    ? fs.readdirSync(t).forEach((f) => walk(path.join(t, f)))
    : /\.(js|jsx)$/.test(t) && files.push(t);
})(SRC);

const iconSrc = fs.readFileSync(path.join(SRC, 'components', 'Icon.js'), 'utf8');
const iconNames = new Set();
for (const m of iconSrc.matchAll(/case '([A-Za-z]+)':/g)) iconNames.add(m[1]);

const themeSrc = fs.readFileSync(path.join(SRC, 'theme.js'), 'utf8');
const themeKeys = new Set();
// Récupère les clés des objets exportés (colors, radius, baseStyles…), que
// l'objet soit sur plusieurs lignes ou sur une seule.
for (const obj of themeSrc.matchAll(/export const [A-Za-z0-9_]+ = \{([\s\S]*?)\n?\};/g)) {
  // Les commentaires peuvent contenir des virgules : on les retire d'abord.
  const body = obj[1].replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');
  for (const raw of body.split(',')) {
    const key = raw.split(':')[0].trim().replace(/^['"]|['"]$/g, '');
    if (/^[A-Za-z][A-Za-z0-9_]*$/.test(key)) themeKeys.add(key);
  }
}

let problems = 0;
for (const f of files) {
  const rel = path.relative(__dirname, f);
  const code = fs.readFileSync(f, 'utf8');
  if (f !== path.join(SRC, 'components', 'Icon.js')) {
    for (const m of code.matchAll(/<Icon\b[^>]*?name=(?:"([A-Za-z]+)"|'([A-Za-z]+)')/g)) {
      const used = m[1] || m[2];
      if (!iconNames.has(used)) {
        problems += 1;
        console.log('ICONE INCONNUE  ' + rel + ' -> ' + used);
      }
    }
  }
  for (const m of code.matchAll(/\bcolors\.([A-Za-z0-9_]+)/g)) {
    if (!themeKeys.has(m[1]) && f !== path.join(SRC, 'theme.js')) {
      problems += 1;
      console.log('COULEUR INCONNUE ' + rel + ' -> colors.' + m[1]);
    }
  }
  for (const m of code.matchAll(/\bradius\.([A-Za-z0-9_]+)/g)) {
    if (!themeKeys.has(m[1])) {
      problems += 1;
      console.log('RADIUS INCONNU  ' + rel + ' -> radius.' + m[1]);
    }
  }
}
console.log((problems ? problems + ' problème(s)' : 'OK') + ' — références vérifiées (' + iconNames.size + ' icônes, thème: ' + [...themeKeys].join(',') + ')');
