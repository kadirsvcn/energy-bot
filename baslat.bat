@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem METIN2 yonetici olarak calisiyor; bot da yonetici olmazsa Windows
rem tiklamalari oyuna iletmez. Gerekirse kendini yeniden yetkili baslatir.
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Yonetici yetkisi isteniyor...
    if "%*"=="" (
        powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    ) else (
        powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '%*' -Verb RunAs"
    )
    exit /b
)

echo ================================
echo   Energy Bot - NPC tiklayici
echo ================================
echo NPC ismi ekranda aranir, uzerine tiklanir, ardindan "Marketi ac"
echo dugmesi bulunup tiklanir. Dugme cikmazsa NPC tiklamasi tekrar denenir.
echo Durdurmak icin: Ctrl+C  veya  fareyi sol ust koseye goturun
echo.
python bot.py %*
echo.
pause
