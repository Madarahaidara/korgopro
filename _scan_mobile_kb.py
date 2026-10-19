# -*- coding: utf-8 -*-
import io, os, re
BASE = 'c:/Users/COMTECH-DESKONE/korgopro/mobile/src/'
out = []
for root, dirs, files in os.walk(BASE):
    for fn in sorted(files):
        if not fn.endswith(('.js', '.jsx')):
            continue
        full = os.path.join(root, fn)
        rel = os.path.relpath(full, BASE).replace(os.sep, '/')
        lines = io.open(full, encoding='utf-8').read().splitlines()
        hits = []
        for i, l in enumerate(lines, 1):
            if re.search(r'KeyboardAvoidingView|behavior=|keyboardShouldPersistTaps|keyboardVerticalOffset|keyboardDismissMode|<ScrollView', l):
                hits.append(f"    {i}: {l.strip()[:110]}")
        if hits:
            out.append(f"=== {rel} ===")
            out.extend(hits)
io.open('c:/Users/COMTECH-DESKONE/korgopro/_scan_kav.txt', 'w', encoding='utf-8').write("\n".join(out))
print("done", len(out))


