# -*- mode: python ; coding: utf-8 -*-
#
# Build requirements: all packages in ../requirements.txt must be installed
# in the Python / venv that PyInstaller uses.
#   pip install -r ../requirements.txt
#
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files
import importlib.util, sys

# Abort early with a clear message if vispy is not installed in this environment
if importlib.util.find_spec('vispy') is None:
    sys.exit(
        '\n\nERROR: vispy is not installed in the current Python environment.\n'
        'Run:  pip install -r ../requirements.txt\n'
        'then re-run PyInstaller.\n'
    )

block_cipher = None

vispy_datas, vispy_binaries, vispy_hidden = collect_all('vispy')

a = Analysis(
    ['main.py'],
    pathex=['..'],
    binaries=[] + vispy_binaries,
    datas=[
        ('../README.md', '.'),
        ('../LICENSE', '.'),
        ('../CONTRIBUTING.md', '.'),
        ('../DICOM.md', '.'),
        ('../MATH.md', '.'),
    ] + vispy_datas,
    hiddenimports=[
        # Qt
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtSvg',
        'PySide6.QtPrintSupport',
        'PySide6.QtCharts',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
        # pydicom
        'pydicom',
        'pydicom.dataset',
        'pydicom.tag',
        'pydicom.uid',
        # numpy
        'numpy',
        'numpy.core',
        'numpy.core._multiarray_umath',
        # encodings
        'encodings.ascii',
        'encodings.latin_1',
        'encodings.utf_8',
        # vispy — explicit backend + GL paths
        'vispy',
        'vispy.app',
        'vispy.app.backends',
        'vispy.app.backends._pyside6',
        'vispy.scene',
        'vispy.scene.cameras',
        'vispy.scene.visuals',
        'vispy.visuals',
        'vispy.visuals.transforms',
        'vispy.visuals.transforms._base',
        'vispy.visuals.transforms.linear',
        'vispy.visuals.filters',
        'vispy.gloo',
        'vispy.gloo.gl',
        'vispy.gloo.gl.gl2',
        'vispy.gloo.gl.pyopengl2',
        'vispy.gloo.gl.desktop',
        'vispy.io',
        'vispy.util',
        'vispy.util.fonts',
        'vispy.color',
        'vispy.geometry',
        'vispy.glsl',
        # PyOpenGL (vispy GL fallback on Windows)
        'OpenGL',
        'OpenGL.GL',
        'OpenGL.platform',
        'OpenGL.platform.win32',
        'OpenGL.arrays',
        'OpenGL.arrays.numpymodule',
        'OpenGL.extensions',
    ] + vispy_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pydicom.data.test_files',
        'pydicom.data.charset_files',
        'pydicom.data.palettes',
    ],
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
