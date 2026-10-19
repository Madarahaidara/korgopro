import zipfile, binascii
apk='c:/Users/COMTECH-DESKONE/korgopro/mobile/android/app/build/outputs/apk/release/app-release.apk'
z=zipfile.ZipFile(apk)
for n in z.namelist():
    if 'Manifest' in n or n.endswith('.so') or 'resources.arsc' in n:
        i=z.getinfo(n)
        print(n, 'compress_type='+str(i.compress_type), 'filename=', i.filename)
        data=z.read(n)
        print('len='+str(len(data)))
        print('HEAD_HEX='+binascii.hexlify(data[:32]).decode('ascii'))
        print('HEAD_TEXT='+repr(data[:80]))
