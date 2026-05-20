# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

block_cipher = None

# Collect everything vispy needs: data files (shaders, etc.), binaries, hidden imports
vispy_datas, vispy_binaries, vispy_hiddenimports = collect_all('vispy')

# Add the parent directory to the path so we can import from the project root
pathex = ['..']

a = Analysis(
    ['main.py'],
    pathex=pathex,
    binaries=[] + vispy_binaries,
    datas=[
        ('../README.md', '.'),
        ('../LICENSE', '.'),
        ('../CONTRIBUTING.md', '.'),
        ('../DICOM.md', '.'),
        ('../MATH.md', '.'),
    ] + vispy_datas,
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtSvg',
        'PySide6.QtPrintSupport',
        'PySide6.QtCharts',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
        'pydicom',
        'pydicom.dataset',
        'pydicom.tag',
        'pydicom.uid',
        'numpy',
        'numpy.core',
        'numpy.core._multiarray_umath',
        'encodings.ascii',
        'encodings.latin_1',
        # vispy core
        'vispy',
        'vispy.app',
        'vispy.app.backends',
        'vispy.app.backends._pyside6',
        'vispy.scene',
        'vispy.scene.cameras',
        'vispy.scene.visuals',
        'vispy.visuals',
        'vispy.visuals.transforms',
        'vispy.visuals.filters',
        'vispy.gloo',
        'vispy.gloo.gl',
        'vispy.gloo.gl.gl2',
        'vispy.io',
        'vispy.util',
        'vispy.color',
        'vispy.geometry',
        'vispy.glsl',
    ] + vispy_hiddenimports,
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
