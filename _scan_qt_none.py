"""Scan : QTableWidgetItem/setText avec argument attribute non protege."""
import io, re, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

pat_item = re.compile(
    r'QTableWidgetItem\(\s*([A-Za-z_][\w]*(?:\.\w+)+)\s*\)')
pat_settext = re.compile(r'\.setText\(\s*([A-Za-z_][\w]*(?:\.\w+)+)\s*\)')
hits = []
for p in Path('ui').rglob('*.py'):
    for n, line in enumerate(p.read_text(encoding='utf-8', errors='ignore').splitlines(), 1):
        for m in pat_item.finditer(line):
            attr = m.group(1)
            if not attr.startswith(('self.', 'str', 'Qt', 'QStyle')):
                hits.append(f'{p}:{n}: {line.strip()}  [item {attr}]')
        for m in pat_settext.finditer(line):
            attr = m.group(1)
            if not attr.startswith(('self.', 'str')):
                hits.append(f'{p}:{n}: {line.strip()}  [setText {attr}]')
print('\n'.join(hits) or 'aucun motif a risque')
print(f'TOTAL: {len(hits)}')
