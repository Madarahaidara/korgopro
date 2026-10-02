@echo off
REM ============================================================================
REM Korgo Pro Web — Arret du serveur Vite (port 5173)
REM ============================================================================
echo Arret du serveur Korgo Pro Web (port 5173)...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /R /C:"LISTENING" ^| findstr ":5173 "') do (
  echo   arret du processus PID %%p
  taskkill /F /PID %%p >nul 2>nul
)
echo Termine.
pause
