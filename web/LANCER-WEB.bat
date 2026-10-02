@echo off
REM ============================================================================
REM Korgo Pro Web — Lanceur portable (double-clic)
REM - Installe les dependances au 1er lancement (npm install)
REM - Demarre le serveur Vite sur http://localhost:5173
REM ============================================================================
setlocal
cd /d "%~dp0"

where node >nul 2>nul
if errorlevel 1 (
  if exist "C:\tools\nodejs\node.exe" (
    set "PATH=C:\tools\nodejs;%PATH%"
  ) else (
    echo.
    echo [ERREUR] Node.js est introuvable.
    echo.
    echo 1. Installez Node.js LTS depuis https://nodejs.org/
    echo 2. Fermez puis rouvrez cette fenetre, puis relancez ce fichier.
    echo.
    pause
    exit /b 1
  )
)

if not exist "node_modules" (
  echo Installation des dependances (1er lancement, ~1-2 min)...
  call npm install
  if errorlevel 1 (
    echo.
    echo [ERREUR] npm install a echoue. Verifiez votre connexion Internet.
    pause
    exit /b 1
  )
)

echo.
echo Demarrage de Korgo Pro Web...
echo Ouvrez http://localhost:5173 dans votre navigateur.
echo (Ctrl+C pour arreter le serveur)
echo.
call npm run dev
pause
