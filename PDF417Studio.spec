# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [
    ("assets/logo.png",   "."),   # toolbar logo + Linux/macOS window icon
    ("assets/app.ico",    "."),   # Windows taskbar / titlebar icon
    ("assets/card_bg.png","."),   # card background asset
]
binaries = []
hiddenimports = []

tmp_ret = collect_all('pdf417gen')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

tmp_ret = collect_all('barcode')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# python-barcode package (Code 128 support)
from PyInstaller.utils.hooks import collect_all as _ca
try:
    tmp_ret = _ca('python_barcode')
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
except Exception:
    pass

hiddenimports += [
    'barcode',
    'barcode.codex',
    'barcode.writer',
    'barcode.base',
    'barcode.errors',
    'barcode.isxn',
    'barcode.itf',
    'barcode.upc',
]


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PDF417Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/app.ico",        # ← Windows EXE icon (shows on desktop shortcut)
)
