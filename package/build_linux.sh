#!/bin/bash
# Build script for Linux using PyInstaller

set -e

echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "Installing dependencies..."
pip install -r package/requirements.txt

echo "Building executable..."
pyinstaller \
  --onefile \
  --windowed \
  --name "DICOM-Data-Extraction-Helper" \
  --clean \
  --distpath dist \
  --workpath build \
  --add-data "gui:gui" \
  --add-data "dicom_header_extractor.py:." \
  --add-data "dicom_to_png.py:." \
  --add-data "dicom_hounsfield.py:." \
  --add-data "dicom_roi_overlay_printer.py:." \
  --add-data "dicom_dump_overlaydata.py:." \
  --add-data "dicom_presentation_state.py:." \
  --add-data "profile_analyzer.py:." \
  --add-data "profile_parser.py:." \
  --hidden-import PySide6.QtCore \
  --hidden-import PySide6.QtGui \
  --hidden-import PySide6.QtWidgets \
  --hidden-import PySide6.QtSvg \
  --hidden-import PySide6.QtPrintSupport \
  --collect-all pydicom \
  --collect-all numpy \
  --hidden-import pydicom \
  --hidden-import pydicom.dataset \
  --hidden-import pydicom.tag \
  --hidden-import pydicom.uid \
  --hidden-import numpy \
  --hidden-import numpy.core \
  gui/main.py

echo ""
echo "Build complete! Executable is in dist/DICOM-Data-Extraction-Helper"
echo ""
echo "To run: ./dist/DICOM-Data-Extraction-Helper"
