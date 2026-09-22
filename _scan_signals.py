"""Scan des Signal() et emit() : emit(None) sur signal type = warning Shiboken."""
import io, re, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

decl = re.compile(r'(\w+)\s*=\s*Signal\(([^)]*)\)')
for p in list(Path('ui').rglob('*.py')) + list(Path('controllers').rglob('*.py')) + \
        list(Path('services').rglob('*.py')) + list(Path('core').rglob('*.py')):
    txt = p.read_text(encoding='utf-8', errors='ignore')
    signals = {m.group(1): m.group(2).strip() for m in decl.finditer(txt)}
    if not signals:
        continue
    for n, line in enumerate(txt.splitlines(), 1):
        m = re.search(r'(?:self\.)?(\w+)\.emit\((.*?)\)', line)
        if m and m.group(1) in signals:
            arg = m.group(2).strip()
            sig = signals[m.group(1)]
            print(f'{p.name}:{n}: {sig} <- emit({arg[:60]})')
print('--- declarations ---')
for p in Path('ui').rglob('*.py'):
    txt = p.read_text(encoding='utf-8', errors='ignore')
    for m in decl.finditer(txt):
        print(f'{p.name}: {m.group(1)} = Signal({m.group(2)})')
