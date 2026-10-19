import io, sys
p='c:/Users/COMTECH-DESKONE/korgopro/mobile/android/app/build/generated/assets/react/release/index.android.bundle'
s=io.open(p,encoding='utf-8',errors='ignore').read()
for k in ['scrollToField','onFocus','keyboardScroll','identifiantRef','LoginScreen','useKeyboardScroll','display_name','scrollRef','scrollYRef']:
    print(k, '=>', s.count(k))
