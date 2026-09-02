#!/usr/bin/env python3
"""
Series-Centric Main Entry Point for DICOM Data Extraction Helper.

This is the primary entry point for the new series-centric architecture.
Use this to run the application with the new ImageSeries-based design.

Usage:
    python series_centric_main.py
"""

import sys
import os

# Add project root to path for imports
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Set QT environment variables for better appearance
os.environ['QT_API'] = 'pyside6'

from PySide6.QtWidgets import QApplication


def main():
    """Main entry point for the series-centric GUI application."""
    app = QApplication(sys.argv)
    app.setApplicationName("DICOM Data Extraction Helper - Series Centric")
    app.setOrganizationName("Inselspital")
    
    # Set application style
    app.setStyle('Fusion')
    
    # Import and create the series-centric main window
    try:
        from gui.series_centric_main_window import SeriesCentricMainWindow
        window = SeriesCentricMainWindow()
        print("Using series-centric architecture with ImageSeries as central model")
    except ImportError as e:
        print(f"Error: Series-centric architecture not available: {e}")
        print("Falling back to original architecture...")
        
        try:
            from gui.main_window import MainWindow
            window = MainWindow()
            print("Using original architecture")
        except ImportError as e2:
            print(f"Critical error: Neither architecture available: {e2}")
            sys.exit(1)
    
    # Show the window
    window.show()
    
    # Set window geometry if needed
    window.resize(1200, 800)
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())