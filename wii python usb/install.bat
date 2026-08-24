@echo off
REM Wii Game Converter - Installer Windows
REM Installe les dependances et genere WiiConverter.exe

echo ========================================
echo  Wii Game Converter - Installation
echo ========================================
echo.

REM Verifier Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERREUR: Python non trouve.
    telechargez Python depuis https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo [1/3] Installation de PyInstaller...
pip install pyinstaller

echo.
echo [2/3] Generation de WiiConverter.exe...
pyinstaller --onefile --windowed --name "WiiConverter" wii_converter.py

echo.
echo [3/3] Installation terminee !
echo.
echo WiiConverter.exe se trouve dans le dossier dist\
echo.
pause
