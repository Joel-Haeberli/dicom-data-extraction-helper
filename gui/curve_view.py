#!/usr/bin/env python3
"""
Curve View Widget for displaying pixel data as a line chart.

Displays HU values from a row of the measurement window with configurable axis ranges.
"""

from typing import Optional, List
import numpy as np

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QDoubleSpinBox, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis, QSplineSeries


class CurveView(QWidget):
    """
    Widget for displaying a curve of pixel HU values from a measurement window row.
    
    Features:
    - Line chart showing HU values vs X position
    - Manual axis range controls
    - Automatic axis scaling based on data
    - Dark mode styling
    """
    
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
        self._chart.setTitle("HU Profile (First Row of Window)")
        self._chart.legend().hide()
        self._chart.setAnimationOptions(QChart.SeriesAnimations)
        
        # Use spline series for smooth curve
        self._series = QSplineSeries()
        self._series.setName("HU Values")
        self._series.setColor(Qt.cyan)  # Cyan for dark mode visibility
        self._chart.addSeries(self._series)
        
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
        
        self._chart_view = QChartView(self._chart)
        self._chart_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        main_layout.addWidget(self._chart_view, 1)
        
        # Axis range controls
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(4)
        
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
        
        main_layout.addLayout(controls_layout, 0)
    
    def _setup_connections(self):
        """Setup signal connections for axis range inputs."""
        if self._x_min_input:
            self._x_min_input.valueChanged.connect(self._on_axis_range_changed)
        if self._x_max_input:
            self._x_max_input.valueChanged.connect(self._on_axis_range_changed)
        if self._y_min_input:
            self._y_min_input.valueChanged.connect(self._on_axis_range_changed)
        if self._y_max_input:
            self._y_max_input.valueChanged.connect(self._on_axis_range_changed)
    
    def _on_axis_range_changed(self, value):
        """Handler for axis range input changes."""
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
        for spin in [self._x_min_input, self._x_max_input, self._y_min_input, self._y_max_input]:
            if spin:
                spin.setStyleSheet("""
                    QDoubleSpinBox {
                        background-color: #2b2b2b;
                        color: #e0e0e0;
                        border: 1px solid #444;
                        padding: 2px;
                    }
                    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                        background-color: #3c3c3c;
                    }
                """)
    
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
        
        # Update axes (use automatic mode if manual ranges not set)
        if (self._manual_x_min is None and self._manual_x_max is None and
            self._manual_y_min is None and self._manual_y_max is None):
            # Auto mode: use data min/max
            x_min = min(self._x_values) if self._x_values else 0
            x_max = max(self._x_values) if self._x_values else 1
            y_min = min(self._y_values) if self._y_values else 0
            y_max = max(self._y_values) if self._y_values else 1
            
            # Add some padding
            x_range = x_max - x_min
            y_range = y_max - y_min
            if x_range > 0:
                x_min -= x_range * 0.05
                x_max += x_range * 0.05
            if y_range > 0:
                y_min -= y_range * 0.05
                y_max += y_range * 0.05
            
            # Update inputs to show current auto ranges
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
        if self._manual_x_min is not None and self._manual_x_max is not None:
            x_min = self._manual_x_min
            x_max = self._manual_x_max
        else:
            x_min = min(self._x_values) if self._x_values else 0
            x_max = max(self._x_values) if self._x_values else 1
            # Add padding in auto mode
            x_range = x_max - x_min
            if x_range > 0:
                x_min -= x_range * 0.05
                x_max += x_range * 0.05
            else:
                x_min -= 0.5
                x_max += 0.5
        
        if self._manual_y_min is not None and self._manual_y_max is not None:
            y_min = self._manual_y_min
            y_max = self._manual_y_max
        else:
            y_min = min(self._y_values) if self._y_values else 0
            y_max = max(self._y_values) if self._y_values else 1
            # Add padding in auto mode
            y_range = y_max - y_min
            if y_range > 0:
                y_min -= y_range * 0.05
                y_max += y_range * 0.05
            else:
                y_min -= 0.5
                y_max += 0.5
        
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
    
    def set_manual_ranges(self, x_min: float, x_max: float, y_min: float, y_max: float):
        """
        Set manual axis ranges.
        
        Args:
            x_min: Minimum X value
            x_max: Maximum X value
            y_min: Minimum Y (HU) value
            y_max: Maximum Y (HU) value
        """
        self._manual_x_min = x_min
        self._manual_x_max = x_max
        self._manual_y_min = y_min
        self._manual_y_max = y_max
        
        # Update input fields
        if self._x_min_input:
            self._x_min_input.setValue(x_min)
        if self._x_max_input:
            self._x_max_input.setValue(x_max)
        if self._y_min_input:
            self._y_min_input.setValue(y_min)
        if self._y_max_input:
            self._y_max_input.setValue(y_max)
        
        self._update_axes()
    
    def reset_manual_ranges(self):
        """Reset manual ranges to automatic mode."""
        self._manual_x_min = None
        self._manual_x_max = None
        self._manual_y_min = None
        self._manual_y_max = None
        
        # Re-update axes with auto ranges
        if self._x_values and self._y_values:
            self.set_data(self._x_values, self._y_values)
