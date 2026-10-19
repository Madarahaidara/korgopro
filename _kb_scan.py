# -*- coding: utf-8 -*-
import io, os, re

BASE = 'c:/Users/COMTECH-DESKONE/korgopro/mobile/src'
pats = ['KeyboardAvoidingView', 'keyboardShouldPersistTaps', 'keyboardDismissMode',
        'automaticallyAdjustKeyboardInsets', 'behavior=', 'keyboardVerticalOffset',
        '<ScrollView', '<Modal', 'bounces']
out = io.open('c:/Users/COMTECH-DESKONE/korgopro/_kb_scan.txt', 'w', encoding='utf-8')
for root, dirs, files in os.walk(BASE):
    for fn in files:
        if not fn.endswith('.js'):
            continue
        full = os.path.join(root, fn)
        rel = os.path.relpath(full, 'c:/Users/COMTECH-DESKONE/korgopro/').replace(os.sep, '/')
        lines = io.open(full, encoding='utf-8').read().splitlines()
        for i, ln in enumerate(lines, 1):
            if any(p in ln for p in pats):
                out.write(f"{rel}:{i}: {ln.rstrip()}\n")
out.close()
print('done')
