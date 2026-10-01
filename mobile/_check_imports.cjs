// Vérifie que chaque import local pointe vers un export qui existe vraiment.
const fs = require('fs');
const path = require('path');
const parser = require('./node_modules/@babel/parser');
const traverse = require('./node_modules/@babel/traverse').default;

const SRC = path.join(__dirname, 'src');
const files = [];
(function walk(t) {
  fs.statSync(t).isDirectory()
    ? fs.readdirSync(t).forEach((f) => walk(path.join(t, f)))
    : /\.(js|jsx)$/.test(t) && files.push(t);
})(SRC);
files.push(path.join(__dirname, 'App.js'));

function exportsOf(code) {
  const names = new Set();
  const ast = parser.parse(code, { sourceType: 'module', plugins: ['jsx'] });
  traverse(ast, {
    ExportNamedDeclaration(p) {
      const d = p.node.declaration;
      if (d && d.type === 'VariableDeclaration') d.declarations.forEach((v) => v.id && names.add(v.id.name));
      else if (d && d.id) names.add(d.id.name);
      (p.node.specifiers || []).forEach((s) => names.add(s.exported.name));
    },
    ExportDefaultDeclaration() { names.add('default'); },
    ExportAllDeclaration(p) { names.add('*' + (p.node.source && p.node.source.value)); },
  });
  return names;
}

const cache = new Map();
function resolve(from, spec) {
  const base = path.resolve(path.dirname(from), spec);
  for (const cand of [base, base + '.js', base + '.jsx', path.join(base, 'index.js'), path.join(base, 'index.jsx')]) {
    if (fs.existsSync(cand) && fs.statSync(cand).isFile()) return cand;
  }
  return null;
}

let problems = 0;
for (const f of files) {
  const code = fs.readFileSync(f, 'utf8');
  const ast = parser.parse(code, { sourceType: 'module', plugins: ['jsx'] });
  traverse(ast, {
    ImportDeclaration(p) {
      const spec = p.node.source.value;
      if (!spec.startsWith('.')) return;
      const target = resolve(f, spec);
      if (!target) {
        problems += 1;
        console.log('MISSING FILE  ' + path.relative(__dirname, f) + ' -> ' + spec);
        return;
      }
      if (!cache.has(target)) cache.set(target, exportsOf(fs.readFileSync(target, 'utf8')));
      const available = cache.get(target);
      for (const s of p.node.specifiers) {
        if (s.type === 'ImportNamespaceSpecifier') continue;
        const needed = s.type === 'ImportDefaultSpecifier' ? 'default' : s.imported.name;
        if (available.has(needed) || [...available].some((a) => a.startsWith('*'))) continue;
        problems += 1;
        console.log('MISSING EXPORT ' + path.relative(__dirname, f) + ' importe ' + needed + ' de ' + spec);
      }
    },
  });
}
console.log((problems ? problems + ' problème(s)' : 'OK') + ' — imports vérifiés dans ' + files.length + ' fichier(s)');
