# Wii Game Converter - Creator .exe (Windows)
# Lance ce script une seule fois pour generer WiiConverter.exe

pip install pyinstaller

pyinstaller --onefile --windowed --name "WiiConverter" wii_converter.py

echo.
echo ========================================
echo  WiiConverter.exe genere dans dist/
echo ========================================
echo.
pause
