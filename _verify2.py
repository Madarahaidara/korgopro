import zipfile
apk='c:/Users/COMTECH-DESKONE/korgopro/mobile/android/app/build/outputs/apk/release/app-release.apk'
z=zipfile.ZipFile(apk)
m=z.read('AndroidManifest.xml')
open('c:/Users/COMTECH-DESKONE/korgopro/_apk_manifest.xml','wb').write(m)
print('BYTES='+str(len(m)))
print('NOTIF='+str(b'POST_NOTIFICATIONS' in m))
print('NET='+str(b'ACCESS_NETWORK_STATE' in m))
print('MEDIA='+str(b'READ_MEDIA_IMAGES' in m))
print('INT='+str(b'INTERNET' in m))
print('EXT='+str(b'WRITE_EXTERNAL_STORAGE' in m))
print('VIBE='+str(b'VIBRATE' in m))
