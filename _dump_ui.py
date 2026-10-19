import io
L = io.open('c:/Users/COMTECH-DESKONE/korgopro/mobile/src/components/ui.js', encoding='utf-8').read().splitlines()
out = io.open('c:/Users/COMTECH-DESKONE/korgopro/_ui_modal.txt', 'w', encoding='utf-8')
for i in range(225, 350):
    if i < len(L):
        out.write(f"{i+1}: {L[i]}\n")
out.close()
print('done', len(L))
