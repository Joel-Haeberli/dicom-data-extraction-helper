#!/usr/bin/env python3
"""
Series-Aware Curve View for DICOM Data Extraction Helper.

This refactored version inherits from SeriesViewerWidget to work with
ImageSeries objects instead of raw data arrays.

This provides HU profile visualization for DICOM series data.
"""

from typing import Optional, List, Tuple, TYPE_CHECKING
import numpy as np

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QDoubleSpinBox, QSizePolicy, QSpinBox, QPushButton, QFileDialog, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QDateTime
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis, QSplineSeries
from PySide6.QtGui import QImage, QPainter, QColor

if TYPE_CHECKING:
    from models.image_series import ImageSeries, ImageSlice

from .base import SeriesViewerWidget


class SeriesCurveView(SeriesViewerWidget):
    """
    Series-aware widget for displaying a curve of pixel HU values from an ImageSeries.
    
    This widget inherits from SeriesViewerWidget to provide series navigation functionality
    and displays HU profiles from the current slice.
    
    Features:
    - Line chart showing HU values vs X position for a selected row
    - Manual axis range controls
    - Automatic axis scaling based on data
    - Row selection for HU profile
    - Series navigation (inherited from SeriesViewerWidget)
    - Dark mode styling
    
    Signals:
    - Inherits signals from SeriesViewerWidget
    - row_changed: Emitted when the selected row changes
    """
    
    # Signal emitted when the selected row changes
    row_changed = Signal(int)
    
    def __init__(self, parent=None):
        """Initialize the series curve viewer."""
        # Call parent with call_setup_widget=False to avoid double setup
        super().__init__(parent, call_setup_widget=False)
        
        # Data
        self._x_values: List[float] = []
        self._y_values: List[float] = []
        
        # Manual range settings
        self._manual_x_min: Optional[float] = None
        self._manual_x_max: Optional[float] = None
        self._manual_y_min: Optional[float] = None
        self._manual_y_max: Optional[float] = None
        self._manual_ranges_set: bool = False  # True if user has manually set any axis range
        
        # Row selection
        self._current_row: int = 0
        self._row_spin: Optional[QSpinBox] = None
        
        # Chart components
        self._chart: Optional[QChart] = None
        self._series: Optional[QSplineSeries] = None
        self._regression_series: Optional[QLineSeries] = None
        self._chart_view: Optional[QChartView] = None
        
        # Axis components
        self._axis_x: Optional[QValueAxis] = None
        self._axis_y: Optional[QValueAxis] = None
        
        # Regression UI
        self._regression_checkbox: Optional[QCheckBox] = None
        self._regression_label: Optional[QLabel] = None
        self._show_regression: bool = True
        
        # Axis range inputs
        self._x_min_input: Optional[QDoubleSpinBox] = None
        self._x_max_input: Optional[QDoubleSpinBox] = None
        self._y_min_input: Optional[QDoubleSpinBox] = None
        self._y_max_input: Optional[QDoubleSpinBox] = None
        
        # Export button
        self._export_button: Optional[QPushButton] = None
        
        # HU conversion parameters
        self._slope: float = 1.0
        self._intercept: float = 0.0
        
        # Setup UI
        self._setup_widget()
        self._setup_connections()
        
        # Dark mode styling
        self._apply_dark_mode()
    
    def _setup_widget(self):
        """Setup the widget layout with chart and axis controls."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)
        
        # Create chart view
        self._chart = QChart()
        self._chart.setTitle("HU Profile (No series)")
        self._chart.legend().hide()
        self._chart.setAnimationOptions(QChart.SeriesAnimations)
        
        # Use spline series for smooth curve
        self._series = QSplineSeries()
        self._series.setName("HU Values")
        self._series.setColor(Qt.cyan)  # Cyan for dark mode visibility
        self._chart.addSeries(self._series)
        
        # Linear regression overlay
        self._regression_series = QLineSeries()
        self._regression_series.setName("Linear Regression")
        pen = self._regression_series.pen()
        pen.setColor(QColor(255, 165, 0))  # orange
        pen.setWidth(2)
        self._regression_series.setPen(pen)
        self._chart.addSeries(self._regression_series)
        
        # Create axes
        self._axis_x = QValueAxis()
        self._axis_x.setTitleText("X Position (pixel)")
        self._axis_x.setLabelFormat("%.1f")
        self._axis_x.setTickCount(10)
        
        self._axis_y = QValueAxis()
        self._axis_y.setTitleText("HU Value")
        self._axis_y.setLabelFormat("%.1f")
        self._axis_y.setTickCount(10)
        
        self._chart.addAxis(self._axis_x, Qt.AlignBottom)
        self._chart.addAxis(self._axis_y, Qt.AlignLeft)
        
        self._series.attachAxis(self._axis_x)
        self._series.attachAxis(self._axis_y)
        self._regression_series.attachAxis(self._axis_x)
        self._regression_series.attachAxis(self._axis_y)
        
        self._chart_view = QChartView(self._chart)
        self._chart_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        main_layout.addWidget(self._chart_view, 1)
        
        # Axis range controls
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(4)
        
        # Row selector
        controls_layout.addWidget(QLabel("Row:"))
        self._row_spin = QSpinBox()
        self._row_spin.setRange(0, 10000)
        self._row_spin.setValue(0)
        self._row_spin.setToolTip("Select which row of the current slice to display in the HU profile")
        controls_layout.addWidget(self._row_spin)
        
        controls_layout.addWidget(QLabel("X Min:"))
        self._x_min_input = QDoubleSpinBox()
        self._x_min_input.setRange(-100000, 100000)
        self._x_min_input.setDecimals(2)
        controls_layout.addWidget(self._x_min_input)
        
        controls_layout.addWidget(QLabel("X Max:"))
        self._x_max_input = QDoubleSpinBox()
        self._x_max_input.setRange(-100000, 100000)
        self._x_max_input.setDecimals(2)
        controls_layout.addWidget(self._x_max_input)
        
        controls_layout.addWidget(QLabel("Y Min:"))
        self._y_min_input = QDoubleSpinBox()
        self._y_min_input.setRange(-100000, 100000)
        self._y_min_input.setDecimals(2)
        controls_layout.addWidget(self._y_min_input)
        
        controls_layout.addWidget(QLabel("Y Max:"))
        self._y_max_input = QDoubleSpinBox()
        self._y_max_input.setRange(-100000, 100000)
        self._y_max_input.setDecimals(2)
        controls_layout.addWidget(self._y_max_input)
        
        # Linear regression toggle + equation label
        self._regression_checkbox = QCheckBox("Lin. Reg.")
        self._regression_checkbox.setChecked(True)
        self._regression_checkbox.setToolTip("Show/hide linear regression line")
        controls_layout.addWidget(self._regression_checkbox)
        
        self._regression_label = QLabel("")
        self._regression_label.setStyleSheet("color: rgb(255,165,0); font-size: 10px;")
        self._regression_label.setToolTip("Linear regression: slope, intercept, R²")
        controls_layout.addWidget(self._regression_label)
        
        # Export button
        self._export_button = QPushButton("Export PNG")
        self._export_button.setToolTip("Export the curve as PNG image")
        controls_layout.addWidget(self._export_button)
        
        main_layout.addLayout(controls_layout, 0)
    
    def _setup_connections(self):
        """Setup signal connections."""
        # Series viewer connections
        self.series_changed.connect(self._on_series_changed)
        self.slice_changed.connect(self._on_slice_changed)
        
        # Row and axis connections
        if self._row_spin:
            self._row_spin.valueChanged.connect(self._on_row_changed)
        if self._x_min_input:
            self._x_min_input.valueChanged.connect(self._on_axis_range_changed)
        if self._x_max_input:
            self._x_max_input.valueChanged.connect(self._on_axis_range_changed)
        if self._y_min_input:
            self._y_min_input.valueChanged.connect(self._on_axis_range_changed)
        if self._y_max_input:
            self._y_max_input.valueChanged.connect(self._on_axis_range_changed)
        if self._export_button:
            self._export_button.clicked.connect(self._on_export_png)
        if self._regression_checkbox:
            self._regression_checkbox.toggled.connect(self._on_regression_toggled)
    
    def _on_series_changed(self):
        """Handle series changes - update the display."""
        self._update_from_series()
    
    def _on_slice_changed(self):
        """Handle slice changes - update the display."""
        self._update_from_series()
    
    def _update_from_series(self):
        """Update the curve data from the current series and slice."""
        if not self.has_series:
            self.clear()
            return
        
        slice_obj = self.current_slice_object
        if slice_obj is None or slice_obj.pixel_array is None:
            self.clear()
            return
        
        pixel_array = slice_obj.pixel_array
        
        # Get HU conversion parameters from slice metadata
        self._slope, self._intercept = self._get_hu_parameters(slice_obj)
        
        # Update row range based on slice dimensions
        if self._row_spin:
            self._row_spin.setRange(0, max(0, pixel_array.shape[0] - 1))
        
        # If we have data in the window, use it
        if self._current_row < pixel_array.shape[0]:
            self._update_row_data(self._current_row)
        else:
            # Reset to first row if current row is out of bounds
            self._current_row = 0
            if self._row_spin:
                self._row_spin.setValue(0)
            self._update_row_data(0)
    
    def _get_hu_parameters(self, slice_obj: 'ImageSlice') -> Tuple[float, float]:
        """Extract HU conversion parameters from slice metadata."""
        try:
            metadata = slice_obj.metadata
            slope = float(metadata.get('RescaleSlope', 1.0))
            intercept = float(metadata.get('RescaleIntercept', 0.0))
            return slope, intercept
        except (ValueError, TypeError):
            return 1.0, 0.0
    
    def _update_row_data(self, row: int):
        """Update the curve data for a specific row."""
        if not self.has_series:
            self.clear()
            return
        
        slice_obj = self.current_slice_object
        if slice_obj is None or slice_obj.pixel_array is None:
            self.clear()
            return
        
        pixel_array = slice_obj.pixel_array
        
        # Check if row is valid
        if row < 0 or row >= pixel_array.shape[0]:
            self.clear()
            return
        
        # Extract row data
        row_data = pixel_array[row, :]
        
        # Convert to HU values
        slope, intercept = self._slope, self._intercept
        x_values = list(range(len(row_data)))
        y_values = [float(val * slope + intercept) for val in row_data]
        
        # Set the data
        self.set_data(x_values, y_values)
        
        # Update chart title with absolute row and slice info
        if self._chart:
            series = self.series
            if series:
                self._chart.setTitle(
                    f"HU Profile (Row: {row}, Slice: {self.current_slice + 1}/{series.num_slices})"
                )
            else:
                self._chart.setTitle(f"HU Profile (Row: {row})")
    
    def _on_row_changed(self, value: int):
        """Handler for row selector changes."""
        self._current_row = value
        self.row_changed.emit(value)
        self._update_row_data(value)
    
    def _on_axis_range_changed(self, value):
        """Handler for axis range input changes."""
        self._manual_ranges_set = True
        self._manual_x_min = self._x_min_input.value() if self._x_min_input else None
        self._manual_x_max = self._x_max_input.value() if self._x_max_input else None
        self._manual_y_min = self._y_min_input.value() if self._y_min_input else None
        self._manual_y_max = self._y_max_input.value() if self._y_max_input else None
        self._update_axes()
    
    def _apply_dark_mode(self):
        """Apply dark mode styling to the chart."""
        if self._chart:
            self._chart.setBackgroundBrush(Qt.black)
            self._chart.setPlotAreaBackgroundBrush(Qt.black)
            self._chart.setPlotAreaBackgroundVisible(True)
            
        # Style axes for dark mode
        for axis in [self._axis_x, self._axis_y]:
            if axis:
                axis.setLabelsColor(Qt.white)
                axis.setTitleBrush(Qt.white)
                axis.setGridLineColor(Qt.darkGray)
                axis.setLinePenColor(Qt.white)
        
        # Style series
        if self._series:
            self._series.setColor(Qt.cyan)
        
        # Style inputs
        for spin in [self._x_min_input, self._x_max_input, self._y_min_input, self._y_max_input, self._row_spin]:
            if spin:
                spin.setStyleSheet("""
                    QSpinBox, QDoubleSpinBox {
                        background-color: #2b2b2b;
                        color: #e0e0e0;
                        border: 1px solid #444;
                        padding: 2px;
                    }
                    QSpinBox::up-button, QSpinBox::down-button,
                    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                        background-color: #3c3c3c;
                    }
                """)
    
    def set_row_range(self, min_row: int, max_row: int):
        """Set the valid range for the row selector.
        
        Args:
            min_row: Minimum row value (typically 0)
            max_row: Maximum row value (window height - 1)
        """
        if self._row_spin:
            self._row_spin.setRange(min_row, max_row)
    
    def set_row(self, row: int, absolute_row: int = None):
        """Set the row number displayed in the chart title.
        
        Args:
            row: The relative row index within the window (0 = first row)
            absolute_row: The absolute y-coordinate in the image. If None, uses row.
        """
        self._current_row = row
        if self._row_spin:
            # Use blockSignals to prevent feedback loop
            self._row_spin.blockSignals(True)
            self._row_spin.setValue(row)
            self._row_spin.blockSignals(False)
        if self._chart:
            # Display absolute row if provided, otherwise use relative row
            display_row = absolute_row if absolute_row is not None else row
            if self.has_series:
                series = self.series
                if series:
                    self._chart.setTitle(
                        f"HU Profile (Row: {display_row}, Slice: {self.current_slice + 1}/{series.num_slices})"
                    )
                else:
                    self._chart.setTitle(f"HU Profile (Row: {display_row})")
            else:
                self._chart.setTitle(f"HU Profile (Row: {display_row})")
    
    def set_data(self, x_values: List[float], y_values: List[float]):
        """
        Set the data for the curve.
        
        Args:
            x_values: List of X coordinates (pixel positions)
            y_values: List of Y values (HU values)
        """
        if not x_values or not y_values or len(x_values) != len(y_values):
            self.clear()
            return
        
        self._x_values = list(x_values)
        self._y_values = list(y_values)
        
        # Update series data
        if self._series:
            self._series.clear()
            for x, y in zip(self._x_values, self._y_values):
                self._series.append(x, y)
        
        # Always update input fields to show current data ranges (with Y padding)
        # This allows user to see actual data ranges even in manual mode
        x_min = min(self._x_values) if self._x_values else 0
        x_max = max(self._x_values) if self._x_values else 1
        
        # Y axis: use min-20 and max+20 for perfect alignment
        y_min = min(self._y_values) if self._y_values else 0
        y_max = max(self._y_values) if self._y_values else 1
        y_min -= 20
        y_max += 20
        
        # Update inputs to show current data ranges without triggering manual-mode lock
        for spin, val in (
            (self._x_min_input, x_min), (self._x_max_input, x_max),
            (self._y_min_input, y_min), (self._y_max_input, y_max),
        ):
            if spin:
                spin.blockSignals(True)
                spin.setValue(val)
                spin.blockSignals(False)
        
        self._update_regression()
        self._update_axes()
    
    def _update_regression(self):
        """Recompute and redraw the linear regression line from current data."""
        if self._regression_series is None:
            return
        self._regression_series.clear()
        if self._regression_label:
            self._regression_label.setText("")
        
        if len(self._x_values) < 2:
            return
        
        x = np.array(self._x_values)
        y = np.array(self._y_values)
        slope, intercept = np.polyfit(x, y, 1)
        
        # R²
        y_pred = slope * x + intercept
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - y.mean()) ** 2)
        r2 = 1.0 - ss_res / ss_tot if ss_tot != 0 else 1.0
        
        x_min, x_max = x.min(), x.max()
        self._regression_series.append(x_min, slope * x_min + intercept)
        self._regression_series.append(x_max, slope * x_max + intercept)
        
        if self._regression_label:
            self._regression_label.setText(
                f"y = {slope:.3f}x + {intercept:.1f}   R²={r2:.4f}"
            )
        
        self._regression_series.setVisible(self._show_regression)
    
    def _on_regression_toggled(self, checked: bool):
        """Show or hide the regression line."""
        self._show_regression = checked
        if self._regression_series:
            self._regression_series.setVisible(checked)
        if self._regression_label:
            self._regression_label.setVisible(checked)
    
    def _update_axes(self):
        """Update axis ranges based on manual or automatic mode."""
        if not self._axis_x or not self._axis_y:
            return
        
        # Determine ranges
        if self._manual_ranges_set:
            # Use manual ranges from inputs
            x_min = self._manual_x_min if self._manual_x_min is not None else (min(self._x_values) if self._x_values else 0)
            x_max = self._manual_x_max if self._manual_x_max is not None else (max(self._x_values) if self._x_values else 1)
            y_min = self._manual_y_min if self._manual_y_min is not None else (min(self._y_values) if self._y_values else 0)
            y_max = self._manual_y_max if self._manual_y_max is not None else (max(self._y_values) if self._y_values else 1)
        else:
            # Auto mode: use data min/max
            x_min = min(self._x_values) if self._x_values else 0
            x_max = max(self._x_values) if self._x_values else 1
            y_min = min(self._y_values) if self._y_values else 0
            y_max = max(self._y_values) if self._y_values else 1
            # Apply fixed padding: Y gets ±20, X gets no padding
            y_min -= 20
            y_max += 20
        
        # Set axis ranges
        self._axis_x.setRange(x_min, x_max)
        self._axis_y.setRange(y_min, y_max)
    
    def clear(self):
        """Clear the curve data."""
        super().clear()  # Clear series viewer state
        
        if self._series:
            self._series.clear()
        if self._regression_series:
            self._regression_series.clear()
        if self._regression_label:
            self._regression_label.setText("")
        self._x_values = []
        self._y_values = []
        
        # Reset axes
        if self._axis_x:
            self._axis_x.setRange(0, 1)
        if self._axis_y:
            self._axis_y.setRange(0, 1)
        
        # Reset row in title but keep spinbox value
        if self._chart:
            self._chart.setTitle("HU Profile (No data)")
        self._current_row = 0
    
    def _on_export_png(self):
        """Export the current curve as PNG image."""
        if not self._chart or not self._chart_view:
            return
        
        # Get save file path
        timestamp = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
        default_filename = f"curve_{timestamp}.png"
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Curve as PNG",
            default_filename,
            "PNG Files (*.png);;All Files (*)"
        )
        
        if not filepath:
            return
        
        # Render chart to image
        image = QImage(self._chart_view.size(), QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        
        painter = QPainter(image)
        self._chart_view.render(painter)
        painter.end()
        
        # Save image
        if image.save(filepath, "PNG"):
            print(f"Curve exported to {filepath}")
        else:
            print(f"Failed to export curve to {filepath}")
    
    def set_hu_parameters(self, slope: float, intercept: float):
        """Set HU conversion parameters."""
        self._slope = slope
        self._intercept = intercept
        if self.has_series:
            # Refresh data with new HU parameters
            self._update_from_series()
    
    def refresh(self):
        """Refresh the curve display."""
        super().refresh()
        self._update_from_series()
    
    # Override next/prev slice to also update the curve
    def next_slice(self):
        """Go to next slice and update curve."""
        super().next_slice()
        self._update_from_series()
    
    def prev_slice(self):
        """Go to previous slice and update curve."""
        super().prev_slice()
        self._update_from_series()


# For backward compatibility, create an alias
CurveView = SeriesCurveView

# Keep the original class available for backward compatibility
__all__ = ['SeriesCurveView', 'CurveView']