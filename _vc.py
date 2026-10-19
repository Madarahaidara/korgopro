import zipfile
apk='c:/Users/COMTECH-DESKONE/korgopro/mobile/android/app/build/outputs/apk/release/app-release.apk'
z=zipfile.ZipFile(apk)
print('TOTAL_FILES='+str(len(z.infolist())))
for i in z.infolist():
    n=i.filename
    if 'Manifest' in n or 'resources.arsc' in n or n.endswith('.so'):
        print(i.file_size,'->',i.compress_size,'|',n)
