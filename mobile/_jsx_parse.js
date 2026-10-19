// -*- coding: utf-8 -*-
// Parse a JSX file with the project's @babel/parser (Metro-compatible).
const fs = require('fs');
const path = require('path');
let parser;
try {
  parser = require('@babel/parser');
} catch (e) {
  console.log('NO_BABEL', e.message);
  process.exit(2);
}
const files = process.argv.slice(2);
let bad = 0;
for (const f of files) {
  const code = fs.readFileSync(f, 'utf8');
  try {
    parser.parse(code, { sourceType: 'module', plugins: ['jsx', 'typescript'] });
    console.log('OK  ', f);
  } catch (e) {
    console.log('FAIL', f, '->', e.message);
    bad++; 
  }
}
process.exit(bad ? 1 : 0);
