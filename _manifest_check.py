import zipfile
apk='c:/Users/COMTECH-DESKONE/korgopro/mobile/android/app/build/outputs/apk/release/app-release.apk'
z=zipfile.ZipFile(apk)
m=z.read('AndroidManifest.xml')
t=m.decode('utf-8')
print('BYTES='+str(len(m)))
print('POST_NOTIFICATIONS='+str('POST_NOTIFICATIONS' in t))
print('ACCESS_NETWORK_STATE='+str('ACCESS_NETWORK_STATE' in t))
print('READ_MEDIA_IMAGES='+str('READ_MEDIA_IMAGES' in t))
print('WRITE_EXTERNAL_STORAGE='+str('WRITE_EXTERNAL_STORAGE' in t))
print('INTERNET='+str('INTERNET' in t))
print('----MANIFEST----')
print(t)
