# Install mobile APK
$adb = "c:/Users/COMTECH-DESKONE/korgopro/platform-tools/platform-tools/adb.exe"
$apk = "c:/Users/COMTECH-DESKONE/korgopro/mobile/apk/app-release.apk"

Write-Host "=== Restarting ADB ==="
& $adb kill-server
Start-Sleep -Milliseconds 1000
& $adb start-server
Start-Sleep -Milliseconds 1000
& $adb devices
Write-Host "=== Installing APK ==="
& $adb install -r $apk
Write-Host "=== Post-install devices ==="
& $adb devices
