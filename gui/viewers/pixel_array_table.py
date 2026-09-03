#!/usr/bin/env python3
"""
Series-Aware Pixel Array Table for DICOM Data Extraction Helper.

This refactored version inherits from SeriesViewerWidget to work with
ImageSeries objects instead of individual DICOM files.

This is a proof of concept for the new series-centric architecture.
"""

from typing import Optional, List, Any, Dict, Tuple, TYPE_CHECKING
import numpy as np

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QHeaderView, QScrollArea, QSizePolicy, 
    QFrame, QTabWidget, QSpinBox, QCheckBox, QPushButton, QComboBox
)
from PySide6.QtCore import Qt, Signal, QModelIndex, QAbstractTableModel
from PySide6.QtGui import QColor, QPalette, QBrush, QFont

if TYPE_CHECKING:
    from services.measurement_service import MeasurementService
    from models.measurement import Measurement

try:
    from models.image_series import ImageSeries, ImageSlice
    HAS_MODELS = True
except ImportError:
    HAS_MODELS = False
    ImageSeries = Any
    ImageSlice = Any

try:
    import pydicom
    from pydicom.dataset import Dataset
    HAS_PYDICOM = True
except ImportError:
    HAS_PYDICOM = False

from .base import SeriesViewerWidget


class SeriesPixelArrayModel(QAbstractTableModel):
    """
    Custom table model for pixel array data from ImageSeries.
    
    This allows efficient display of pixel data with lazy loading and windowing.
    """
    
    def __init__(self, series: Optional[ImageSeries] = None, 
                 current_slice: int = 0, 
                 show_hu: bool = False, 
                 slope: float = 1.0, 
                 intercept: float = 0.0, 
                 parent=None):
        super().__init__(parent)
        self._series = series
        self._current_slice_index = current_slice
        self._show_hu = show_hu
        self._slope = slope
        self._intercept = intercept
        
        # Window settings (0 means use full array)
        self._window_x = 0
        self._window_y = 0 
        self._window_width = 30  # Default window size
        self._window_height = 30
        
        # Zoom settings
        self._zoom_factor = 1
    
    def set_series(self, series: Optional[ImageSeries]):
        """Set the series and reset the model."""
        self.beginResetModel()
        self._series = series
        self._current_slice_index = 0
        self.endResetModel()
    
    def set_current_slice(self, index: int):
        """Set the current slice index."""
        if index != self._current_slice_index:
            self.beginResetModel()
            self._current_slice_index = index
            self.endResetModel()
    
    def set_window(self, x: int, y: int, width: int, height: int):
        """Set the window region to display."""
        if (x != self._window_x or y != self._window_y or 
            width != self._window_width or height != self._window_height):
            self._window_x = x
            self._window_y = y
            self._window_width = width
            self._window_height = height
            self.layoutChanged.emit()
    
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        
        if not self._series or self._current_slice_index >= self._series.num_slices:
            return 0
        
        slice_obj = self._series.get_slice(self._current_slice_index)
        if not slice_obj or slice_obj.pixel_array is None:
            return 0
            
        pixel_array = slice_obj.pixel_array
        
        # Apply windowing
        if self._window_height > 0:
            start_row = self._window_y
            end_row = min(start_row + self._window_height, pixel_array.shape[0])
            return end_row - start_row
        else:
            return pixel_array.shape[0]
    
    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
            
        if not self._series or self._current_slice_index >= self._series.num_slices:
            return 0
            
        slice_obj = self._series.get_slice(self._current_slice_index)
        if not slice_obj or slice_obj.pixel_array is None:
            return 0
            
        pixel_array = slice_obj.pixel_array
        
        # Apply windowing
        if self._window_width > 0:
            start_col = self._window_x
            end_col = min(start_col + self._window_width, pixel_array.shape[1])
            return end_col - start_col
        else:
            return pixel_array.shape[1]
    
    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
            
        if not self._series or self._current_slice_index >= self._series.num_slices:
            return None
            
        slice_obj = self._series.get_slice(self._current_slice_index)
        if not slice_obj or slice_obj.pixel_array is None:
            return None
            
        pixel_array = slice_obj.pixel_array
        
        # Calculate actual position in pixel array considering window
        actual_row = self._window_y + index.row() if self._window_height > 0 else index.row()
        actual_col = self._window_x + index.column() if self._window_width > 0 else index.column()
        
        if actual_row >= pixel_array.shape[0] or actual_col >= pixel_array.shape[1]:
            return None
            
        pixel_value = pixel_array[actual_row, actual_col]
        
        if role == Qt.DisplayRole:
            # Convert to HU if requested
            if self._show_hu:
                hu_value = pixel_value * self._slope + self._intercept
                return f"{hu_value:.1f}"
            else:
                return str(int(pixel_value))
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignRight | Qt.AlignVCenter
            
        return None
    
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._window_x + section) if self._window_width > 0 else str(section)
            else:  # Qt.Vertical
                return str(self._window_y + section) if self._window_height > 0 else str(section)
        return None


class SeriesPixelArrayTable(SeriesViewerWidget):
    """
    Series-aware pixel array table widget.
    
    This is a refactored version of the original PixelArrayTable that works
    with ImageSeries objects instead of individual DICOM files.
    
    Features:
    - Displays pixel data from the current series and slice
    - Configurable window size and position
    - Shows raw or HU values
    - Supports slice navigation through the SeriesViewer interface
    
    Signals:
    - Inherits signals from SeriesViewerWidget
    - Additional signals for pixel data interactions
    """
    
    # Additional signals specific to pixel array display
    window_changed = Signal(int, int, int, int)  # x, y, width, height
    pixel_selected = Signal(int, int)  # row, col of selected pixel
    measurement_captured = Signal(str)  # measurement_id
    cursor_position_changed = Signal(int, int)  # x, y
    roi_parameters_changed = Signal(int, str)  # size, form
    
    def __init__(self, parent=None, measurement_service: Optional['MeasurementService'] = None):
        """Initialize the series pixel array table."""
        # Call parent with call_setup_widget=False to avoid double setup
        super().__init__(parent, call_setup_widget=False)
        
        # Additional state
        self._show_hu = False
        self._slope = 1.0
        self._intercept = 0.0
        self._window_x = 0
        self._window_y = 0
        self._window_width = 30
        self._window_height = 30
        
        # Measurement mode state
        self._measurement_mode_enabled = False
        self._cursor_x = 0  # Cursor position in pixel coordinates
        self._cursor_y = 0
        self._cursor_size = 3  # Size for ROI measurements
        self._roi_form = 'square'  # circle, square, cross
        self._highlight_roi = True  # Whether to highlight ROI region
        
        # ROI display state
        self._highlight_circle = False  # False = rectangle, True = circle
        self._circle_diameter = 0
        self._circle_center_x = 0
        self._circle_center_y = 0
        
        # Measurement service integration
        self._measurement_service = measurement_service
        
        # Setup UI
        self._setup_ui()
    
    def _setup_widget(self):
        """Setup the widget appearance."""
        # This is called by parent constructor
        pass
    
    def _setup_ui(self):
        """Setup the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Create info label
        self._info_label = QLabel("No series loaded", self)
        self._info_label.setStyleSheet("color: #e0e0e0; font-style: italic;")
        layout.addWidget(self._info_label)
        
        # Create the table widget
        self._table = QTableWidget(self)
        self._table.setMinimumSize(200, 200)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setSelectionBehavior(QTableWidget.SelectItems)
        
        # Set up styling for dark mode
        self._table.setStyleSheet("""
            QTableWidget {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #444;
                gridline-color: #444;
            }
            QHeaderView::section {
                background-color: #3c3c3c;
                color: #e0e0e0;
                padding: 4px;
                border: 1px solid #444;
            }
            QTableWidget::item:selected {
                background-color: #0078d7;
                color: #ffffff;
            }
        """)
        
        # Configure table behavior
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.verticalHeader().setStretchLastSection(False)
        self._table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Add table to layout
        layout.addWidget(self._table, 1)
        
        # Create control panel
        self._create_control_panel(layout)
        
        # Connect signals
        self.series_changed.connect(self._on_series_changed)
        self.slice_changed.connect(self._on_slice_changed)
        self._table.itemClicked.connect(self._on_table_item_clicked)
    
    def _sync_with_measurement_service(self):
        """Sync this viewer's state with the measurement service."""
        if self._measurement_service:
            self._measurement_mode_enabled = self._measurement_service.measurement_mode_enabled
            self._cursor_size = self._measurement_service.cursor_size
            self._roi_form = self._measurement_service.roi_form
            self._cursor_x, self._cursor_y = self._measurement_service.cursor_position
            self._current_slice = self._measurement_service.current_slice_index
            
            # Update UI to reflect service state
            self._measurement_mode_checkbox.setChecked(self._measurement_mode_enabled)
            self._cursor_size_spin.setValue(self._cursor_size)
            self._roi_form_combo.setCurrentText(self._roi_form)
    
    def _sync_measurement_mode_to_service(self):
        """Sync this viewer's measurement mode state to the service."""
        if self._measurement_service:
            self._measurement_service.measurement_mode_enabled = self._measurement_mode_enabled
            self._measurement_service.cursor_size = self._cursor_size
            self._measurement_service.roi_form = self._roi_form
            self._measurement_service.cursor_position = (self._cursor_x, self._cursor_y)
            self._measurement_service.current_slice_index = self._current_slice
    
    def _create_control_panel(self, layout):
        """Create the control panel with options."""
        control_layout = QHBoxLayout()
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(8)
        
        # Window size controls
        control_layout.addWidget(QLabel("Window:", self))
        
        self._window_size_spin = QSpinBox(self)
        self._window_size_spin.setRange(5, 100)
        self._window_size_spin.setValue(30)
        self._window_size_spin.valueChanged.connect(self._on_window_size_changed)
        control_layout.addWidget(self._window_size_spin)
        
        # HU toggle
        self._hu_checkbox = QCheckBox("Show HU", self)
        self._hu_checkbox.setChecked(False)
        self._hu_checkbox.stateChanged.connect(self._on_show_hu_changed)
        control_layout.addWidget(self._hu_checkbox)
        
        # Measurement mode controls
        control_layout.addWidget(QLabel("|", self))
        
        # Measurement mode toggle
        self._measurement_mode_checkbox = QCheckBox("Measurement", self)
        self._measurement_mode_checkbox.setChecked(False)
        self._measurement_mode_checkbox.stateChanged.connect(self._on_measurement_mode_changed)
        control_layout.addWidget(self._measurement_mode_checkbox)
        
        # Cursor size control
        control_layout.addWidget(QLabel("Size:", self))
        self._cursor_size_spin = QSpinBox(self)
        self._cursor_size_spin.setRange(1, 20)
        self._cursor_size_spin.setValue(3)
        self._cursor_size_spin.valueChanged.connect(self._on_cursor_size_changed)
        control_layout.addWidget(self._cursor_size_spin)
        
        # ROI form selector
        self._roi_form_combo = QComboBox(self)
        self._roi_form_combo.addItems(['square', 'circle', 'cross'])
        self._roi_form_combo.setCurrentText('square')
        self._roi_form_combo.currentTextChanged.connect(self._on_roi_form_changed)
        control_layout.addWidget(self._roi_form_combo)
        
        # Capture measurement button
        self._capture_button = QPushButton("Capture", self)
        self._capture_button.setEnabled(False)
        self._capture_button.clicked.connect(self._on_capture_clicked)
        control_layout.addWidget(self._capture_button)
        
        control_layout.addStretch(1)
        layout.addLayout(control_layout)
    
    def _on_series_changed(self):
        """Handle series changes."""
        self._update_info_label()
        self._update_table_data()
    
    def _on_slice_changed(self):
        """Handle slice changes."""
        self._update_info_label()
        self._update_table_data()
    
    def _update_info_label(self):
        """Update the info label with current series/slice info."""
        if not self.has_series:
            self._info_label.setText("No series loaded")
            return
            
        series = self.series
        current_slice = self.current_slice
        slice_obj = self.current_slice_object
        
        info_parts = []
        info_parts.append(f"Series: {series.series_description or series.series_uid}")
        info_parts.append(f"Slice: {current_slice + 1}/{series.num_slices}")
        
        if slice_obj and slice_obj.pixel_array is not None:
            info_parts.append(f"Size: {slice_obj.pixel_array.shape[1]}x{slice_obj.pixel_array.shape[0]}")
            info_parts.append(f"Z: {slice_obj.z_position:.2f}")
            
        self._info_label.setText(" | ".join(info_parts))
    
    def _update_table_data(self):
        """Update the table with current pixel data."""
        if not self.has_series:
            self._table.setRowCount(0)
            self._table.setColumnCount(0)
            return
            
        slice_obj = self.current_slice_object
        if not slice_obj or slice_obj.pixel_array is None:
            self._table.setRowCount(0)
            self._table.setColumnCount(0)
            return
            
        pixel_array = slice_obj.pixel_array
        
        # Get window dimensions
        rows = min(self._window_height, pixel_array.shape[0] - self._window_y)
        cols = min(self._window_width, pixel_array.shape[1] - self._window_x)
        
        # Ensure we don't go out of bounds
        if self._window_x + cols > pixel_array.shape[1]:
            self._window_x = max(0, pixel_array.shape[1] - cols)
        if self._window_y + rows > pixel_array.shape[0]:
            self._window_y = max(0, pixel_array.shape[0] - rows)
            
        # Update table dimensions
        self._table.setRowCount(rows)
        self._table.setColumnCount(cols)
        
        # Fill table with pixel data
        for row in range(rows):
            for col in range(cols):
                actual_row = self._window_y + row
                actual_col = self._window_x + col
                
                if actual_row < pixel_array.shape[0] and actual_col < pixel_array.shape[1]:
                    pixel_value = pixel_array[actual_row, actual_col]
                    
                    if self._show_hu:
                        hu_value = pixel_value * self._slope + self._intercept
                        text = f"{hu_value:.1f}"
                    else:
                        text = str(int(pixel_value))
                    
                    # Create or update item
                    if self._table.item(row, col) is None:
                        item = QTableWidgetItem(text)
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        self._table.setItem(row, col, item)
                    else:
                        item = self._table.item(row, col)
                        item.setText(text)
                    
                    # Clear highlighting if measurement mode is disabled
                    if not self._measurement_mode_enabled:
                        item.setBackground(QColor(43, 43, 43))  # Reset to table background
                        item.setForeground(QColor(224, 224, 224))  # Reset to normal text color
                    # Apply ROI highlighting if measurement mode is enabled
                    elif self._measurement_mode_enabled and self._highlight_roi:
                        self._apply_roi_highlighting(item, row, col)
        
        # Set header labels
        horizontal_labels = [str(self._window_x + col) for col in range(cols)]
        vertical_labels = [str(self._window_y + row) for row in range(rows)]
        
        self._table.setHorizontalHeaderLabels(horizontal_labels)
        self._table.setVerticalHeaderLabels(vertical_labels)
        
        # Resize columns to contents
        self._table.resizeColumnsToContents()
    
    def _apply_roi_highlighting(self, item: QTableWidgetItem, row: int, col: int):
        """Apply ROI highlighting to a table cell based on cursor position and form."""
        if not item:
            return
        
        if self._highlight_circle and self._circle_diameter > 0:
            # Circle mode: check if cell is within circle
            dx = col - self._circle_center_x
            dy = row - self._circle_center_y
            radius = self._circle_diameter / 2
            distance_squared = dx*dx + dy*dy
            
            if distance_squared <= radius*radius:
                # Cell is inside circle - highlight it
                if col == self._circle_center_x and row == self._circle_center_y:
                    # Center cell - bright green
                    item.setBackground(QColor(0, 200, 0))
                    item.setForeground(QColor(255, 255, 255))
                else:
                    # Regular circle cell - semi-transparent blue
                    item.setBackground(QColor(0, 100, 255, 128))
                    item.setForeground(QColor(255, 255, 255))
            else:
                # Cell is outside circle - normal appearance
                item.setBackground(QColor(43, 43, 43))  # Match table background
                item.setForeground(QColor(224, 224, 224))  # Normal text color
        else:
            # Rectangle mode: highlight all cells in the ROI region
            half_size = self._cursor_size // 2
            min_col = max(0, self._cursor_x - half_size)
            max_col = min(cols - 1, self._cursor_x + half_size)
            min_row = max(0, self._cursor_y - half_size)
            max_row = min(rows - 1, self._cursor_y + half_size)
            
            if (min_col <= col <= max_col and min_row <= row <= max_row):
                if col == self._cursor_x and row == self._cursor_y:
                    # Center cell - bright green
                    item.setBackground(QColor(0, 200, 0))
                    item.setForeground(QColor(255, 255, 255))
                else:
                    # Regular rectangle cell - semi-transparent blue
                    item.setBackground(QColor(0, 100, 255, 128))
                    item.setForeground(QColor(255, 255, 255))
            else:
                # Cell is outside rectangle - normal appearance
                item.setBackground(QColor(43, 43, 43))  # Match table background
                item.setForeground(QColor(224, 224, 224))  # Normal text color
    
    def _on_table_item_clicked(self, item: QTableWidgetItem):
        """Handle table item clicks."""
        if item is not None:
            row = item.row()
            col = item.column()
            actual_row = self._window_y + row
            actual_col = self._window_x + col
            self.pixel_selected.emit(actual_row, actual_col)
    
    def _on_window_size_changed(self, size: int):
        """Handle window size changes."""
        self._window_width = size
        self._window_height = size
        self._update_table_data()
        self.window_changed.emit(self._window_x, self._window_y, self._window_width, self._window_height)
    
    def _on_show_hu_changed(self, state: int):
        """Handle HU display toggle."""
        self._show_hu = state == Qt.Checked
        self._update_table_data()
    
    def set_window_position(self, x: int, y: int):
        """Set the window position in the pixel array."""
        self._window_x = x
        self._window_y = y
        self._update_table_data()
    
    def set_hu_parameters(self, slope: float, intercept: float):
        """Set HU conversion parameters."""
        self._slope = slope
        self._intercept = intercept
        if self._show_hu:
            self._update_table_data()
    
    def set_show_hu(self, show_hu: bool):
        """Set whether to show HU values."""
        self._show_hu = show_hu
        self._hu_checkbox.setChecked(show_hu)
        self._update_table_data()
    
    def set_window_size(self, width: int, height: int):
        """Set the window size."""
        self._window_width = width
        self._window_height = height
        self._window_size_spin.setValue(width)  # Assume square for now
        self._update_table_data()
        self.window_changed.emit(self._window_x, self._window_y, self._window_width, self._window_height)
    
    def get_current_window_data(self) -> Tuple[int, int, int, int, np.ndarray]:
        """
        Get the current window data as a 2D array.
        
        Returns:
            Tuple of (x, y, width, height, window_array)
        """
        if not self.has_series:
            return (0, 0, 0, 0, np.array([]))
            
        slice_obj = self.current_slice_object
        if not slice_obj or slice_obj.pixel_array is None:
            return (0, 0, 0, 0, np.array([]))
            
        pixel_array = slice_obj.pixel_array
        
        # Calculate actual window dimensions
        width = min(self._window_width, pixel_array.shape[1] - self._window_x)
        height = min(self._window_height, pixel_array.shape[0] - self._window_y)
        
        # Extract window region
        window_array = pixel_array[
            self._window_y:self._window_y + height,
            self._window_x:self._window_x + width
        ]
        
        return (self._window_x, self._window_y, width, height, window_array)
    
    def calculate_window_statistics(self) -> Dict[str, float]:
        """Calculate statistics for the current window region."""
        x, y, width, height, window_array = self.get_current_window_data()
        
        if window_array.size == 0:
            return {
                'mean': 0.0, 'std': 0.0, 'min': 0.0, 'max': 0.0,
                'hu_mean': 0.0, 'hu_std': 0.0, 'hu_min': 0.0, 'hu_max': 0.0,
                'pixel_count': 0
            }
        
        # Raw statistics
        raw_mean = float(np.mean(window_array))
        raw_std = float(np.std(window_array))
        raw_min = float(np.min(window_array))
        raw_max = float(np.max(window_array))
        
        # HU statistics
        hu_mean = raw_mean * self._slope + self._intercept
        hu_std = raw_std * self._slope  # std scales linearly
        hu_min = raw_min * self._slope + self._intercept
        hu_max = raw_max * self._slope + self._intercept
        
        return {
            'mean': raw_mean, 'std': raw_std, 'min': raw_min, 'max': raw_max,
            'hu_mean': hu_mean, 'hu_std': hu_std, 'hu_min': hu_min, 'hu_max': hu_max,
            'pixel_count': window_array.size
        }
    
    def next_slice(self):
        """Go to next slice and update display."""
        super().next_slice()
    
    def prev_slice(self):
        """Go to previous slice and update display."""
        super().prev_slice()
    
    def clear(self):
        """Clear the current series and table."""
        super().clear()
        self._table.setRowCount(0)
        self._table.setColumnCount(0)
        self._info_label.setText("No series loaded")
    
    def refresh(self):
        """Refresh the display."""
        self._update_info_label()
        self._update_table_data()
    
    # Measurement mode methods
    def _on_measurement_mode_changed(self, state: int):
        """Handle measurement mode toggle."""
        self._measurement_mode_enabled = state == Qt.Checked
        self._capture_button.setEnabled(self._measurement_mode_enabled and self.has_series)
        self._update_cursor_display()
        self._sync_measurement_mode_to_service()
    
    def _on_cursor_size_changed(self, size: int):
        """Handle cursor size changes."""
        self._cursor_size = size
        self._update_cursor_display()
        self.roi_parameters_changed.emit(size, self._roi_form)
        if self._measurement_service:
            self._measurement_service.cursor_size = size
    
    def _on_roi_form_changed(self, form: str):
        """Handle ROI form changes."""
        self._roi_form = form
        self._update_cursor_display()
        self.roi_parameters_changed.emit(self._cursor_size, form)
        if self._measurement_service:
            self._measurement_service.roi_form = form
    
    def _on_capture_clicked(self):
        """Handle capture button click."""
        self._capture_measurement()
    
    def _capture_measurement(self) -> bool:
        """Capture a measurement at the current cursor position."""
        if not self.has_series or not self._measurement_service:
            return False
        
        # Get current slice and position
        slice_obj = self.current_slice_object
        if not slice_obj or slice_obj.pixel_array is None:
            return False
        
        pixel_array = slice_obj.pixel_array
        
        # Calculate actual cursor position in pixel array coordinates
        actual_x = self._window_x + self._cursor_x
        actual_y = self._window_y + self._cursor_y
        
        # Check bounds
        if (0 <= actual_y < pixel_array.shape[0] and 
            0 <= actual_x < pixel_array.shape[1]):
            
            # Get slope and intercept for HU conversion
            slope = slice_obj.metadata.get('RescaleSlope', 1.0)
            intercept = slice_obj.metadata.get('RescaleIntercept', 0.0)
            
            # Use measurement service to create measurement
            measurement = self._measurement_service.create_roi_measurement(
                series=self.series,
                slice_index=self.current_slice,
                x=actual_x,
                y=actual_y,
                size=self._cursor_size,
                roi_form=self._roi_form,
                name=f"Measurement {self._measurement_service.measurement_collection.count + 1}",
                slope=slope,
                intercept=intercept
            )
            
            if measurement:
                self.measurement_captured.emit(measurement.measurement_id)
                return True
        
        return False
    
    def set_cursor_position(self, x: int, y: int):
        """Set the cursor position within the current window."""
        # Convert from absolute coordinates to window-relative coordinates
        relative_x = x - self._window_x
        relative_y = y - self._window_y
        
        # Clamp to window boundaries
        max_x = max(0, self._window_width - 1)
        max_y = max(0, self._window_height - 1)
        relative_x = max(0, min(relative_x, max_x))
        relative_y = max(0, min(relative_y, max_y))
        
        self._cursor_x = relative_x
        self._cursor_y = relative_y
        self._update_cursor_display()
        self.cursor_position_changed.emit(x, y)
        
        # Update absolute position in measurement service
        if self._measurement_service:
            self._measurement_service.cursor_position = (x, y)
            self._measurement_service.current_slice_index = self.current_slice
    
    def set_absolute_cursor_position(self, x: int, y: int):
        """Set the absolute cursor position in pixel array coordinates."""
        # Store absolute position
        abs_x, abs_y = x, y
        
        # Convert to window-relative coordinates
        relative_x = x - self._window_x
        relative_y = y - self._window_y
        
        # Clamp to window boundaries
        max_x = max(0, self._window_width - 1)
        max_y = max(0, self._window_height - 1)
        relative_x = max(0, min(relative_x, max_x))
        relative_y = max(0, min(relative_y, max_y))
        
        self._cursor_x = relative_x
        self._cursor_y = relative_y
        self._update_cursor_display()
        self.cursor_position_changed.emit(abs_x, abs_y)
        
        # Update position in measurement service
        if self._measurement_service:
            self._measurement_service.cursor_position = (abs_x, abs_y)
            self._measurement_service.current_slice_index = self.current_slice
    
    def _update_cursor_display(self):
        """Update the display to show cursor position and ROI."""
        if not self.has_series:
            return
        
        # Set up ROI highlighting based on cursor position and form
        if self._measurement_mode_enabled and self._highlight_roi:
            if self._roi_form == 'circle':
                self._highlight_circle = True
                self._circle_diameter = self._cursor_size
                self._circle_center_x = self._cursor_x
                self._circle_center_y = self._cursor_y
            else:
                self._highlight_circle = False
        else:
            self._highlight_circle = False
        
        # Trigger table refresh to show ROI highlighting
        self._update_table_data()
    
    def set_highlight_region(self, is_circle: bool, diameter: int = 0, 
                            center_x: int = 0, center_y: int = 0):
        """
        Set the highlighted region for ROI visualization.
        
        Args:
            is_circle: True for circle mode, False for rectangle (all cells)
            diameter: Diameter of circle in cells (for circle mode)
            center_x: Center X within window (0-indexed)
            center_y: Center Y within window (0-indexed)
        """
        self._highlight_circle = is_circle
        if is_circle:
            self._circle_diameter = diameter
            self._circle_center_x = center_x
            self._circle_center_y = center_y
        
        # Update display to show the highlighting
        self._update_table_data()
    
    def set_measurement_mode(self, enabled: bool):
        """Set whether measurement mode is enabled."""
        self._measurement_mode_enabled = enabled
        self._measurement_mode_checkbox.setChecked(enabled)
        self._capture_button.setEnabled(enabled and self.has_series)
        self._update_cursor_display()
        self._sync_measurement_mode_to_service()
    
    def get_measurement_mode_state(self) -> Dict[str, Any]:
        """Get the current measurement mode state."""
        return {
            'enabled': self._measurement_mode_enabled,
            'cursor_size': self._cursor_size,
            'roi_form': self._roi_form,
            'cursor_x': self._cursor_x,
            'cursor_y': self._cursor_y,
            'window_x': self._window_x,
            'window_y': self._window_y
        }
    
    def set_measurement_service(self, service: 'MeasurementService'):
        """Set the measurement service."""
        self._measurement_service = service
        if service:
            self._sync_with_measurement_service()
    
    def keyPressEvent(self, event):
        """Handle key press events for cursor navigation."""
        if self._measurement_mode_enabled and self.has_series:
            if event.key() == Qt.Key_Up:
                self.set_cursor_position(self._cursor_x, max(0, self._cursor_y - 1))
                event.accept()
                return
            elif event.key() == Qt.Key_Down:
                self.set_cursor_position(self._cursor_x, min(self._window_height - 1, self._cursor_y + 1))
                event.accept()
                return
            elif event.key() == Qt.Key_Left:
                self.set_cursor_position(max(0, self._cursor_x - 1), self._cursor_y)
                event.accept()
                return
            elif event.key() == Qt.Key_Right:
                self.set_cursor_position(min(self._window_width - 1, self._cursor_x + 1), self._cursor_y)
                event.accept()
                return
            elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                if self._measurement_mode_enabled:
                    self._capture_measurement()
                    event.accept()
                    return
        
        # Pass to parent for normal handling
        super().keyPressEvent(event)
    
    def wheelEvent(self, event):
        """Handle wheel events for cursor size adjustment."""
        if self._measurement_mode_enabled and event.modifiers() == Qt.ControlModifier:
            # Ctrl+Wheel: Change cursor size
            if event.angleDelta().y() > 0:
                self.cursor_size = min(self._cursor_size + 1, 20)
            else:
                self.cursor_size = max(self._cursor_size - 1, 1)
            event.accept()
        else:
            # Pass to parent for normal scrolling
            super().wheelEvent(event)