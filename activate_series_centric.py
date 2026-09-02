#!/usr/bin/env python3
"""
Activation Script for Series-Centric Architecture

This script activates the new series-centric architecture by:
1. Ensuring all required modules are available
2. Setting the default main window to use the new architecture
3. Providing a simple way to test the new implementation

Usage:
    python activate_series_centric.py [--test]
    
    With --test: Run a basic test to verify all components work
    Without --test: Just verify imports and print status
"""

import sys
import os

def test_imports():
    """Test all imports for the series-centric architecture."""
    print("Testing series-centric architecture imports...")
    
    tests = [
        ("Core models", "from models import ImageSeries, ImageSlice, ImageSeriesManager, SeriesLoader, ObservableImageSeriesManager"),
        ("Measurement models", "from models.measurement import Measurement, MeasurementCollection"),
        ("Services", "from services import AnalysisService, ExportService, MeasurementService"),
        ("Viewers", "from gui.viewers import SeriesViewer, SeriesViewerWidget, SeriesPixelArrayTable, SeriesImageViewer, SeriesVolumeView, SeriesCurveView"),
        ("Widgets", "from gui.widgets.series_selector import SeriesSelector"),
        ("CLI tools", "from cli import find_dicom_files, TAG_CATEGORIES"),
        ("Backward compatibility", "from gui.curve_view import CurveView"),
        ("Series-centric window", "from gui.series_centric_main_window import SeriesCentricMainWindow"),
    ]
    
    passed = 0
    failed = 0
    
    for name, import_statement in tests:
        try:
            exec(import_statement)
            print(f"✓ {name}")
            passed += 1
        except Exception as e:
            print(f"✗ {name}: {e}")
            failed += 1
    
    print(f"\nImport test results: {passed} passed, {failed} failed")
    return failed == 0


def test_window_creation():
    """Test that we can create the series-centric main window."""
    print("\nTesting window creation...")
    
    try:
        from PySide6.QtWidgets import QApplication
        import sys
        
        app = QApplication(sys.argv)
        
        from gui.series_centric_main_window import SeriesCentricMainWindow
        window = SeriesCentricMainWindow()
        
        # Verify all components
        components = [
            ('Series Loader', window._series_loader),
            ('Series Manager', window._series_manager),
            ('Explorer', window._explorer),
            ('Series Selector', window._series_selector),
            ('Pixel Table', window._pixel_table),
            ('Image Viewer', window._image_viewer),
            ('Volume View', window._volume_view),
            ('Curve View', window._curve_view),
            ('Viewer Tabs', window._viewer_tabs),
        ]
        
        for name, component in components:
            if component:
                print(f"✓ {name}")
            else:
                print(f"✗ {name} is None")
                return False
        
        app.quit()
        print("✓ Window creation test passed")
        return True
        
    except Exception as e:
        print(f"✗ Window creation test failed: {e}")
        return False


def run_full_test():
    """Run a complete test of the series-centric architecture."""
    print("Running full series-centric architecture test...\n")
    
    imports_ok = test_imports()
    if not imports_ok:
        print("Import tests failed, skipping window creation test")
        return False
    
    window_ok = test_window_creation()
    
    if imports_ok and window_ok:
        print("\n🎉 All series-centric architecture tests passed!")
        print("The new architecture is ready to use.")
        return True
    else:
        print("\n❌ Some tests failed. Please check the error messages above.")
        return False


def main():
    """Main activation function."""
    print("Series-Centric Architecture Activation")
    print("=" * 50)
    
    # Parse command line arguments
    test_mode = '--test' in sys.argv
    
    if test_mode:
        success = run_full_test()
        return 0 if success else 1
    else:
        # Just test imports
        success = test_imports()
        if success:
            print("\n✅ Series-centric architecture imports successful!")
            print("\nTo use the new architecture:")
            print("1. Run: python series_centric_main.py")
            print("2. Or import: from gui.series_centric_main_window import SeriesCentricMainWindow")
            print("\nTo run full tests:")
            print("python activate_series_centric.py --test")
        else:
            print("\n❌ Some imports failed. The new architecture may not be fully available.")
        
        return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())