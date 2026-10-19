import os, re, json
root='c:/Users/COMTECH-DESKONE/korgopro/mobile/src'
files=[]
for dp,_,fns in os.walk(root):
    for f in fns:
        if f.endswith('.js'):
            files.append(os.path.join(dp,f))
text='\n'.join(open(p,encoding='utf-8',errors='ignore').read() for p in files)
text=re.sub(r'/\*.*?\*/','',text,flags=re.S)
text=re.sub(r'\s+',' ',text)
keys=['Notification','Notification','Camera','camera','Location','location','Storage','storage','Share','share','Download','download','voice','Voice','sms','Sms','Contact','contact','Path','path','upload','Upload','Alert','alert']
for k in keys:
    c=list(re.finditer(re.escape(k),text,flags=re.I))
    if c:
        print(k,'=>',len(c))
print('---REACT-NATIVE IMPORTS---')
for m in sorted(set(re.findall(r"from\s+['\"]([a-zA-Z0-9\-_]+)['\"]",text))):
    print(m)
print('---EXPO/IMPORT---')
for m in sorted(set(re.findall(r"import\s+\{?([a-zA-Z0-9\s,]+)\}?\s+from\s+['\"]([^'\"]+)['\"]",text))):
    print(m[0],'::',m[1])
