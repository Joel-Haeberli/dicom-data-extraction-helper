# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Add the parent directory to the path so we can import from the project root
pathex = ['..']

a = Analysis(
    ['main.py'],
    pathex=pathex,
    binaries=[],
    datas=[('*.md', '.'), ('LICENSE', '.'), ('../README.md', '.'), ('../LICENSE', '.'), ('../CONTRIBUTING.md', '.'), ('../DICOM.md', '.'), ('../MATH.md', '.')],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui', 
        'PySide6.QtWidgets',
        'PySide6.QtSvg',
        'pydicom',
        'pydicom.dataset',
        'pydicom.tag',
        'pydicom.uid',
        'numpy',
        'numpy.core',
        'encodings.ascii',
        'encodings.latin_1',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Collect all necessary data from pydicom and numpy
tmp_ret = collect_all('pydicom')
a.datas += tmp_ret[0]
a.binaries += tmp_ret[1]
a.hiddenimports += tmp_ret[2]

tmp_ret = collect_all('numpy')
a.datas += tmp_ret[0]
a.binaries += tmp_ret[1]
a.hiddenimports += tmp_ret[2]

# Add the gui directory and its subdirectories
a.datas += [('gui', 'gui')]
a.datas += [('gui/utils', 'gui/utils')]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DICOM-Data-Extraction-Helper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon=None,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
