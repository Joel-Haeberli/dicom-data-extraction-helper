#!/usr/bin/env python3
"""
Build script for DICOM Data Extraction Helper
Creates standalone executables for Windows and Linux using PyInstaller

Usage:
    python package/build.py [--windows] [--linux] [--clean]

Examples:
    python package/build.py --windows    # Build for Windows
    python package/build.py --linux      # Build for Linux
    python package/build.py --both       # Build for both platforms
    python package/build.py --clean      # Clean build artifacts
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
PACKAGE_DIR = PROJECT_ROOT / "package"
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
VENV_DIR = PROJECT_ROOT / "venv"

# Required Python packages
REQUIREMENTS = [
    "pydicom>=2.4.0",
    "numpy>=1.24.0",
    "PySide6>=6.4.0",
    "pyinstaller>=5.0.0",
]


def is_windows():
    """Check if running on Windows."""
    return sys.platform.startswith('win')


def is_linux():
    """Check if running on Linux."""
    return sys.platform.startswith('linux')


def create_venv():
    """Create a virtual environment."""
    print("Creating virtual environment...")
    if VENV_DIR.exists():
        print("Virtual environment already exists. Skipping.")
        return
    
    python_exe = "python" if is_windows() else "python3"
    subprocess.run([python_exe, "-m", "venv", str(VENV_DIR)], check=True)


def install_dependencies():
    """Install Python dependencies in the virtual environment."""
    print("Installing dependencies...")
    
    pip_exe = str(VENV_DIR / ("Scripts" if is_windows() else "bin") / "pip")
    
    # Install from requirements
    requirements_file = PACKAGE_DIR / "requirements.txt"
    if requirements_file.exists():
        subprocess.run([pip_exe, "install", "-r", str(requirements_file)], check=True)
    else:
        # Fallback: install individual packages
        for pkg in REQUIREMENTS:
            subprocess.run([pip_exe, "install", pkg], check=True)


def get_pyinstaller_cmd(spec_file=None):
    """Get the PyInstaller command."""
    pyinstaller_exe = str(VENV_DIR / ("Scripts" if is_windows() else "bin") / "pyinstaller")
    
    if spec_file:
        return [pyinstaller_exe, str(spec_file)]
    
    # Default command line arguments
    cmd = [
        pyinstaller_exe,
        "--onefile",
        "--windowed",
        "--name", "DICOM-Data-Extraction-Helper",
        "--clean",
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
    ]
    
    # Add collect-all and hidden imports for dependencies
    cmd.extend([
        "--collect-all", "pydicom",
        "--collect-all", "numpy",
        "--hidden-import", "PySide6.QtCore",
        "--hidden-import", "PySide6.QtGui",
        "--hidden-import", "PySide6.QtWidgets",
        "--hidden-import", "PySide6.QtSvg",
        "--hidden-import", "PySide6.QtPrintSupport",
        "--hidden-import", "pydicom",
        "--hidden-import", "pydicom.dataset",
        "--hidden-import", "pydicom.tag",
        "--hidden-import", "pydicom.uid",
        "--hidden-import", "numpy",
        "--hidden-import", "numpy.core",
    ])
    
    # Add data files
    cmd.extend([
        "--add-data", "gui;gui",
        "--add-data", "dicom_header_extractor.py;.",
        "--add-data", "dicom_to_png.py;.",
        "--add-data", "dicom_hounsfield.py;.",
        "--add-data", "dicom_roi_overlay_printer.py;.",
        "--add-data", "dicom_dump_overlaydata.py;.",
        "--add-data", "dicom_presentation_state.py;.",
        "--add-data", "profile_analyzer.py;.",
        "--add-data", "profile_parser.py;.",
    ])
    
    # Add main script
    cmd.append("gui/main.py")
    
    return cmd


def build_with_spec():
    """Build using the spec file."""
    spec_file = PACKAGE_DIR / "dicom_helper.spec"
    if not spec_file.exists():
        print(f"Spec file not found: {spec_file}")
        return False
    
    print("Building with spec file...")
    cmd = get_pyinstaller_cmd(spec_file)
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return result.returncode == 0


def build_direct():
    """Build directly with PyInstaller."""
    print("Building directly with PyInstaller...")
    cmd = get_pyinstaller_cmd()
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return result.returncode == 0


def clean():
    """Clean build artifacts."""
    print("Cleaning build artifacts...")
    
    # Remove dist directory
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
        print(f"Removed {DIST_DIR}")
    
    # Remove build directory
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
        print(f"Removed {BUILD_DIR}")
    
    # Remove venv directory
    if VENV_DIR.exists():
        shutil.rmtree(VENV_DIR)
        print(f"Removed {VENV_DIR}")
    
    # Remove .PyInstaller directory
    pyinstaller_dir = PROJECT_ROOT / ".PyInstaller"
    if pyinstaller_dir.exists():
        shutil.rmtree(pyinstaller_dir)
        print(f"Removed {pyinstaller_dir}")
    
    # Remove spec file
    spec_file = PROJECT_ROOT / "DICOM-Data-Extraction-Helper.spec"
    if spec_file.exists():
        spec_file.unlink()
        print(f"Removed {spec_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Build DICOM Data Extraction Helper as standalone executable"
    )
    parser.add_argument(
        "--windows",
        action="store_true",
        help="Build for Windows"
    )
    parser.add_argument(
        "--linux",
        action="store_true",
        help="Build for Linux"
    )
    parser.add_argument(
        "--both",
        action="store_true",
        help="Build for both Windows and Linux"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean build artifacts"
    )
    parser.add_argument(
        "--spec",
        action="store_true",
        help="Use spec file for building"
    )
    
    args = parser.parse_args()
    
    if args.clean:
        clean()
        return
    
    # Determine platform
    build_windows = args.windows or args.both
    build_linux = args.linux or args.both
    
    if not build_windows and not build_linux:
        # Default to current platform
        build_windows = is_windows()
        build_linux = is_linux()
    
    # Check if we're on the right platform
    if build_windows and not is_windows():
        print("Error: Cannot build for Windows from a non-Windows system")
        sys.exit(1)
    
    if build_linux and not is_linux():
        print("Error: Cannot build for Linux from a non-Linux system")
        sys.exit(1)
    
    # Create venv and install dependencies
    create_venv()
    install_dependencies()
    
    # Build
    if args.spec:
        success = build_with_spec()
    else:
        success = build_direct()
    
    if success:
        print("\nBuild successful!")
        if is_windows():
            print(f"Executable: {DIST_DIR / 'DICOM-Data-Extraction-Helper.exe'}")
        else:
            print(f"Executable: {DIST_DIR / 'DICOM-Data-Extraction-Helper'}")
    else:
        print("\nBuild failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
