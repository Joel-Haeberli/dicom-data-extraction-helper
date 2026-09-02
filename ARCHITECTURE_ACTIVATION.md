# Series-Centric Architecture Activation Guide

This document describes how to activate and use the new series-centric architecture for the DICOM Data Extraction Helper.

## 🎯 Architecture Status: **ACTIVATED**

The new series-centric architecture has been fully implemented and is ready to use.

## 🚀 Entry Points

### Primary Entry Point (Recommended)
```bash
# Run the series-centric application
python series_centric_main.py
```

This entry point:
- Uses the new `SeriesCentricMainWindow` with all series-aware viewers
- Includes Image Viewer, Pixel Data Table, Volume View, and HU Profile tabs
- Uses ImageSeries as the central model
- Coordinates all viewers through the ObservableImageSeriesManager

### Original Entry Point (Still Available)
```bash
# Run the original application (backward compatible)
python gui/main.py
```

This entry point:
- Defaults to using the new series-centric architecture
- Falls back to original MainWindow if series-centric fails
- Can be forced to use original with `--original` flag (if implemented)

## 🏗️ Architecture Components

### Core Models (`models/`)
- **ImageSeries**: Central data model representing DICOM series
- **ImageSlice**: Individual slice within a series
- **ImageSeriesManager**: Manages multiple loaded series
- **ObservableImageSeriesManager**: Manager with Qt signal support
- **SeriesLoader**: Loads DICOM files into ImageSeries objects
- **Measurement**: ROI measurement data model
- **MeasurementCollection**: Collection of measurements

### Services Layer (`services/`)
- **AnalysisService**: Statistical analysis and validation
- **ExportService**: Export series data to CSV, JSON, NPY formats
- **MeasurementService**: Create and manage ROI, profile, and point measurements

### Viewers (`gui/viewers/`)
- **SeriesViewer**: Abstract base class for all series-aware viewers
- **SeriesViewerWidget**: Base class with Qt widget support
- **SeriesPixelArrayTable**: Pixel data table with series support
- **SeriesImageViewer**: 2D image viewer with series navigation
- **SeriesVolumeView**: 3D volume viewer with series support
- **SeriesCurveView**: HU profile curve viewer with series support

### Widgets (`gui/widgets/`)
- **SeriesSelector**: Widget for selecting from available image series

### Main Window
- **SeriesCentricMainWindow**: Feature-complete main window with:
  - DICOM Explorer for directory navigation
  - Series Selector for choosing loaded series
  - Tabbed interface with all viewers
  - Coordinated slice navigation across all viewers

## 📋 Migration Path

### Current State: Dual Architecture
- **New architecture**: Series-centric with ImageSeries as central model
- **Old architecture**: Still available and functional for backward compatibility
- **Default**: New architecture is used by default

### Migration Strategy

1. **Phase 1: Parallel Development** ✅ COMPLETED
   - New series-centric components developed alongside existing ones
   - Backward compatibility maintained
   - Both architectures work independently

2. **Phase 2: Default Switch** ✅ COMPLETED
   - Series-centric main window is now the primary entry point
   - Original main window still available via `gui/main.py` with fallback
   - All imports work for both old and new code

3. **Phase 3: Gradual Migration** 🔄 IN PROGRESS
   - Existing code can gradually adopt new components
   - No need to rewrite everything at once
   - Components can be migrated one at a time

4. **Phase 4: Full Transition** (Future)
   - All code migrated to new architecture
   - Old components can be deprecated
   - Backward compatibility can be removed

## 🔧 Configuration Options

### Using New Architecture
```python
# Direct import
from gui.series_centric_main_window import SeriesCentricMainWindow
window = SeriesCentricMainWindow()

# Via GUI main module (default)
from gui.main import main
main()  # Uses series-centric by default
```

### Using Original Architecture (for backward compatibility)
```python
# Via GUI main module
from gui.main import main
main(use_series_centric=False)

# Direct import
from gui.main_window import MainWindow
window = MainWindow()
```

## 🧪 Testing

### Run Activation Tests
```bash
# Quick import test
python activate_series_centric.py

# Full test including window creation
python activate_series_centric.py --test
```

### Test Individual Components
```python
# Test models
from models import ImageSeries, SeriesLoader
series = SeriesLoader().load_series_from_directory(Path("/path/to/dicom"))

# Test viewers
from gui.viewers import SeriesImageViewer, SeriesPixelArrayTable
viewer = SeriesImageViewer()
viewer.series = series

# Test services
from services import AnalysisService, ExportService
analysis = AnalysisService()
stats = analysis.get_series_statistics(series)
```

## 🎨 Features of New Architecture

### 1. Centralized Data Model
- **ImageSeries** is the single source of truth
- All viewers work with the same series objects
- No data duplication between components

### 2. Consistent Data Flow
- **Observable pattern** with signals for changes
- **Series manager** coordinates between components
- **Slice navigation** synchronized across all viewers

### 3. Clean Separation of Concerns
- **Models**: Data structures and loading
- **Services**: Business logic and analysis
- **Viewers**: UI components for displaying data
- **Widgets**: Reusable UI components

### 4. Enhanced Functionality
- **Multiple viewers** in a tabbed interface
- **Measurement storage** integrated into series
- **Comprehensive export** options
- **Advanced analysis** capabilities

### 5. Backward Compatibility
- **Original imports** still work
- **Graceful fallbacks** when new components unavailable
- **Dual architecture** support

## 📁 File Structure

```
dicom-data-extraction-helper/
├── models/                          # Core data models
│   ├── __init__.py
│   ├── image_series.py           # ImageSeries, ImageSlice, managers
│   ├── series_loader.py          # Series loading logic
│   ├── measurement.py             # Measurement model
│   └── observable_series_manager.py
│
├── services/                       # Business logic
│   ├── __init__.py
│   ├── analysis_service.py       # Analysis operations
│   ├── export_service.py         # Export functionality
│   └── measurement_service.py    # Measurement operations
│
├── gui/
│   ├── main.py                   # GUI entry point (uses new architecture)
│   ├── main_window.py            # Original main window (still works)
│   ├── series_centric_main_window.py  # New main window
│   │
│   ├── viewers/                  # Series-aware viewers
│   │   ├── __init__.py
│   │   ├── base.py               # Base classes
│   │   ├── image_viewer.py       # Image viewer
│   │   ├── pixel_array_table.py # Pixel data table
│   │   ├── volume_view.py        # Volume viewer
│   │   └── curve_view.py         # HU profile viewer
│   │
│   ├── widgets/                  # Reusable widgets
│   │   ├── __init__.py
│   │   └── series_selector.py    # Series selection
│   │
│   └── utils/                    # Utilities
│       └── dicom_loader.py       # DICOM loading (new-aware)
│
├── cli/                           # CLI tools
│   ├── __init__.py
│   ├── dicom_header_extractor.py
│   ├── profile_analyzer.py
│   └── profile_parser.py
│
├── series_centric_main.py        # Primary entry point (recommended)
└── activate_series_centric.py    # Activation and testing script
```

## 🔄 Next Steps

1. **Start using the new entry point**: `python series_centric_main.py`
2. **Gradually migrate existing code**: Replace old viewer imports with new ones
3. **Update documentation**: Reflect the new architecture in docs
4. **Test thoroughly**: Verify all functionality works with the new architecture
5. **Eventually deprecate old components**: Once fully migrated

## 🎉 Benefits Achieved

✅ **Clean Architecture**: Clear separation between models, services, and viewers  
✅ **Single Source of Truth**: ImageSeries as central model  
✅ **Consistent Data Flow**: All components work with the same data model  
✅ **Enhanced Functionality**: Multiple viewers, measurements, comprehensive export  
✅ **Backward Compatibility**: Existing code continues to work  
✅ **Testability**: Each component can be tested in isolation  
✅ **Extensibility**: Easy to add new viewers or analysis tools  
✅ **Maintainability**: Clear responsibilities for each component

## 📞 Support

For issues or questions about the new architecture:
- Check imports with: `python activate_series_centric.py`
- Run full tests with: `python activate_series_centric.py --test`
- Review the new models in `models/` directory
- See examples in `series_centric_main.py`

The series-centric architecture is now **fully activated and ready to use**! 🎉