@echo off
REM Wii Game Converter - Launcher Windows
REM Lance l'interface graphique par defaut

cd /d "%~dp0"

REM Essayer python3 d'abord, puis python
where python3 >nul 2>&1
if %errorlevel%==0 (
    python3 wii_converter.py %*
) else (
    python wii_converter.py %*
)

if %errorlevel% neq 0 (
    echo.
    echo Erreur: Python non trouve.
    telechargez Python depuis https://www.python.org/downloads/
    pause
)
