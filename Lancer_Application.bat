@echo off
title SamaService Dakar - Lancement de l'application
echo ========================================================
echo        Lancement de l'application SamaService Dakar
echo ========================================================
echo.
cd /d "%~dp0"
echo Demarrage du serveur et ouverture de l'application...
timeout /t 1 >nul
start "" http://127.0.0.1:5000
python app.py
pause
