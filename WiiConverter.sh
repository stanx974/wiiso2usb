#!/bin/bash
# Wii Game Converter - Launcher Linux
# Lance l'interface graphique par defaut

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

python3 wii_converter.py "$@"
