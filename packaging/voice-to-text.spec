# PyInstaller spec — build with: packaging/build.sh
import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

datas = [
    (os.path.join(ROOT, "assets", "check.svg"), "assets"),
    (os.path.join(ROOT, "assets", "chevron.png"), "assets"),
    (os.path.join(ROOT, "assets", "icon.svg"), "assets"),
    (os.path.join(ROOT, "src", "audio", "beep_up.wav"), os.path.join("src", "audio")),
    (os.path.join(ROOT, "src", "audio", "beep_down.wav"), os.path.join("src", "audio")),
]
datas += collect_data_files("faster_whisper")  # Silero VAD assets

binaries = collect_dynamic_libs("ctranslate2")
# CUDA 12 runtime libs (cuBLAS / cuDNN) loaded at startup by stt_engine._load_nvidia_libraries
# ("nvidia" is a namespace package, so collect_dynamic_libs can't see it; glob it and
# keep the nvidia/<pkg>/lib layout the loader expects)
import glob
import site

for sp in site.getsitepackages():
    for lib in glob.glob(os.path.join(sp, "nvidia", "*", "lib", "*.so*")):
        binaries.append((lib, os.path.relpath(os.path.dirname(lib), sp)))

hiddenimports = collect_submodules("pynput")
if sys.platform.startswith("linux"):
    # pynput selects its backend dynamically and discovery can run without X11.
    hiddenimports += ["pynput.keyboard._xorg", "pynput.mouse._xorg"]

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="voice-to-text",
    console=False,
    strip=False,
    upx=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="voice-to-text",
    strip=False,
    upx=False,
)
