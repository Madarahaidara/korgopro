import zipfile
apk='c:/Users/COMTECH-DESKONE/korgopro/mobile/android/app/build/outputs/apk/release/app-release.apk'
s=zipfile.ZipFile(apk).read('AndroidManifest.xml').decode()
print('SIZE='+str(len(s)))
print('NOTIF='+str('POST_NOTIFICATIONS' in s))
print('NET='+str('ACCESS_NETWORK_STATE' in s))
print('MEDIA='+str('READ_MEDIA_IMAGES' in s))
print('INTERNET='+str('INTERNET' in s))
