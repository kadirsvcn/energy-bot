@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ================================
echo   Energy Bot - SABLON OLUSTUR
echo ================================
echo Tiklanacak NPC'nin ISMI ekranda gorunur olsun, sonra devam edin.
echo Ekrandaki en buyuk NPC ismi sablon olarak kaydedilir.
echo.
pause
python bot.py --sablon
echo.
pause
