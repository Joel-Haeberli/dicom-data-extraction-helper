#!/usr/bin/env python3
"""
Quick test to verify PyInstaller can find all dependencies
Run from project root: python package/test_build.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))
os.chdir(project_root)

def test_imports():
    """Test that all required imports work."""
    print("Testing imports...")
    
    try:
        import pydicom
        print(f"✓ pydicom: {pydicom.__version__}")
    except ImportError as e:
        print(f"✗ pydicom: {e}")
        return False
    
    try:
        import numpy
        print(f"✓ numpy: {numpy.__version__}")
    except ImportError as e:
        print(f"✗ numpy: {e}")
        return False
    
    try:
        from PySide6.QtCore import QObject
        from PySide6.QtGui import QImage
        from PySide6.QtWidgets import QApplication
        print("✓ PySide6")
    except ImportError as e:
        print(f"✗ PySide6: {e}")
        return False
    
    try:
        import gui.main_window
        print("✓ gui.main_window")
    except ImportError as e:
        print(f"✗ gui.main_window: {e}")
        return False
    
    try:
        import gui.pixel_array_table
        print("✓ gui.pixel_array_table")
    except ImportError as e:
        print(f"✗ gui.pixel_array_table: {e}")
        return False
    
    try:
        import gui.metadata_table
        print("✓ gui.metadata_table")
    except ImportError as e:
        print(f"✗ gui.metadata_table: {e}")
        return False
    
    try:
        import gui.image_tabs
        print("✓ gui.image_tabs")
    except ImportError as e:
        print(f"✗ gui.image_tabs: {e}")
        return False
    
    try:
        from gui.utils.dicom_loader import DICOMLoader
        print("✓ gui.utils.dicom_loader")
    except ImportError as e:
        print(f"✗ gui.utils.dicom_loader: {e}")
        return False
    
    try:
        from gui.utils.image_utils import dicom_to_qimage
        print("✓ gui.utils.image_utils")
    except ImportError as e:
        print(f"✗ gui.utils.image_utils: {e}")
        return False
    
    print("\nAll imports successful!")
    return True

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
