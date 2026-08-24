#!/usr/bin/env python3
"""
Wii Game Converter - Convert ISO/RVZ to WBFS and copy to USB drive.
Compatible with Linux Mint and Windows.

Requires:
  - Wiimms ISO Tools (wit, wwt): https://wit.wiimm.de/
  - Dolphin Emulator (DolphinTool): https://dolphin-emu.org/ (only for RVZ)
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import glob as globmod
from pathlib import Path


def find_tool(name):
    """Find an executable on PATH or in common locations."""
    found = shutil.which(name)
    if found:
        return found

    system = platform.system()
    search_dirs = []

    if system == "Windows":
        search_dirs = [
            Path(os.environ.get("ProgramFiles", "C:\\Program Files")),
            Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")),
            Path(os.environ.get("LOCALAPPDATA", "")),
            Path.home() / "Downloads",
            Path("C:\\WiimmsISOTools"),
            Path("C:\\Dolphin"),
        ]
        if name == "wit":
            candidates = ["wit.exe", "wit"]
        elif name == "wwt":
            candidates = ["wwt.exe", "wwt"]
        elif name == "dolphin-tool":
            candidates = ["DolphinTool.exe", "dolphin-tool.exe"]
        else:
            candidates = [name + ".exe", name]
    else:
        search_dirs = [
            Path("/usr/local/bin"),
            Path("/usr/bin"),
            Path.home() / ".local" / "bin",
            Path.home() / "bin",
        ]
        candidates = [name, name + ".exe"]

    for d in search_dirs:
        if not d.exists():
            continue
        for c in candidates:
            p = d / c
            if p.is_file():
                return str(p)

    # Linux: search for dolphin-tool in Flatpak installation
    if system != "Windows" and name == "dolphin-tool":
        flatpak_paths = [
            Path("/var/lib/flatpak/app/org.DolphinEmu.dolphin-emu/x86_64/stable/active/files/bin/dolphin-tool"),
            Path.home() / ".local/share/flatpak/app/org.DolphinEmu.dolphin-emu/x86_64/stable/active/files/bin/dolphin-tool",
        ]
        # Also search in versioned directories
        for base in [Path("/var/lib/flatpak/app/org.DolphinEmu.dolphin-emu/x86_64/stable"),
                     Path.home() / ".local/share/flatpak/app/org.DolphinEmu.dolphin-emu/x86_64/stable"]:
            if base.exists():
                for version_dir in base.iterdir():
                    candidate = version_dir / "files/bin/dolphin-tool"
                    if candidate.is_file():
                        flatpak_paths.append(candidate)

        for p in flatpak_paths:
            if p.is_file():
                # Create a wrapper script so it can be called like a normal binary
                wrapper_dir = Path.home() / ".local/bin"
                wrapper_dir.mkdir(parents=True, exist_ok=True)
                wrapper = wrapper_dir / "dolphin-tool"
                wrapper.write_text(f"""#!/bin/bash
exec flatpak run --command=dolphin-tool org.DolphinEmu.dolphin-emu "$@"
""")
                wrapper.chmod(0o755)
                return str(wrapper)

        # Check if flatpak run works (fallback)
        try:
            result = subprocess.run(
                ["flatpak", "run", "--command=dolphin-tool", "org.DolphinEmu.dolphin-emu", "--help"],
                capture_output=True, timeout=10)
            if result.returncode == 0:
                # Create wrapper script
                wrapper_dir = Path.home() / ".local/bin"
                wrapper_dir.mkdir(parents=True, exist_ok=True)
                wrapper = wrapper_dir / "dolphin-tool"
                wrapper.write_text(f"""#!/bin/bash
exec flatpak run --command=dolphin-tool org.DolphinEmu.dolphin-emu "$@"
""")
                wrapper.chmod(0o755)
                return str(wrapper)
        except Exception:
            pass

    return None


def check_tools(require_dolphin=False):
    """Check that required external tools are available."""
    wit = find_tool("wit")
    wwt = find_tool("wwt")
    dolphin = find_tool("dolphin-tool") if require_dolphin else None

    missing = []
    if not wit:
        missing.append("wit (Wiimms ISO Tools) - https://wit.wiimm.de/")
    if not wwt:
        missing.append("wwt (Wiimms WBFS Tool) - https://wit.wiimm.de/")
    if require_dolphin and not dolphin:
        missing.append("dolphin-tool (Dolphin Emulator) - https://dolphin-emu.org/")

    if missing:
        print("ERROR: Missing required tools:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        sys.exit(1)

    return {"wit": wit, "wwt": wwt, "dolphin": dolphin}


def run_cmd(cmd, description=""):
    """Run a command and stream output. Returns True on success."""
    if description:
        print(f"\n>>> {description}")
    print(f"    CMD: {' '.join(cmd)}\n")
    try:
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            print(f"\nERROR: Command failed with return code {result.returncode}", file=sys.stderr)
            return False
        return True
    except FileNotFoundError as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        return False


def iso_to_wbfs(input_path, output_path, tools):
    """Convert ISO to WBFS using wit."""
    cmd = [tools["wit"], "copy", str(input_path), str(output_path),
           "--wbfs", "--links"]
    return run_cmd(cmd, f"Converting ISO -> WBFS: {input_path}")


def rvz_to_wbfs(input_path, output_path, tools):
    """Convert RVZ to WBFS via intermediate ISO (DolphinTool -> wit)."""
    tmp_base = Path.home() / ".cache" / "wii_converter"
    tmp_base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(tmp_base), prefix="tmp_") as tmpdir:
        tmp_iso = Path(tmpdir) / Path(input_path).with_suffix(".iso").name

        # Step 1: RVZ -> ISO
        cmd_dolphin = [tools["dolphin"], "convert", "-f", "iso",
                       "-i", str(input_path), "-o", str(tmp_iso)]
        if not run_cmd(cmd_dolphin, f"Converting RVZ -> ISO: {input_path}"):
            return False

        # Step 2: ISO -> WBFS
        return iso_to_wbfs(tmp_iso, output_path, tools)


def rvz_to_usb_wbfs(input_path, usb_drive, tools):
    """Convert RVZ directly to USB WBFS partition (no local .wbfs file)."""
    tmp_base = Path.home() / ".cache" / "wii_converter"
    tmp_base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(tmp_base), prefix="tmp_") as tmpdir:
        tmp_iso = Path(tmpdir) / Path(input_path).with_suffix(".iso").name

        # Step 1: RVZ -> ISO
        cmd_dolphin = [tools["dolphin"], "convert", "-f", "iso",
                       "-i", str(input_path), "-o", str(tmp_iso)]
        if not run_cmd(cmd_dolphin, f"Converting RVZ -> ISO: {input_path}"):
            return False

        # Step 2: ISO -> USB WBFS partition directly
        return iso_to_usb_wbfs(tmp_iso, usb_drive, tools)


def iso_to_usb_wbfs(input_path, usb_drive, tools):
    """Add ISO directly to USB WBFS partition (no local .wbfs file)."""
    cmd = [tools["wwt"], "add", "-p", usb_drive, str(input_path)]
    return run_cmd(cmd, f"Ajout ISO sur partition WBFS: {usb_drive}")


def detect_usb_drives():
    """Detect potential USB drives with existing WBFS or that could be used."""
    system = platform.system()
    drives = []

    if system == "Windows":
        # List drives with wwt
        try:
            result = subprocess.run(["wwt", "drive", "list"],
                                    capture_output=True, text=True, timeout=10)
            for line in result.stdout.splitlines():
                line = line.strip()
                if line and ":" in line and not line.startswith("Drive"):
                    parts = line.split()
                    if parts:
                        drives.append(parts[0])
        except Exception:
            # Fallback: list all removable drives
            for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    drives.append(drive)
    else:
        # First: find existing WBFS partitions via wwt
        wbt = find_tool("wwt")
        if wbt:
            try:
                result = subprocess.run([wbt, "find"], capture_output=True, text=True, timeout=10)
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line.startswith("/dev/"):
                        drives.append(line)
            except Exception:
                pass

        # Then: list USB disks with their partitions
        try:
            result = subprocess.run(["lsblk", "-o", "NAME,TYPE,SIZE,FSTYPE,LABEL,MODEL", "-J"],
                                    capture_output=True, text=True, timeout=10)
            import json
            data = json.loads(result.stdout)
            for device in data.get("blockdevices", []):
                if device.get("type") == "disk":
                    name = device.get("name", "")
                    model = device.get("model", "").lower()
                    # Check if it's likely a USB device
                    removable_path = f"/sys/block/{name}/removable"
                    is_removable = False
                    if os.path.exists(removable_path):
                        with open(removable_path) as f:
                            is_removable = f.read().strip() == "1"
                    if is_removable or "usb" in model or "generic" in model:
                        # List partitions of this disk
                        for child in device.get("children", []):
                            part_name = child.get("name", "")
                            part_fstype = child.get("fstype", "") or "?"
                            part_label = child.get("label", "") or ""
                            part_size = child.get("size", "") or ""
                            desc = f"/dev/{part_name}  ({part_size} {part_fstype}"
                            if part_label:
                                desc += f" {part_label}"
                            desc += ")"
                            if desc not in drives:
                                drives.append(desc)
        except Exception:
            pass

        # Also check common mount points
        for p in Path("/media").iterdir() if Path("/media").exists() else []:
            if p.is_dir():
                drives.append(str(p))
        for p in Path("/mnt").iterdir() if Path("/mnt").exists() else []:
            if p.is_dir():
                drives.append(str(p))

    return drives


def _extract_device_path(display_str):
    """Extract /dev/xxx path from a display string like '/dev/sdb1  (57,6G ext4)'."""
    import re
    match = re.search(r'(/dev/\S+)', display_str)
    if match:
        return match.group(1)
    return display_str.strip()


def list_wbfs_games(drive, tools):
    """List games on a WBFS partition."""
    cmd = [tools["wwt"], "list", "-p", drive]
    return run_cmd(cmd, f"Jeux sur {drive}")


def copy_to_usb_usb_wbfs_partition(wbfs_file, drive, tools):
    """Copy a WBFS file to a USB drive that has a WBFS partition using wwt."""
    cmd = [tools["wwt"], "add", "-p", drive, str(wbfs_file)]
    return run_cmd(cmd, f"Copie sur partition WBFS: {drive}")


def copy_to_usb_fat32(wbfs_file, usb_path):
    """Copy WBFS file to a FAT32 USB drive in /wbfs/ structure."""
    usb = Path(usb_path)
    wbfs_dir = usb / "wbfs"
    wbfs_dir.mkdir(parents=True, exist_ok=True)

    wbfs_name = Path(wbfs_file).stem
    game_dir = wbfs_dir / wbfs_name
    game_dir.mkdir(parents=True, exist_ok=True)

    dest = game_dir / Path(wbfs_file).name
    print(f">>> Copying {wbfs_file} -> {dest}")
    shutil.copy2(str(wbfs_file), str(dest))
    print(f"    Done. ({dest})")
    return True


def interactive_menu():
    """Interactive menu for choosing operations."""
    print("=" * 60)
    print("  Wii Game Converter - ISO/RVZ -> WBFS -> USB")
    print("=" * 60)
    print()
    print("  1) Convert a single file (ISO or RVZ -> WBFS)")
    print("  2) Batch convert a folder (ISO/RVZ -> WBFS)")
    print("  3) Convert and copy to USB drive")
    print("  4) Copy existing WBFS file(s) to USB drive")
    print("  5) List USB drives")
    print("  6) List WBFS games on USB drive")
    print("  0) Quit")
    print()

    choice = input("  Choice: ").strip()
    return choice


# ============================================================================
#  GUI (tkinter)
# ============================================================================

def launch_gui():
    """Launch the graphical interface."""
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    class WiiConverterGUI:
        def __init__(self, root):
            self.root = root
            self.root.title("Wii Game Converter - ISO/RVZ -> WBFS -> USB")
            self.root.geometry("780x620")
            self.root.minsize(680, 550)
            self.root.resizable(True, True)

            self.input_files = []
            self.tools = {}

            self._build_ui()
            self._check_tools()

        def _build_ui(self):
            # --- Main frame ---
            main = ttk.Frame(self.root, padding=10)
            main.pack(fill=tk.BOTH, expand=True)

            # === Input section ===
            frame_input = ttk.LabelFrame(main, text="Fichier(s) d'entree", padding=8)
            frame_input.pack(fill=tk.X, pady=(0, 8))

            row_files = ttk.Frame(frame_input)
            row_files.pack(fill=tk.X)

            self.entry_input = ttk.Entry(row_files)
            self.entry_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

            ttk.Button(row_files, text="Parcourir...", command=self._browse_input).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(row_files, text="Dossier...", command=self._browse_folder).pack(side=tk.LEFT)

            self.lbl_files = ttk.Label(frame_input, text="Aucun fichier selectionne", foreground="gray")
            self.lbl_files.pack(anchor=tk.W, pady=(4, 0))

            # === Output section ===
            frame_output = ttk.LabelFrame(main, text="Repertoire de sortie", padding=8)
            frame_output.pack(fill=tk.X, pady=(0, 8))

            row_out = ttk.Frame(frame_output)
            row_out.pack(fill=tk.X)

            self.entry_output = ttk.Entry(row_out)
            self.entry_output.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

            ttk.Button(row_out, text="Parcourir...", command=self._browse_output).pack(side=tk.LEFT)

            ttk.Label(frame_output, text="(laisser vide = meme repertoire que l'entree)",
                      foreground="gray").pack(anchor=tk.W, pady=(4, 0))

            # === USB section ===
            frame_usb = ttk.LabelFrame(main, text="Copie USB", padding=8)
            frame_usb.pack(fill=tk.X, pady=(0, 8))

            row_usb1 = ttk.Frame(frame_usb)
            row_usb1.pack(fill=tk.X)

            self.var_usb_enable = tk.BooleanVar()
            ttk.Checkbutton(row_usb1, text="Copier sur USB",
                            variable=self.var_usb_enable).pack(side=tk.LEFT)
            ttk.Button(row_usb1, text="Detecter USB", command=self._detect_usb).pack(side=tk.RIGHT)
            ttk.Button(row_usb1, text="Lister jeux", command=self._list_games).pack(side=tk.RIGHT, padx=(0, 5))

            row_usb2 = ttk.Frame(frame_usb)
            row_usb2.pack(fill=tk.X, pady=(4, 0))

            ttk.Label(row_usb2, text="Lecteur :").pack(side=tk.LEFT)
            self.combo_usb = ttk.Combobox(row_usb2, state="readonly", width=30)
            self.combo_usb.pack(side=tk.LEFT, padx=(4, 10))

            ttk.Label(row_usb2, text="Mode :").pack(side=tk.LEFT)
            self.var_usb_mode = tk.StringVar(value="wbfs")
            ttk.Radiobutton(row_usb2, text="Partition WBFS", variable=self.var_usb_mode,
                            value="wbfs").pack(side=tk.LEFT, padx=(4, 0))
            ttk.Radiobutton(row_usb2, text="FAT32", variable=self.var_usb_mode,
                            value="fat32").pack(side=tk.LEFT, padx=(4, 0))

            # === Action buttons ===
            frame_actions = ttk.Frame(main)
            frame_actions.pack(fill=tk.X, pady=(0, 8))

            self.btn_convert = ttk.Button(frame_actions, text="  Convertir  ",
                                          command=self._run_convert)
            self.btn_convert.pack(side=tk.LEFT)

            self.btn_quit = ttk.Button(frame_actions, text="  Quitter  ",
                                       command=self.root.quit)
            self.btn_quit.pack(side=tk.RIGHT)

            # === Progress ===
            self.progress = ttk.Progressbar(main, mode="indeterminate")
            self.progress.pack(fill=tk.X, pady=(0, 4))

            # === Log ===
            frame_log = ttk.LabelFrame(main, text="Journal", padding=4)
            frame_log.pack(fill=tk.BOTH, expand=True)

            self.log_text = tk.Text(frame_log, height=12, state=tk.DISABLED,
                                    wrap=tk.WORD, font=("Consolas", 9))
            scroll = ttk.Scrollbar(frame_log, command=self.log_text.yview)
            self.log_text.configure(yscrollcommand=scroll.set)
            scroll.pack(side=tk.RIGHT, fill=tk.Y)
            self.log_text.pack(fill=tk.BOTH, expand=True)

            # === Status bar ===
            self.status_var = tk.StringVar(value="Pret")
            ttk.Label(self.root, textvariable=self.status_var,
                      relief=tk.SUNKEN, anchor=tk.W, padding=(6, 2)).pack(fill=tk.X, side=tk.BOTTOM)

        # ----- helpers -----

        def _log(self, msg):
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, msg + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)

        def _set_status(self, msg):
            self.status_var.set(msg)

        def _browse_input(self):
            files = filedialog.askopenfilenames(
                title="Selectionner un ou plusieurs fichiers Wii",
                filetypes=[
                    ("Fichiers Wii", "*.iso *.rvz *.wbfs"),
                    ("ISO", "*.iso"),
                    ("RVZ", "*.rvz"),
                    ("WBFS", "*.wbfs"),
                    ("Tous les fichiers", "*.*"),
                ])
            if files:
                self.input_files = list(files)
                self.entry_input.delete(0, tk.END)
                self.entry_input.insert(0, files[0])
                if len(files) == 1:
                    self.lbl_files.configure(text=Path(files[0]).name)
                else:
                    self.lbl_files.configure(text=f"{len(files)} fichiers selectionnes")

        def _browse_folder(self):
            folder = filedialog.askdirectory(title="Selectionner un dossier de jeux Wii")
            if folder:
                self.input_files = []
                for ext in ("*.iso", "*.ISO", "*.rvz", "*.RVZ"):
                    self.input_files.extend(Path(folder).glob(ext))
                self.input_files = [str(f) for f in self.input_files]
                self.entry_input.delete(0, tk.END)
                self.entry_input.insert(0, folder)
                if self.input_files:
                    self.lbl_files.configure(text=f"{len(self.input_files)} fichier(s) trouve(s)")
                else:
                    self.lbl_files.configure(text="Aucun ISO/RVZ trouve dans ce dossier")

        def _browse_output(self):
            folder = filedialog.askdirectory(title="Selectionner le repertoire de sortie")
            if folder:
                self.entry_output.delete(0, tk.END)
                self.entry_output.insert(0, folder)

        def _detect_usb(self):
            drives = detect_usb_drives()
            self.combo_usb["values"] = drives
            if drives:
                self.combo_usb.current(0)
                self._log("Lecteurs USB detectes :")
                for d in drives:
                    self._log(f"  - {d}")
            else:
                self._log("Aucun lecteur USB detecte.")

        def _list_games(self):
            drive = self.combo_usb.get().strip()
            if not drive:
                self._log("Aucun lecteur selectionne.")
                return
            device = _extract_device_path(drive)
            if not self.tools.get("wwt"):
                self._log("wwt introuvable.")
                return
            self._log(f"\nJeux sur {device} :")
            cmd = [self.tools["wwt"], "list", "-p", device]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                self._log(result.stdout)
                if result.stderr:
                    self._log(result.stderr)
            except Exception as e:
                self._log(f"Erreur : {e}")

        def _check_tools(self):
            wit = find_tool("wit")
            wwt = find_tool("wwt")
            dolphin = find_tool("dolphin-tool")

            self.tools = {"wit": wit, "wwt": wwt, "dolphin": dolphin}

            status_parts = []
            if wit:
                status_parts.append(f"wit: OK")
            else:
                status_parts.append(f"wit: MANQUANT")
            if wwt:
                status_parts.append(f"wwt: OK")
            else:
                status_parts.append(f"wwt: MANQUANT")
            if dolphin:
                status_parts.append(f"dolphin-tool: OK")
            else:
                status_parts.append(f"dolphin-tool: absent (RVZ impossible)")

            self._log("Verification des outils :")
            self._log("  " + " | ".join(status_parts))
            self._log("")

            if not wit or not wwt:
                self._log("ATTENTION : wit et/ou wwt introuvables.")
                self._log("Telechargez Wiimms ISO Tools : https://wit.wiimm.de/")
                self._log("")

            self._detect_usb()

        # ----- conversion -----

        def _run_convert(self):
            if not self.input_files:
                messagebox.showwarning("Attention", "Aucun fichier d'entree selectionne.")
                return

            need_dolphin = any(Path(f).suffix.lower() == ".rvz" for f in self.input_files)
            if need_dolphin and not self.tools.get("dolphin"):
                messagebox.showerror("Erreur",
                                     "Des fichiers RVZ sont presents mais dolphin-tool est introuvable.\n"
                                     "Installez Dolphin Emulator : https://dolphin-emu.org/")
                return
            if not self.tools.get("wit") or not self.tools.get("wwt"):
                messagebox.showerror("Erreur",
                                     "wit et/ou wwt introuvables.\n"
                                     "Telechargez Wiimms ISO Tools : https://wit.wiimm.de/")
                return

            output_dir = self.entry_output.get().strip() or None
            if output_dir:
                Path(output_dir).mkdir(parents=True, exist_ok=True)

            usb_drive = _extract_device_path(self.combo_usb.get()) if self.var_usb_enable.get() else None
            usb_mode = self.var_usb_mode.get()

            self.btn_convert.configure(state=tk.DISABLED)
            self.progress.start(12)
            self._set_status("Conversion en cours...")

            def worker():
                ok_count = 0
                fail_count = 0
                total = len(self.input_files)

                for idx, fpath in enumerate(self.input_files, 1):
                    fp = Path(fpath)
                    ext = fp.suffix.lower()

                    self.root.after(0, self._log,
                                    f"[{idx}/{total}] Conversion de {fp.name} ...")

                    # Conversion
                    try:
                        if usb_drive and usb_mode == "wbfs":
                            # Direct to USB WBFS partition (no local .wbfs)
                            if ext == ".iso":
                                ok = iso_to_usb_wbfs(fp, usb_drive, self.tools)
                            elif ext == ".rvz":
                                ok = rvz_to_usb_wbfs(fp, usb_drive, self.tools)
                            elif ext == ".wbfs":
                                ok = copy_to_usb_usb_wbfs_partition(fp, usb_drive, self.tools)
                            else:
                                self.root.after(0, self._log, f"  Format ignore : {ext}")
                                fail_count += 1
                                continue
                            if ok:
                                self.root.after(0, self._log, f"  OK -> {usb_drive}")
                            else:
                                self.root.after(0, self._log, "  Echec de la conversion.")
                                fail_count += 1
                                continue
                        else:
                            # Local conversion (FAT32 or no USB)
                            if output_dir:
                                out_wbfs = Path(output_dir) / fp.with_suffix(".wbfs").name
                            else:
                                out_wbfs = fp.with_suffix(".wbfs")

                            if ext == ".iso":
                                ok = iso_to_wbfs(fp, out_wbfs, self.tools)
                            elif ext == ".rvz":
                                ok = rvz_to_wbfs(fp, out_wbfs, self.tools)
                            elif ext == ".wbfs":
                                ok = True
                                out_wbfs = fp
                            else:
                                self.root.after(0, self._log, f"  Format ignore : {ext}")
                                fail_count += 1
                                continue

                            if not ok:
                                self.root.after(0, self._log, "  Echec de la conversion.")
                                fail_count += 1
                                continue

                            self.root.after(0, self._log, f"  OK -> {out_wbfs.name}")

                            # Copie USB FAT32
                            if usb_drive:
                                self.root.after(0, self._log, f"  Copie sur {usb_drive} ...")
                                try:
                                    copy_to_usb_fat32(out_wbfs, usb_drive)
                                    self.root.after(0, self._log, "  Copie terminee.")
                                except Exception as e:
                                    self.root.after(0, self._log, f"  Erreur copie : {e}")
                                    fail_count += 1
                    except Exception as e:
                        self.root.after(0, self._log, f"  ERREUR : {e}")
                        fail_count += 1
                        continue

                    ok_count += 1

                self.root.after(0, self._done, ok_count, fail_count)

            import threading
            threading.Thread(target=worker, daemon=True).start()

        def _done(self, ok_count, fail_count):
            self.progress.stop()
            self.btn_convert.configure(state=tk.NORMAL)
            msg = f"Termine : {ok_count} reussi(s), {fail_count} en echec"
            self._set_status(msg)
            self._log(f"\n{'='*40}\n{msg}\n")
            if fail_count == 0 and ok_count > 0:
                messagebox.showinfo("Termine", msg)
            elif fail_count > 0:
                messagebox.showwarning("Termine", msg)


    root = tk.Tk()
    WiiConverterGUI(root)
    root.mainloop()


def batch_convert(input_dir, output_dir, tools):
    """Convert all ISO and RVZ files in a directory."""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    patterns = ["*.iso", "*.ISO", "*.rvz", "*.RVZ"]
    files = []
    for pat in patterns:
        files.extend(input_path.glob(pat))

    if not files:
        print(f"No ISO or RVZ files found in {input_dir}")
        return

    print(f"Found {len(files)} file(s) to convert:")
    for f in files:
        print(f"  - {f.name}")
    print()

    success = 0
    fail = 0
    for f in files:
        ext = f.suffix.lower()
        out_file = output_path / f.with_suffix(".wbfs").name

        if ext == ".iso":
            ok = iso_to_wbfs(f, out_file, tools)
        elif ext == ".rvz":
            ok = rvz_to_wbfs(f, out_file, tools)
        else:
            print(f"Skipping unknown format: {f}")
            continue

        if ok:
            success += 1
        else:
            fail += 1

    print(f"\n{'=' * 40}")
    print(f"Batch conversion complete: {success} success, {fail} failed")


def _run_interactive():
    """Run the text-based interactive menu."""
    while True:
        choice = interactive_menu()
        if choice == "0":
            break
        elif choice == "1":
            f = input("  Input file (ISO/RVZ): ").strip()
            if not f or not Path(f).exists():
                print("  File not found.")
                continue
            out = input("  Output path (Enter for current dir): ").strip() or "."
            ext = Path(f).suffix.lower()
            require_dolphin = ext == ".rvz"
            tools = check_tools(require_dolphin=require_dolphin)
            out_file = Path(out) / Path(f).with_suffix(".wbfs").name
            if ext == ".iso":
                iso_to_wbfs(f, out_file, tools)
            elif ext == ".rvz":
                rvz_to_wbfs(f, out_file, tools)
            else:
                print("  Unsupported format. Use ISO or RVZ.")
        elif choice == "2":
            d = input("  Input directory: ").strip()
            out = input("  Output directory (Enter for ./output): ").strip() or "./output"
            tools = check_tools(require_dolphin=True)
            batch_convert(d, out, tools)
        elif choice == "3":
            f = input("  Input file (ISO/RVZ): ").strip()
            if not f or not Path(f).exists():
                print("  File not found.")
                continue
            ext = Path(f).suffix.lower()
            require_dolphin = ext == ".rvz"
            tools = check_tools(require_dolphin=require_dolphin)
            drives = detect_usb_drives()
            if drives:
                print("  Detected drives:")
                for i, d in enumerate(drives):
                    print(f"    {i}) {d}")
                idx = input("  Select drive number: ").strip()
                try:
                    usb = _extract_device_path(drives[int(idx)])
                except (ValueError, IndexError):
                    usb = input("  Enter drive path manually: ").strip()
            else:
                usb = input("  Enter USB drive path (e.g. /dev/sdb1 or E:): ").strip()
            if not usb:
                print("  No drive selected.")
                continue
            mode = input("  USB mode - wbfs partition or fat32? [wbfs/fat32]: ").strip().lower() or "wbfs"
            if mode == "wbfs":
                # Direct to USB WBFS partition (no local .wbfs)
                if ext == ".iso":
                    ok = iso_to_usb_wbfs(f, usb, tools)
                elif ext == ".rvz":
                    ok = rvz_to_usb_wbfs(f, usb, tools)
                elif ext == ".wbfs":
                    ok = copy_to_usb_usb_wbfs_partition(f, usb, tools)
                else:
                    print("  Unsupported format.")
                    continue
            else:
                # FAT32: create local .wbfs then copy
                tmp_base = Path.home() / ".cache" / "wii_converter"
                tmp_base.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(dir=str(tmp_base), prefix="tmp_") as tmpdir:
                    tmp_wbfs = Path(tmpdir) / Path(f).with_suffix(".wbfs").name
                    if ext == ".iso":
                        ok = iso_to_wbfs(f, tmp_wbfs, tools)
                    elif ext == ".rvz":
                        ok = rvz_to_wbfs(f, tmp_wbfs, tools)
                    elif ext == ".wbfs":
                        tmp_wbfs = Path(f)
                        ok = True
                    else:
                        print("  Unsupported format.")
                        continue
                    if ok:
                        copy_to_usb_fat32(tmp_wbfs, usb)
        elif choice == "4":
            f = input("  WBFS file path: ").strip()
            if not f or not Path(f).exists():
                print("  File not found.")
                continue
            tools = check_tools()
            drives = detect_usb_drives()
            if drives:
                print("  Detected drives:")
                for i, d in enumerate(drives):
                    print(f"    {i}) {d}")
                idx = input("  Select drive number: ").strip()
                try:
                    usb = _extract_device_path(drives[int(idx)])
                except (ValueError, IndexError):
                    usb = input("  Enter drive path manually: ").strip()
            else:
                usb = input("  Enter USB drive path (e.g. /dev/sdb1): ").strip()
            if not usb:
                continue
            mode = input("  USB mode - wbfs partition or fat32? [wbfs/fat32]: ").strip().lower() or "wbfs"
            if mode == "wbfs":
                copy_to_usb_usb_wbfs_partition(f, usb, tools)
            else:
                copy_to_usb_fat32(f, usb)
        elif choice == "5":
            drives = detect_usb_drives()
            if drives:
                print("  Detected USB drives:")
                for d in drives:
                    print(f"    - {d}")
            else:
                print("  No USB drives detected.")
        elif choice == "6":
            drives = detect_usb_drives()
            if drives:
                print("  Detected drives:")
                for i, d in enumerate(drives):
                    print(f"    {i}) {d}")
                idx = input("  Select drive number: ").strip()
                try:
                    usb = _extract_device_path(drives[int(idx)])
                except (ValueError, IndexError):
                    usb = input("  Enter drive path (e.g. /dev/sdb1): ").strip()
                if usb:
                    tools = check_tools()
                    list_wbfs_games(usb, tools)
            else:
                print("  No USB drives detected.")
        else:
            print("  Invalid choice.")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Convert ISO/RVZ Wii games to WBFS and copy to USB.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s game.iso                     # Convert ISO -> WBFS in current dir
  %(prog)s game.rvz -o /output/dir      # Convert RVZ -> WBFS to output dir
  %(prog)s --batch /path/to/games       # Convert all ISO/RVZ in folder
  %(prog)s game.wbfs --usb /dev/sdb     # Copy WBFS to USB (WBFS partition)
  %(prog)s --list-usb                   # List detected USB drives
  %(prog)s --list-games /dev/sdb1       # List WBFS games on USB drive
  %(prog)s --gui                        # Launch graphical interface
  %(prog)s                              # Launch interactive menu

External tools required:
  - wit, wwt (Wiimms ISO Tools): https://wit.wiimm.de/
  - dolphin-tool (Dolphin Emulator): https://dolphin-emu.org/ (only for RVZ)
        """)

    parser.add_argument("input", nargs="?", help="Input file (ISO, RVZ, or WBFS)")
    parser.add_argument("-o", "--output", help="Output file or directory")
    parser.add_argument("--batch", metavar="DIR",
                        help="Batch convert all ISO/RVZ in DIR")
    parser.add_argument("--usb", metavar="DRIVE",
                        help="USB drive to copy to (e.g. /dev/sdb or E:)")
    parser.add_argument("--usb-mode", choices=["wbfs", "fat32"], default="wbfs",
                        help="USB partition mode: 'wbfs' (wwt) or 'fat32' (copy to /wbfs/)")
    parser.add_argument("--list-usb", action="store_true",
                        help="List detected USB drives and exit")
    parser.add_argument("--list-games", metavar="DRIVE",
                        help="List WBFS games on USB drive and exit")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Launch interactive menu")
    parser.add_argument("--gui", "-g", action="store_true",
                        help="Launch graphical interface (tkinter)")
    parser.add_argument("--no-color", action="store_true",
                        help="Disable colored output")

    args = parser.parse_args()

    # GUI mode
    if args.gui:
        launch_gui()
        return

    # Interactive mode
    if args.interactive:
        _run_interactive()
        return

    # No arguments -> launch GUI by default
    if not args.input and not args.batch and not args.list_usb and not args.list_games:
        launch_gui()
        return

    # CLI mode
    if args.list_usb:
        drives = detect_usb_drives()
        if drives:
            print("Detected USB drives:")
            for d in drives:
                print(f"  - {d}")
        else:
            print("No USB drives detected.")
        return

    if args.list_games:
        tools = check_tools()
        list_wbfs_games(args.list_games, tools)
        return

    if args.batch:
        tools = check_tools(require_dolphin=True)
        output_dir = args.output or "./output"
        batch_convert(args.batch, output_dir, tools)
        return

    if not args.input:
        parser.print_help()
        sys.exit(1)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    ext = input_path.suffix.lower()
    require_dolphin = ext == ".rvz"
    tools = check_tools(require_dolphin=require_dolphin)

    # Direct to USB WBFS partition (no local .wbfs file needed)
    if args.usb and args.usb_mode == "wbfs":
        if ext == ".iso":
            ok = iso_to_usb_wbfs(input_path, args.usb, tools)
        elif ext == ".rvz":
            ok = rvz_to_usb_wbfs(input_path, args.usb, tools)
        elif ext == ".wbfs":
            ok = copy_to_usb_usb_wbfs_partition(input_path, args.usb, tools)
        else:
            print(f"ERROR: Unsupported file format: {ext}", file=sys.stderr)
            sys.exit(1)
        if not ok:
            sys.exit(1)
        print("\nDone.")
        return

    # Local conversion
    if args.output:
        output_path = Path(args.output)
        if output_path.is_dir():
            output_path = output_path / input_path.with_suffix(".wbfs").name
    else:
        output_path = input_path.with_suffix(".wbfs")

    if ext == ".iso":
        ok = iso_to_wbfs(input_path, output_path, tools)
    elif ext == ".rvz":
        ok = rvz_to_wbfs(input_path, output_path, tools)
    elif ext == ".wbfs":
        ok = True
        output_path = input_path
    else:
        print(f"ERROR: Unsupported file format: {ext}", file=sys.stderr)
        sys.exit(1)

    if not ok:
        sys.exit(1)

    # Copy to USB FAT32 if requested
    if args.usb:
        copy_to_usb_fat32(output_path, args.usb)

    print("\nDone.")


if __name__ == "__main__":
    main()
