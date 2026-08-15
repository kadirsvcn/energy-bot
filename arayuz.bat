@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem METIN2 yonetici olarak calistigi icin arayuz de yonetici olmali,
rem yoksa Windows girdileri oyuna iletmez.
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Yonetici yetkisi isteniyor...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

start "" pythonw arayuz.py
