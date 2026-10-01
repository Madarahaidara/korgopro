// Valide la syntaxe (JSX + ESM) de tous les fichiers source du mobile.
const fs = require('fs');
const path = require('path');
const parser = require('./node_modules/@babel/parser');

const roots = [path.join(__dirname, 'src'), path.join(__dirname, 'App.js'), path.join(__dirname, 'index.js')];
const files = [];
(function walk(target) {
  const st = fs.statSync(target);
  if (st.isDirectory()) fs.readdirSync(target).forEach((f) => walk(path.join(target, f)));
  else if (/\.(js|jsx)$/.test(target)) files.push(target);
})(roots.length ? roots[0] : '.');
roots.slice(1).forEach((r) => files.push(r));

let bad = 0;
for (const f of files) {
  try {
    parser.parse(fs.readFileSync(f, 'utf8'), { sourceType: 'module', plugins: ['jsx', 'classProperties', 'optionalChaining', 'nullishCoalescingOperator'] });
  } catch (e) {
    bad += 1;
    console.log('FAIL ' + path.relative(__dirname, f) + ' :: ' + e.message);
  }
}
console.log((bad ? bad + ' erreur(s)' : 'OK') + ' sur ' + files.length + ' fichier(s)');
