import zipfile
apk='c:/Users/COMTECH-DESKONE/korgopro/mobile/android/app/build/outputs/apk/release/app-release.apk'
z=zipfile.ZipFile(apk)
m=z.read('AndroidManifest.xml')
open('c:/Users/COMTECH-DESKONE/korgopro/_apk_manifest.xml','wb').write(m)
print('WROTE='+str(len(m)))
