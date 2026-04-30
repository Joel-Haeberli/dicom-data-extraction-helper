# Hook for pydicom to ensure all necessary data files are included
# Place this file in a hooks directory and reference it in your spec file

from PyInstaller.utils.hooks import collect_data_files

# Collect pydicom character set data files
datas = collect_data_files('pydicom', include_py_files=False)

# Also explicitly include the encodings directory
# This ensures pydicom can find its character set mappings
import os
import pydicom

# Get the path to pydicom's data
try:
    pydicom_path = os.path.dirname(pydicom.__file__)
    encodings_path = os.path.join(pydicom_path, 'encodings')
    if os.path.exists(encodings_path):
        datas += [(encodings_path, 'pydicom/encodings')]
except Exception:
    pass

# Also include the character set Python files
try:
    charset_path = os.path.join(pydicom_path, 'charset.py')
    if os.path.exists(charset_path):
        datas += [(charset_path, 'pydicom')]
except Exception:
    pass
