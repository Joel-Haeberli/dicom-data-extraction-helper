#!/usr/bin/env python3
"""
Series-Aware Curve View for DICOM Data Extraction Helper.

This refactored version inherits from SeriesViewerWidget to work with
ImageSeries objects instead of raw data arrays.

This provides HU profile visualization for DICOM series data.
"""

from typing import Optional, List, Tuple, Dict, Any, TYPE_CHECKING
import numpy as np

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QDoubleSpinBox, QSizePolicy, QSpinBox, QPushButton, QFileDialog, QCheckBox,
    QGroupBox, QComboBox
)
from PySide6.QtCore import Qt, Signal, QDateTime, QPointF
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis, QSplineSeries, QScatterSeries
from PySide6.QtGui import QImage, QPainter, QColor, QPen

if TYPE_CHECKING:
    from models.image_series import ImageSeries, ImageSlice
    from services.measurement_service import MeasurementService
    from models.measurement import Measurement

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
    
    # Additional signals for profile measurements
    profile_measurement_captured = Signal(str)  # measurement_id
    measurement_selected = Signal(str)  # measurement_id
    profile_points_changed = Signal(int, int, int, int)  # x1, y1, x2, y2
    
    def __init__(self, parent=None, measurement_service: Optional['MeasurementService'] = None):
        """Initialize the series curve viewer."""
        # Call parent with call_setup_widget=False to avoid double setup
        super().__init__(parent, call_setup_widget=False)
        
        # Measurement service integration
        self._measurement_service = measurement_service
        
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
        self._chart_series: Optional[QSplineSeries] = None
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
        
        # Profile measurement state
        self._profile_mode_enabled: bool = False
        self._profile_start_x: int = 0
        self._profile_start_y: int = 0
        self._profile_end_x: int = 0
        self._profile_end_y: int = 0
        self._profile_width: int = 1  # Width of profile line in pixels
        self._showing_measurement_profile: bool = False
        self._current_measurement_id: Optional[str] = None
        
        # Measurement service integration
        self._measurement_service: Optional['MeasurementService'] = measurement_service
        
        # Profile type: 'row' (existing), 'horizontal', 'vertical', 'diagonal', 'custom'
        self._profile_type: str = 'row'
        
        # Additional chart series for measurements
        self._measurement_series: Dict[str, QSplineSeries] = {}
        self._current_profile_series: Optional[QSplineSeries] = None
        
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
        self._chart_series = QSplineSeries()
        self._chart_series.setName("HU Values")
        self._chart_series.setColor(Qt.cyan)  # Cyan for dark mode visibility
        self._chart.addSeries(self._chart_series)
        
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
        
        self._chart_series.attachAxis(self._axis_x)
        self._chart_series.attachAxis(self._axis_y)
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
        
        # Profile measurement controls
        self._create_profile_measurement_controls(main_layout)
    
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
    
    def _create_profile_measurement_controls(self, layout):
        """Create profile measurement controls."""
        # Profile measurement controls group
        profile_group = QGroupBox("Profile Measurement", self)
        profile_layout = QHBoxLayout(profile_group)
        profile_layout.setContentsMargins(4, 4, 4, 4)
        profile_layout.setSpacing(8)
        
        # Profile mode toggle
        self._profile_mode_checkbox = QCheckBox("Profile Mode", self)
        self._profile_mode_checkbox.setChecked(False)
        self._profile_mode_checkbox.setToolTip("Enable profile measurement mode")
        self._profile_mode_checkbox.stateChanged.connect(self._on_profile_mode_changed)
        profile_layout.addWidget(self._profile_mode_checkbox)
        
        # Profile type selector
        profile_layout.addWidget(QLabel("Type:", self))
        self._profile_type_combo = QComboBox(self)
        self._profile_type_combo.addItems(['row', 'horizontal', 'vertical', 'diagonal', 'custom'])
        self._profile_type_combo.setCurrentText('row')
        self._profile_type_combo.setToolTip("Type of profile to measure")
        self._profile_type_combo.currentTextChanged.connect(self._on_profile_type_changed)
        profile_layout.addWidget(self._profile_type_combo)
        
        # Profile width control
        profile_layout.addWidget(QLabel("Width:", self))
        self._profile_width_spin = QSpinBox(self)
        self._profile_width_spin.setRange(1, 10)
        self._profile_width_spin.setValue(1)
        self._profile_width_spin.setToolTip("Width of profile line in pixels")
        self._profile_width_spin.valueChanged.connect(self._on_profile_width_changed)
        profile_layout.addWidget(self._profile_width_spin)
        
        # Profile start and end position controls
        profile_layout.addWidget(QLabel("Start:", self))
        self._profile_start_spin = QSpinBox(self)
        self._profile_start_spin.setRange(0, 10000)
        self._profile_start_spin.setValue(0)
        self._profile_start_spin.setToolTip("Start position for profile")
        self._profile_start_spin.valueChanged.connect(self._on_profile_start_changed)
        profile_layout.addWidget(self._profile_start_spin)
        
        profile_layout.addWidget(QLabel("End:", self))
        self._profile_end_spin = QSpinBox(self)
        self._profile_end_spin.setRange(0, 10000)
        self._profile_end_spin.setValue(100)
        self._profile_end_spin.setToolTip("End position for profile")
        self._profile_end_spin.valueChanged.connect(self._on_profile_end_changed)
        profile_layout.addWidget(self._profile_end_spin)
        
        # Capture profile button
        self._capture_profile_button = QPushButton("Capture Profile", self)
        self._capture_profile_button.setEnabled(False)
        self._capture_profile_button.setToolTip("Capture current profile as measurement")
        self._capture_profile_button.clicked.connect(self._on_capture_profile_clicked)
        profile_layout.addWidget(self._capture_profile_button)
        
        # Measurement selection for display
        profile_layout.addWidget(QLabel("Measurement:", self))
        self._measurement_combo = QComboBox(self)
        self._measurement_combo.addItem("Current Profile", "")
        self._measurement_combo.setToolTip("Select measurement to display")
        self._measurement_combo.currentTextChanged.connect(self._on_measurement_selected)
        profile_layout.addWidget(self._measurement_combo)
        
        layout.addWidget(profile_group)
    
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
        if self._chart_series:
            self._chart_series.setColor(Qt.cyan)
        
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
        if self._chart_series:
            self._chart_series.clear()
            for x, y in zip(self._x_values, self._y_values):
                self._chart_series.append(x, y)
        
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
        
        if self._chart_series:
            self._chart_series.clear()
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
    
    # Profile measurement methods
    def _on_profile_mode_changed(self, state: int):
        """Handle profile mode toggle."""
        self._profile_mode_enabled = state == Qt.Checked
        self._capture_profile_button.setEnabled(self._profile_mode_enabled and self.has_series)
        if self._profile_mode_enabled:
            self._enter_profile_mode()
        else:
            self._exit_profile_mode()
    
    def _on_profile_type_changed(self, profile_type: str):
        """Handle profile type changes."""
        self._profile_type = profile_type
        if self._profile_mode_enabled:
            self._update_profile_display()
    
    def _on_profile_width_changed(self, width: int):
        """Handle profile width changes."""
        self._profile_width = width
        if self._profile_mode_enabled:
            self._update_profile_display()
    
    def _on_profile_start_changed(self, start: int):
        """Handle profile start position changes."""
        self._profile_start_x = start
        if self._profile_type in ['horizontal', 'custom']:
            self._profile_start_y = self._current_row
        elif self._profile_type == 'vertical':
            self._profile_start_y = start
        if self._profile_mode_enabled:
            self._update_profile_display()
        self.profile_points_changed.emit(self._profile_start_x, self._profile_start_y, 
                                         self._profile_end_x, self._profile_end_y)
    
    def _on_profile_end_changed(self, end: int):
        """Handle profile end position changes."""
        self._profile_end_x = end
        if self._profile_type in ['horizontal', 'custom']:
            self._profile_end_y = self._current_row
        elif self._profile_type == 'vertical':
            self._profile_end_y = end
        if self._profile_mode_enabled:
            self._update_profile_display()
        self.profile_points_changed.emit(self._profile_start_x, self._profile_start_y, 
                                         self._profile_end_x, self._profile_end_y)
    
    def _on_capture_profile_clicked(self):
        """Handle capture profile button click."""
        self._capture_profile_measurement()
    
    def _on_measurement_selected(self, text: str):
        """Handle measurement selection from combo box."""
        if text == "Current Profile":
            self._current_measurement_id = None
            self._show_current_profile()
        else:
            # Extract measurement ID from text (format: "measurement_name (id)")
            measurement_id = text.split('(')[-1].rstrip(')')
            self._current_measurement_id = measurement_id
            self._show_measurement_profile(measurement_id)
    
    def _enter_profile_mode(self):
        """Enter profile measurement mode."""
        if not self.has_series:
            return
        
        # Initialize profile points based on current row
        if self._profile_type == 'row':
            self._profile_start_x = 0
            self._profile_start_y = self._current_row
            self._profile_end_x = self._get_slice_width() - 1
            self._profile_end_y = self._current_row
        elif self._profile_type == 'horizontal':
            self._profile_start_y = self._current_row
            self._profile_end_y = self._current_row
        elif self._profile_type == 'vertical':
            self._profile_start_x = self._current_row
            self._profile_end_x = self._current_row
        
        # Update controls
        if self._profile_type in ['row', 'horizontal']:
            self._profile_start_spin.setRange(0, self._get_slice_width() - 1)
            self._profile_end_spin.setRange(0, self._get_slice_width() - 1)
            self._profile_start_spin.setValue(self._profile_start_x)
            self._profile_end_spin.setValue(self._profile_end_x)
        elif self._profile_type == 'vertical':
            self._profile_start_spin.setRange(0, self._get_slice_height() - 1)
            self._profile_end_spin.setRange(0, self._get_slice_height() - 1)
            self._profile_start_spin.setValue(self._profile_start_y)
            self._profile_end_spin.setValue(self._profile_end_y)
        
        # Update display
        self._update_profile_display()
        
        # Update measurement combo
        self._update_measurement_combo()
    
    def _exit_profile_mode(self):
        """Exit profile measurement mode."""
        # Clear profile display
        if self._current_profile_series:
            self._chart.removeSeries(self._current_profile_series)
            self._current_profile_series = None
        
        # Clear measurement series
        self._clear_measurement_series()
        
        # Reset to normal row display
        if self.has_series:
            self._update_row_data(self._current_row)
    
    def _get_slice_width(self) -> int:
        """Get the width of the current slice."""
        if self.has_series:
            slice_obj = self.current_slice_object
            if slice_obj and slice_obj.pixel_array is not None:
                return slice_obj.pixel_array.shape[1]
        return 512  # Default
    
    def _get_slice_height(self) -> int:
        """Get the height of the current slice."""
        if self.has_series:
            slice_obj = self.current_slice_object
            if slice_obj and slice_obj.pixel_array is not None:
                return slice_obj.pixel_array.shape[0]
        return 512  # Default
    
    def _update_profile_display(self):
        """Update the profile display based on current settings."""
        if not self.has_series or not self._profile_mode_enabled:
            return
        
        slice_obj = self.current_slice_object
        if slice_obj is None or slice_obj.pixel_array is None:
            return
        
        pixel_array = slice_obj.pixel_array
        
        # Extract profile data based on type
        if self._profile_type == 'row':
            x_values, y_values = self._extract_row_profile(pixel_array)
        elif self._profile_type == 'horizontal':
            x_values, y_values = self._extract_horizontal_profile(pixel_array)
        elif self._profile_type == 'vertical':
            x_values, y_values = self._extract_vertical_profile(pixel_array)
        elif self._profile_type == 'diagonal':
            x_values, y_values = self._extract_diagonal_profile(pixel_array)
        else:  # custom
            x_values, y_values = self._extract_custom_profile(pixel_array)
        
        # Update current profile series or create if needed
        if self._current_profile_series is None:
            self._current_profile_series = QSplineSeries()
            self._current_profile_series.setName("Current Profile")
            self._current_profile_series.setColor(Qt.green)
            pen = self._current_profile_series.pen()
            pen.setWidth(2)
            self._current_profile_series.setPen(pen)
            self._chart.addSeries(self._current_profile_series)
            self._current_profile_series.attachAxis(self._axis_x)
            self._current_profile_series.attachAxis(self._axis_y)
        
        # Clear and populate series
        self._current_profile_series.clear()
        for x, y in zip(x_values, y_values):
            self._current_profile_series.append(x, y)
        
        # Update chart title
        if self._chart:
            self._chart.setTitle(f"Profile Measurement: {self._profile_type}")
        
        # Update axes
        self._update_axes()
    
    def _extract_row_profile(self, pixel_array: np.ndarray) -> Tuple[List[float], List[float]]:
        """Extract profile data for a row."""
        row = self._current_row
        if row < 0 or row >= pixel_array.shape[0]:
            return [], []
        
        start_col = self._profile_start_x
        end_col = self._profile_end_x
        
        # Clamp to array bounds
        start_col = max(0, min(start_col, pixel_array.shape[1] - 1))
        end_col = max(0, min(end_col, pixel_array.shape[1] - 1))
        
        # Ensure start <= end
        if start_col > end_col:
            start_col, end_col = end_col, start_col
        
        # Extract row data
        row_data = pixel_array[row, start_col:end_col + 1]
        
        # Convert to HU values
        x_values = list(range(start_col, end_col + 1))
        y_values = [float(val * self._slope + self._intercept) for val in row_data]
        
        return x_values, y_values
    
    def _extract_horizontal_profile(self, pixel_array: np.ndarray) -> Tuple[List[float], List[float]]:
        """Extract horizontal profile at current row."""
        # Same as row profile for now
        return self._extract_row_profile(pixel_array)
    
    def _extract_vertical_profile(self, pixel_array: np.ndarray) -> Tuple[List[float], List[float]]:
        """Extract vertical profile."""
        col = self._profile_start_x
        start_row = self._profile_start_y
        end_row = self._profile_end_y
        
        if col < 0 or col >= pixel_array.shape[1]:
            return [], []
        
        # Clamp to array bounds
        start_row = max(0, min(start_row, pixel_array.shape[0] - 1))
        end_row = max(0, min(end_row, pixel_array.shape[0] - 1))
        
        # Ensure start <= end
        if start_row > end_row:
            start_row, end_row = end_row, start_row
        
        # Extract column data
        col_data = pixel_array[start_row:end_row + 1, col]
        
        # Convert to HU values
        y_values = [float(val * self._slope + self._intercept) for val in col_data]
        x_values = list(range(start_row, end_row + 1))
        
        return x_values, y_values
    
    def _extract_diagonal_profile(self, pixel_array: np.ndarray) -> Tuple[List[float], List[float]]:
        """Extract diagonal profile using Bresenham's line algorithm."""
        start_x, start_y = 0, 0
        end_x, end_y = min(pixel_array.shape[1] - 1, pixel_array.shape[0] - 1), \
                      min(pixel_array.shape[1] - 1, pixel_array.shape[0] - 1)
        
        # Use Bresenham's algorithm to get points along diagonal
        points = self._get_line_points(start_x, start_y, end_x, end_y)
        
        x_values = []
        y_values = []
        
        for x, y in points:
            if 0 <= y < pixel_array.shape[0] and 0 <= x < pixel_array.shape[1]:
                pixel_value = pixel_array[y, x]
                hu_value = float(pixel_value * self._slope + self._intercept)
                x_values.append(x)
                y_values.append(hu_value)
        
        return x_values, y_values
    
    def _extract_custom_profile(self, pixel_array: np.ndarray) -> Tuple[List[float], List[float]]:
        """Extract custom profile between start and end points."""
        # Use Bresenham's algorithm to get points along the line
        points = self._get_line_points(
            self._profile_start_x, self._profile_start_y,
            self._profile_end_x, self._profile_end_y
        )
        
        x_values = []
        y_values = []
        
        for x, y in points:
            if 0 <= y < pixel_array.shape[0] and 0 <= x < pixel_array.shape[1]:
                pixel_value = pixel_array[y, x]
                hu_value = float(pixel_value * self._slope + self._intercept)
                x_values.append(x)
                y_values.append(hu_value)
        
        return x_values, y_values
    
    def _get_line_points(self, x0: int, y0: int, x1: int, y1: int) -> List[Tuple[int, int]]:
        """Get points along a line using Bresenham's algorithm."""
        points = []
        is_steep = abs(y1 - y0) > abs(x1 - x0)
        
        if is_steep:
            x0, y0 = y0, x0
            x1, y1 = y1, x1
        
        rev = False
        if x0 > x1:
            x0, x1 = x1, x0
            y0, y1 = y1, y0
            rev = True
        
        delta_x = x1 - x0
        delta_y = abs(y1 - y0)
        error = int(delta_x / 2)
        y = y0
        y_step = None
        
        if y0 < y1:
            y_step = 1
        else:
            y_step = -1
        
        for x in range(x0, x1 + 1):
            if is_steep:
                points.append((y, x))
            else:
                points.append((x, y))
            
            error -= delta_y
            if error < 0:
                y += y_step
                error += delta_x
        
        if rev:
            points.reverse()
        
        return points
    
    def _capture_profile_measurement(self) -> bool:
        """Capture the current profile as a measurement."""
        if not self.has_series or not self._measurement_service:
            return False
        
        slice_obj = self.current_slice_object
        if slice_obj is None or slice_obj.pixel_array is None:
            return False
        
        # Get profile data
        pixel_array = slice_obj.pixel_array
        if self._profile_type == 'row':
            x_values, y_values = self._extract_row_profile(pixel_array)
            start_pos = (self._profile_start_x, self._current_row)
            end_pos = (self._profile_end_x, self._current_row)
        elif self._profile_type == 'horizontal':
            x_values, y_values = self._extract_horizontal_profile(pixel_array)
            start_pos = (self._profile_start_x, self._current_row)
            end_pos = (self._profile_end_x, self._current_row)
        elif self._profile_type == 'vertical':
            x_values, y_values = self._extract_vertical_profile(pixel_array)
            start_pos = (self._current_row, self._profile_start_y)
            end_pos = (self._current_row, self._profile_end_y)
        else:  # diagonal or custom
            x_values, y_values = self._extract_custom_profile(pixel_array)
            start_pos = (self._profile_start_x, self._profile_start_y)
            end_pos = (self._profile_end_x, self._profile_end_y)
        
        if not x_values or not y_values:
            return False
        
        # Calculate profile statistics
        profile_array = np.array(y_values)
        profile_mean = float(np.mean(profile_array))
        profile_std = float(np.std(profile_array))
        profile_min = float(np.min(profile_array))
        profile_max = float(np.max(profile_array))
        profile_length = len(profile_array)
        
        # Store profile data in statistics for later retrieval
        profile_stats = {
            'profile_data': y_values,
            'profile_x_data': x_values,
            'profile_length': profile_length,
            'profile_mean': profile_mean,
            'profile_std': profile_std,
            'profile_min': profile_min,
            'profile_max': profile_max,
            'start_pos': start_pos,
            'end_pos': end_pos,
            'profile_type': self._profile_type,
            'profile_width': self._profile_width
        }
        
        # Create measurement using service
        measurement = self._measurement_service.create_profile_measurement(
            series=self.series,
            slice_index=self.current_slice,
            start_pos=start_pos,
            end_pos=end_pos,
            profile_width=self._profile_width,
            name=f"Profile {self._measurement_service.measurement_collection.count + 1}",
            slope=self._slope,
            intercept=self._intercept
        )
        
        if measurement:
            # Add profile data to measurement statistics
            measurement.statistics.update(profile_stats)
            
            # Update measurement combo
            self._update_measurement_combo()
            
            # Select the new measurement
            self._current_measurement_id = measurement.measurement_id
            self._show_measurement_profile(measurement.measurement_id)
            
            # Emit signal
            self.profile_measurement_captured.emit(measurement.measurement_id)
            
            return True
        
        return False
    
    def _show_current_profile(self):
        """Show the current profile."""
        self._showing_measurement_profile = False
        if self._profile_mode_enabled:
            self._update_profile_display()
    
    def _show_measurement_profile(self, measurement_id: str):
        """Show a specific measurement profile."""
        if not self._measurement_service:
            return
        
        measurement = self._measurement_service.get_measurement_by_id(measurement_id)
        if not measurement:
            return
        
        self._showing_measurement_profile = True
        self._current_measurement_id = measurement_id
        
        # Clear current profile series
        if self._current_profile_series:
            self._current_profile_series.clear()
        else:
            self._current_profile_series = QSplineSeries()
            self._current_profile_series.setName(f"Measurement: {measurement.name}")
            self._current_profile_series.setColor(Qt.magenta)
            pen = self._current_profile_series.pen()
            pen.setWidth(2)
            self._current_profile_series.setPen(pen)
            self._chart.addSeries(self._current_profile_series)
            self._current_profile_series.attachAxis(self._axis_x)
            self._current_profile_series.attachAxis(self._axis_y)
        
        # Check if measurement has profile data
        if hasattr(measurement, 'statistics') and 'profile_data' in measurement.statistics:
            y_values = measurement.statistics['profile_data']
            x_values = measurement.statistics.get('profile_x_data', list(range(len(y_values))))
        else:
            # Create synthetic profile from ROI statistics
            x_values = [0, 1, 2]  # Simple profile
            y_values = [measurement.hu_min, measurement.hu_mean, measurement.hu_max]
        
        # Populate series
        self._current_profile_series.clear()
        for x, y in zip(x_values, y_values):
            self._current_profile_series.append(x, y)
        
        # Update chart title
        if self._chart:
            self._chart.setTitle(f"Profile: {measurement.name or measurement.measurement_id[:8]}")
        
        # Update axes
        self._update_axes()
        
        # Emit signal
        self.measurement_selected.emit(measurement_id)
    
    def _update_measurement_combo(self):
        """Update the measurement combo box with available measurements."""
        if not self._measurement_service:
            self._measurement_combo.clear()
            self._measurement_combo.addItem("Current Profile", "")
            return
        
        self._measurement_combo.blockSignals(True)
        try:
            self._measurement_combo.clear()
            self._measurement_combo.addItem("Current Profile", "")
            
            # Get measurements for current series if available
            if self.series:
                measurements = self._measurement_service.get_measurements_for_series(self.series.series_uid)
            else:
                measurements = self._measurement_service.measurements
            
            for measurement in measurements:
                # Use name if available, otherwise use short ID
                display_name = measurement.name or f"Measurement {measurement.measurement_id[:8]}"
                self._measurement_combo.addItem(f"{display_name} ({measurement.measurement_id})", measurement.measurement_id)
        finally:
            self._measurement_combo.blockSignals(False)
    
    def _clear_measurement_series(self):
        """Clear all measurement series from the chart."""
        for series in self._measurement_series.values():
            self._chart.removeSeries(series)
            if hasattr(series, 'deleteLater'):
                series.deleteLater()
        self._measurement_series.clear()
    
    def _show_all_measurements(self):
        """Show all measurements as profiles on the chart."""
        if not self._measurement_service:
            return
        
        # Clear existing measurement series
        self._clear_measurement_series()
        
        # Get measurements for current series
        if self.series:
            measurements = self._measurement_service.get_measurements_for_series(self.series.series_uid)
        else:
            measurements = self._measurement_service.measurements
        
        # Create series for each measurement
        colors = [Qt.red, Qt.green, Qt.blue, Qt.cyan, Qt.magenta, Qt.yellow]
        for i, measurement in enumerate(measurements):
            if hasattr(measurement, 'statistics') and 'profile_data' in measurement.statistics:
                # Create series for this measurement
                series = QSplineSeries()
                series.setName(measurement.name or f"M{measurement.measurement_id[:8]}")
                series.setColor(colors[i % len(colors)])
                
                # Add profile data
                y_values = measurement.statistics['profile_data']
                x_values = measurement.statistics.get('profile_x_data', list(range(len(y_values))))
                
                for x, y in zip(x_values, y_values):
                    series.append(x, y)
                
                # Add to chart
                self._chart.addSeries(series)
                series.attachAxis(self._axis_x)
                series.attachAxis(self._axis_y)
                
                # Store reference
                self._measurement_series[measurement.measurement_id] = series
        
        # Update axes
        self._update_axes()
    
    # Additional utility methods
    def set_measurement_service(self, service: 'MeasurementService'):
        """Set the measurement service."""
        self._measurement_service = service
        self._update_measurement_combo()
    
    def set_profile_mode(self, enabled: bool):
        """Set whether profile mode is enabled."""
        self._profile_mode_checkbox.setChecked(enabled)
        self._profile_mode_enabled = enabled
        if enabled:
            self._enter_profile_mode()
        else:
            self._exit_profile_mode()
    
    def set_profile_points(self, x1: int, y1: int, x2: int, y2: int):
        """Set profile start and end points."""
        self._profile_start_x = x1
        self._profile_start_y = y1
        self._profile_end_x = x2
        self._profile_end_y = y2
        
        # Update controls
        if self._profile_type in ['horizontal', 'row']:
            self._profile_start_spin.setValue(x1)
            self._profile_end_spin.setValue(x2)
        elif self._profile_type == 'vertical':
            self._profile_start_spin.setValue(y1)
            self._profile_end_spin.setValue(y2)
        
        # Update display
        if self._profile_mode_enabled:
            self._update_profile_display()
        
        self.profile_points_changed.emit(x1, y1, x2, y2)
    
    def refresh(self):
        """Refresh the curve view."""
        if self.has_series:
            if self._profile_mode_enabled:
                self._update_profile_display()
            else:
                self._update_from_series()
        self._update_measurement_combo()


# For backward compatibility, create an alias
CurveView = SeriesCurveView

# Keep the original class available for backward compatibility
__all__ = ['SeriesCurveView', 'CurveView']