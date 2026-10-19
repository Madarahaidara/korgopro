# -*- coding: utf-8 -*-
"""Scan mobile source for Input usage + keyboard-wrapping per file."""
import io, os, re

BASE = 'c:/Users/COMTECH-DESKONE/korgopro/mobile/'
SKIP = {'.git', 'node_modules', '.expo', 'assets'}

for root, dirs, files in os.walk(BASE):
    dirs[:] = [d for d in dirs if d not in SKIP]
    for fn in sorted(files):
        if not fn.endswith('.js') and not fn.endswith('.jsx'):
            continue
        full = os.path.join(root, fn)
        rel = os.path.relpath(full, BASE).replace(os.sep, '/')
        try:
            c = io.open(full, encoding='utf-8').read()
        except Exception:
            continue
        n_input = len(re.findall(r'<Input\b', c))
        n_textinput = len(re.findall(r'<TextInput\b', c))
        if n_input + n_textinput == 0:
            continue
        n_kav = len(re.findall(r'<KeyboardAvoidingView\b', c))
        n_scroll = len(re.findall(r'<ScrollView\b', c))
        n_persist = len(re.findall(r'keyboardShouldPersistTaps', c))
        n_dismiss = len(re.findall(r'keyboardDismissMode', c))
        print(f"{rel}: Input={n_input} TextInput={n_textinput} KAV={n_kav} Scroll={n_scroll} persist={n_persist} dismiss={n_dismiss}")
