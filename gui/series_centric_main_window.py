#!/usr/bin/env python3
"""
Series-Centric Main Window for DICOM Data Extraction Helper.

This is a refactored version of the main window that uses the new
series-centric architecture with ImageSeries as the central model.

This demonstrates how the existing MainWindow can be gradually refactored
to use the new architecture while maintaining backward compatibility.
"""

from pathlib import Path
from typing import Optional, List
import sys

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSplitter, QMessageBox, QTabWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

try:
    from models import (
        ImageSeries, ImageSeriesManager, SeriesLoader, 
        ObservableImageSeriesManager, Measurement, MeasurementCollection
    )
    from gui.widgets.series_selector import SeriesSelector
    from gui.viewers import (
        SeriesPixelArrayTable, 
        SeriesImageViewer, 
        SeriesVolumeView,
        SeriesCurveView
    )
    from gui.explorer import DICOMExplorer
    HAS_NEW_ARCHITECTURE = True
except ImportError as e:
    print(f"Warning: New architecture not available: {e}")
    HAS_NEW_ARCHITECTURE = False


class SeriesCentricMainWindow(QMainWindow):
    """
    Series-centric main window that uses the new architecture.
    
    This window demonstrates the new series-centric design where:
    - ImageSeries is the central data model
    - All viewers work with the same ImageSeries objects
    - Navigation and selection are coordinated through the series manager
    """
    
    def __init__(self, parent=None):
        """Initialize the series-centric main window."""
        super().__init__(parent)
        
        # Set window properties
        self.setWindowTitle("DICOM Data Extraction Helper - Series Centric")
        self.setMinimumSize(1000, 700)
        
        # Check if new architecture is available
        if not HAS_NEW_ARCHITECTURE:
            QMessageBox.critical(
                self, 
                "Error", 
                "New architecture components are not available. "
                "Please ensure all new modules are installed correctly."
            )
            return
        
        # Initialize model layer
        self._series_loader = SeriesLoader()
        self._series_manager = ObservableImageSeriesManager(self)
        self._measurements = MeasurementCollection()
        
        # Initialize UI components
        self._create_components()
        
        # Setup layout
        self._setup_layout()
        
        # Connect signals
        self._connect_signals()
        
        # Initial state
        self._update_ui_state()
    
    def _create_components(self):
        """Create all UI components."""
        # Central widget
        self._central_widget = QWidget(self)
        self.setCentralWidget(self._central_widget)
        
        # DICOM Explorer
        self._explorer = DICOMExplorer(self)
        self._explorer.directory_selected.connect(self._on_directory_selected)
        
        # Series Selector
        self._series_selector = SeriesSelector(self._series_manager)
        self._series_selector.series_selected.connect(self._on_series_selected)
        
        # Create all viewers
        self._pixel_table = SeriesPixelArrayTable(self)
        self._image_viewer = SeriesImageViewer(self)
        self._volume_view = SeriesVolumeView(self)
        self._curve_view = SeriesCurveView(self)
        
        # Info label
        self._info_label = QLabel("No DICOM directory loaded", self)
        self._info_label.setStyleSheet("color: #e0e0e0; font-style: italic;")
    
    def _setup_layout(self):
        """Setup the main layout."""
        # Main layout for central widget
        main_layout = QVBoxLayout(self._central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)
        
        # Info label at the top
        main_layout.addWidget(self._info_label)
        
        # Main splitter for layout organization
        main_splitter = QSplitter(Qt.Horizontal, self)
        main_splitter.setHandleWidth(8)
        
        # Left panel: Explorer + Series Selector
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        
        # Add explorer (takes most of the space)
        left_layout.addWidget(self._explorer, 2)
        
        # Add series selector
        left_layout.addWidget(self._series_selector, 1)
        
        # Right panel: Tab widget with all viewers
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create tab widget for viewers
        self._viewer_tabs = QTabWidget(self)
        
        # Add viewers to tabs
        self._viewer_tabs.addTab(self._image_viewer, "Image Viewer")
        self._viewer_tabs.addTab(self._pixel_table, "Pixel Data")
        self._viewer_tabs.addTab(self._volume_view, "Volume View")
        self._viewer_tabs.addTab(self._curve_view, "HU Profile")
        
        right_layout.addWidget(self._viewer_tabs, 1)
        
        # Add panels to splitter
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        main_splitter.setStretchFactor(0, 1)  # Left panel: 1/4
        main_splitter.setStretchFactor(1, 3)  # Right panel: 3/4
        
        # Add splitter to main layout
        main_layout.addWidget(main_splitter, 1)
    
    def _connect_signals(self):
        """Connect all signals between components."""
        # Connect series manager signals to viewers
        self._series_manager.series_list_changed.connect(self._on_series_list_changed)
        self._series_manager.current_series_changed.connect(self._on_current_series_changed)
        
        # Connect pixel table navigation to series manager (if needed)
        # For now, the pixel table handles its own slice navigation
    
    def _on_directory_selected(self, path: Path):
        """Handle directory selection from explorer."""
        try:
            self._info_label.setText(f"Loading: {path.name}...")
            
            # Load series from directory using the new SeriesLoader
            series_list = self._series_loader.load_series_from_directory(path)
            
            if not series_list:
                QMessageBox.information(
                    self,
                    "No Series Found",
                    f"No DICOM series found in:\n{path}"
                )
                self._info_label.setText(f"No series in: {path.name}")
                return
            
            # Load series into manager
            self._series_manager.load_series_list(series_list)
            
            # Update info
            series_count = len(series_list)
            total_slices = sum(s.num_slices for s in series_list)
            self._info_label.setText(f"Loaded {series_count} series ({total_slices} slices) from: {path.name}")
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Loading Series",
                f"Failed to load series from {path}:\n{str(e)}"
            )
            self._info_label.setText("Error loading series")
    
    def _on_series_list_changed(self, series_list: List[ImageSeries]):
        """Handle changes in available series."""
        self._update_ui_state()
    
    def _on_current_series_changed(self, series: Optional[ImageSeries]):
        """Handle changes in current series selection."""
        # Update all viewers with the new series
        if self._pixel_table:
            self._pixel_table.series = series
        if self._image_viewer:
            self._image_viewer.series = series
        if self._volume_view:
            self._volume_view.series = series
        if self._curve_view:
            self._curve_view.series = series
        
        self._update_ui_state()
    
    def _on_series_selected(self, series: ImageSeries):
        """Handle user selection of a series from the selector."""
        # Set the selected series as current
        self._series_manager.set_current_series(series)
    
    def _update_ui_state(self):
        """Update UI state based on current data."""
        has_series = self._series_manager.has_series
        current_series = self._series_manager.current_series
        
        # Update info label
        if current_series:
            self._info_label.setText(
                f"Series: {current_series.series_description or current_series.series_uid} "
                f"| Slice: {self._pixel_table.current_slice + 1}/{current_series.num_slices}"
            )
        elif has_series:
            series_count = len(self._series_manager.available_series)
            current_series = self._series_manager.current_series
            if current_series:
                self._info_label.setText(
                    f"{series_count} series available - Current: {current_series.series_description or current_series.series_uid}"
                )
            else:
                self._info_label.setText(f"{series_count} series available - select one")
        else:
            self._info_label.setText("No DICOM directory loaded")
        
        # Enable/disable components based on state
        self._series_selector.set_enabled(has_series)
        
        if self._pixel_table:
            self._pixel_table.setEnabled(has_series)
    
    def next_slice(self):
        """Navigate to next slice in all viewers."""
        if self._pixel_table:
            self._pixel_table.next_slice()
        if self._image_viewer:
            self._image_viewer.next_slice()
        if self._volume_view:
            self._volume_view.next_slice()
        if self._curve_view:
            self._curve_view.next_slice()
    
    def prev_slice(self):
        """Navigate to previous slice in all viewers."""
        if self._pixel_table:
            self._pixel_table.prev_slice()
        if self._image_viewer:
            self._image_viewer.prev_slice()
        if self._volume_view:
            self._volume_view.prev_slice()
        if self._curve_view:
            self._curve_view.prev_slice()
    
    def go_to_slice(self, index: int):
        """Go to specific slice in all viewers."""
        if self._pixel_table:
            self._pixel_table.go_to_slice(index)
        if self._image_viewer:
            self._image_viewer.go_to_slice(index)
        if self._volume_view:
            self._volume_view.go_to_slice(index)
        if self._curve_view:
            self._curve_view.go_to_slice(index)
    
    def keyPressEvent(self, event):
        """Handle key press events for slice navigation."""
        if event.key() == Qt.Key_Right:
            self.next_slice()
            event.accept()
        elif event.key() == Qt.Key_Left:
            self.prev_slice()
            event.accept()
        else:
            super().keyPressEvent(event)
    
    def closeEvent(self, event):
        """Handle window close."""
        # Clean up if needed
        event.accept()