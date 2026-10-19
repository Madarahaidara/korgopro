import os, re, glob
paths=['c:/Users/COMTECH-DESKONE/korgopro/mobile/src','c:/Users/COMTECH-DESKONE/korgopro/mobile/app.json','c:/Users/COMTECH-DESKONE/korgopro/mobile/android/app/src/main/AndroidManifest.xml']
for p in paths:
    if not os.path.exists(p):
        print(p,'MISSING'); continue
    for f in glob.glob(p+'/**/*.py',recursive=True)+glob.glob(p+'/**/*.js',recursive=True)+glob.glob(p+'/**/*.json',recursive=True)+glob.glob(p+'/**/*.xml',recursive=True):
        try:
            s=open(f,encoding='utf-8',errors='ignore').read()
        except:
            continue
        for m in re.finditer(r'(notif|Permission|MIC|Microphone|location|Location|Contact|Contact|Camera|camera|Storage|storage|WRITE|READ|VIBRATE|SMS|RECORD_AUDIO|FINE_LOCATION|BACK_LOCATION)',s,re.I):
            line=s[:m.start()].count('\n')+1
            txt=re.sub(r'\s+',' ',s[max(0,m.start()-50):m.end()+50])
            print(os.path.relpath(f, 'c:/Users/COMTECH-DESKONE/korgopro')+':'+str(line)+' : '+txt)
PY
