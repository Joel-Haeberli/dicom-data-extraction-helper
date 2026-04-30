#!/usr/bin/env python3
"""
DICOM Data Extraction Helper - GUI Application Entry Point

A PySide6-based desktop application for viewing DICOM images with metadata
and overlay support.
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    """Main entry point for the GUI application."""
    app = QApplication(sys.argv)
    app.setApplicationName("DICOM Data Extraction Helper")
    app.setOrganizationName("Inselspital")
    
    # Import and create main window here to avoid circular imports
    from gui.main_window import MainWindow
    
    window = MainWindow()
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
