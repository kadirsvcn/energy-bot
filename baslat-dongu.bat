@echo off
chcp 65001 >nul
cd /d "%~dp0"

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Yonetici yetkisi isteniyor...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo ================================
echo   Energy Bot - SONSUZ DONGU
echo ================================
echo NPC surekli aranip tiklanir, ardindan "Marketi ac" dugmesine basilir.
echo Durdurmak icin: Ctrl+C  veya  fareyi sol ust koseye goturun
echo.
python bot.py --loop %*
echo.
pause
