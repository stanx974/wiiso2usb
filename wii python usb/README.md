# Wii Game Converter

Outil Python pour convertir des fichiers ISO/RVZ de jeux Wii en format WBFS et les copier sur une cle USB.

Compatible **Linux Mint / Ubuntu** et **Windows 10/11**.

---

## Fonctionnalites

| Fonction | Description |
|----------|-------------|
| ISO -> WBFS | Conversion directe via Wiimms ISO Tools |
| RVZ -> WBFS | Conversion via DolphinTool puis wit |
| Copie USB (WBFS) | Ecriture directe sur partition WBFS via wwt |
| Copie USB (FAT32) | Copie dans /wbfs/NomDuJeu [ID]/ |
| Batch | Convertir tout un dossier d'ISO/RVZ en une fois |
| Lister jeux | Afficher la liste des jeux sur une cle USB WBFS |
| Detection USB | Detection automatique des lecteurs USB |

---

## Requirements

### Linux Mint / Ubuntu

```bash
sudo apt update
sudo apt install python3 python3-tk wget
```

### Windows

1. Python 3.8+ : https://www.python.org/downloads/
   - **Cocher "Add Python to PATH"** pendant l'installation
2. Verifier : `python --version`

---

## Installation des outils externes

### 1. Wiimms ISO Tools (wit + wwt)

**Linux :**

```bash
cd /tmp
wget https://wit.wiimm.de/download/wit-v3.01a-linux-x64.tar.gz
tar xzf wit-v3.01a-linux-x64.tar.gz
sudo cp wit-v3.01a-x64/wit /usr/local/bin/
sudo cp wit-v3.01a-x64/wwt /usr/local/bin/
sudo chmod +x /usr/local/bin/wit /usr/local/bin/wwt
```

**Windows :**

1. Telecharger : https://wit.wiimm.de/
2. Extraire dans `C:\WiimmsISOTools\`
3. Ajouter `C:\WiimmsISOTools\` au PATH systeme

### 2. DolphinTool (pour les fichiers RVZ uniquement)

**Linux (Flatpak) :**

```bash
flatpak install -y flathub org.DolphinEmu.dolphin-emu
flatpak override --user org.DolphinEmu.dolphin-emu --filesystem=home

mkdir -p ~/.local/bin
cat > ~/.local/bin/dolphin-tool << 'EOF'
#!/bin/bash
exec flatpak run --command=dolphin-tool org.DolphinEmu.dolphin-emu "$@"
EOF
chmod +x ~/.local/bin/dolphin-tool
```

**Windows :**

1. Telecharger Dolphin Emulator : https://dolphin-emu.org/
2. Installer - DolphinTool.exe est dans le dossier d'installation

---

## Verification de l'installation

```bash
python3 wii_converter.py --help
wit --version
wwt --version
dolphin-tool --help
```

Tous les outils doivent repondre sans erreur.

---

## Utilisation

### Interface graphique (recommandee)

**Linux :**

```bash
cd ~/Bureau/wii\ python\ usb
./WiiConverter.sh
```

**Windows :**

Double-cliquer sur `WiiConverter.bat`

Ou depuis un terminal :

```cmd
cd "%USERPROFILE%\Desktop\wii python usb"
WiiConverter.bat
```

### Generer un .exe autonome (Windows)

```cmd
install.bat
```

Ceci installe PyInstaller et genere `dist\WiiConverter.exe` qui fonctionne sans Python.

### Mode ligne de commande

```bash
# Convertir un ISO
python3 wii_converter.py game.iso

# Convertir un RVZ avec repertoire de sortie
python3 wii_converter.py game.rvz -o /sortie/

# Convertir et copier sur USB (partition WBFS)
python3 wii_converter.py game.iso --usb /dev/sdb1

# Convertir et copier sur USB (FAT32)
python3 wii_converter.py game.iso --usb /media/user/USB --usb-mode fat32

# Batch : convertir un dossier entier
python3 wii_converter.py --batch /dossier/jeux -o /sortie/

# Lister les USB detectees
python3 wii_converter.py --list-usb

# Lister les jeux WBFS sur une cle USB
python3 wii_converter.py --list-games /dev/sdb1

# Mode interactif (menu texte)
python3 wii_converter.py -i
```

### Windows - exemples

```cmd
python wii_converter.py game.iso
python wii_converter.py game.rvz -o D:\WiiGames\
python wii_converter.py game.iso --usb E: --usb-mode fat32
python wii_converter.py --list-games E:
```

---

## Structure USB

### Partition WBFS

Utilisez le mode `--usb` avec `--usb-mode wbfs` (defaut). Les jeux sont ecrits directement sur la partition WBFS.

### FAT32

Les jeux sont copies dans la structure compatible avec USB Loader GX / WiiFlow :

```
USB/
  wbfs/
    Super Mario Galaxy [RMGE01]/
      Super Mario Galaxy [RMGE01].wbfs
    Mario Kart Wii [RMCP01]/
      Mario Kart Wii [RMCP01].wbfs
```

---

## Fichiers inclus

| Fichier | Description |
|---------|-------------|
| `wii_converter.py` | Script principal Python |
| `WiiConverter.sh` | Lanceur Linux |
| `WiiConverter.bat` | Lanceur Windows |
| `install.bat` | Installe les dependances + genere .exe (Windows) |
| `create_exe.ps1` | Genere WiiConverter.exe via PyInstaller (Windows) |
| `README.md` | Ce fichier |

---

## Espace disque requis

Pour la conversion RVZ, un fichier ISO temporaire est cree dans `~/.cache/wii_converter/` :

- **RVZ -> USB WBFS** : necessite ~4.7 Go d'espace libre temporaire (ISO complet)
- **ISO -> USB WBFS** : pas d'espace temporaire requis (ecriture directe)
- **ISO/FAT32** : necessite ~4.7 Go pour le fichier WBFS temporaire

---

##Depannage

### "dolphin-tool introuvable"

**Linux** : Suivre l'installation Flatpak ci-dessus. Le script cree automatiquement un wrapper dans `~/.local/bin/dolphin-tool`.

**Windows** : Verifier que Dolphin Emulator est installe et que DolphinTool.exe est dans le PATH.

### "wit/wwt introuvable"

Verifier que les outils sont installes et dans le PATH :

```bash
which wit wwt       # Linux
where wit wwt       # Windows
```

### "NO WBFS FOUND" lors de la copie USB

- Verifier que la cle USB a bien une partition WBFS
- Utiliser la bonne partition (ex: `/dev/sdb1` pas `/dev/sdb`)
- Lister les partitions WBFS : `wwt find`

### "No space left on device"

Le disque dur est plein. La conversion RVZ necessite ~4.7 Go d'espace temporaire. Liberez de l'espace ou utilisez la copie directe vers USB.

### Erreur de permissions (Linux)

```bash
# Ajouter votre user au groupe disk (necessaire pour acces direct aux peripheriques)
sudo usermod -aG disk $USER
# Puis se reconnecter
```

---

## Licence

Usage personnel. Outil non Commercial.
