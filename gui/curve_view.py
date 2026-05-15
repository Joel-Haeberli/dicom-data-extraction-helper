#!/usr/bin/env python3
"""
Curve View Widget for displaying pixel data as a line chart.

Displays HU values from a row of the measurement window with configurable axis ranges.
"""

from typing import Optional, List
import numpy as np

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QDoubleSpinBox, QSizePolicy, QSpinBox, QPushButton, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QDateTime
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis, QSplineSeries
from PySide6.QtGui import QImage, QPainter


class CurveView(QWidget):
    """
    Widget for displaying a curve of pixel HU values from a measurement window row.
    
    Features:
    - Line chart showing HU values vs X position
    - Manual axis range controls
    - Automatic axis scaling based on data
    - Row selection for HU profile
    - Dark mode styling
    """
    
    # Signal emitted when the selected row changes
    row_changed = Signal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
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
        self._chart_view: Optional[QChartView] = None
        
        # Axis range inputs
        self._x_min_input: Optional[QDoubleSpinBox] = None
        self._x_max_input: Optional[QDoubleSpinBox] = None
        self._y_min_input: Optional[QDoubleSpinBox] = None
        self._y_max_input: Optional[QDoubleSpinBox] = None
        
        # UI Setup
        self._setup_ui()
        self._setup_connections()
        
        # Dark mode styling
        self._apply_dark_mode()
    
    def _setup_ui(self):
        """Setup the widget layout with chart and axis controls."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)
        
        # Create chart view
        self._chart = QChart()
        self._chart.setTitle("HU Profile (Row: 0)")
        self._chart.legend().hide()
        self._chart.setAnimationOptions(QChart.SeriesAnimations)
        
        # Use spline series for smooth curve
        self._series = QSplineSeries()
        self._series.setName("HU Values")
        self._series.setColor(Qt.cyan)  # Cyan for dark mode visibility
        self._chart.addSeries(self._series)
        
        # Create axes
        self._axis_x = QValueAxis()
        self._axis_x.setTitleText("X Position (window-relative)")
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
        self._row_spin.setToolTip("Select which row of the window to display in the HU profile")
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
        
        # Export button
        self._export_button = QPushButton("Export PNG")
        self._export_button.setToolTip("Export the curve as PNG image")
        controls_layout.addWidget(self._export_button)
        
        main_layout.addLayout(controls_layout, 0)
    
    def _setup_connections(self):
        """Setup signal connections for axis range inputs."""
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
    
    def _on_row_changed(self, value: int):
        """Handler for row selector changes."""
        self._current_row = value
        self.row_changed.emit(value)
    
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
        
        # Update inputs to show current data ranges
        if self._x_min_input:
            self._x_min_input.setValue(x_min)
        if self._x_max_input:
            self._x_max_input.setValue(x_max)
        if self._y_min_input:
            self._y_min_input.setValue(y_min)
        if self._y_max_input:
            self._y_max_input.setValue(y_max)
        
        self._update_axes()
    
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
        if self._series:
            self._series.clear()
        self._x_values = []
        self._y_values = []
        
        # Reset axes
        if self._axis_x:
            self._axis_x.setRange(0, 1)
        if self._axis_y:
            self._axis_y.setRange(0, 1)
        
        # Reset row in title but keep spinbox value
        # (spinbox is controlled by the window, not by data clearing)
        if self._chart:
            self._chart.setTitle("HU Profile (Row: 0)")
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
