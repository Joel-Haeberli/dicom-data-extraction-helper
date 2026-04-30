# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

# Add the parent directory to the path so we can import from the project root
pathex = ['..']

a = Analysis(
    ['main.py'],
    pathex=pathex,
    binaries=[],
    datas=[
        ('../README.md', '.'),
        ('../LICENSE', '.'),
        ('../CONTRIBUTING.md', '.'),
        ('../DICOM.md', '.'),
        ('../MATH.md', '.'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui', 
        'PySide6.QtWidgets',
        'PySide6.QtSvg',
        'PySide6.QtPrintSupport',
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
    excludes=['pydicom.data.test_files', 'pydicom.data.charset_files', 'pydicom.data.palettes'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

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
    upx=False,
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
