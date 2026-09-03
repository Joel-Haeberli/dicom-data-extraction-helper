#!/usr/bin/env python3
"""
Comparison View for DICOM Data Extraction Helper.

This viewer provides multi-curve measurement comparison functionality using QtCharts.
It allows users to compare HU profiles from different measurements or series.
"""

from typing import Optional, List, Dict, Any, TYPE_CHECKING
import numpy as np

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QComboBox,
    QPushButton, QSpinBox, QDoubleSpinBox, QSizePolicy, QScrollArea,
    QFrame, QGroupBox
)
from PySide6.QtCore import Qt, Signal, QModelIndex
from PySide6.QtCharts import (
    QChart, QChartView, QLineSeries, QSplineSeries, QScatterSeries,
    QValueAxis, QCategoryAxis, QLegend, QAbstractSeries
)
from PySide6.QtGui import QColor, QPen, QFont

if TYPE_CHECKING:
    from models.image_series import ImageSeries
    from models.measurement import Measurement, MeasurementCollection
    from services.measurement_service import MeasurementService


class ComparisonView(QWidget):
    """
    Advanced comparison view for displaying multiple measurement curves.
    
    Features:
    - Multiple measurement curve display using QtCharts
    - Measurement selection checkboxes
    - Color customization per measurement
    - Row offset adjustment per measurement
    - Chart type selection (line, spline, scatter)
    - Statistical overlay options
    - Export chart to image
    - Measurement filtering by series/study
    
    Signals:
    - measurement_selected: Emitted when a measurement is selected
    - measurements_updated: Emitted when the displayed measurements change
    """
    
    # Signals
    measurement_selected = Signal(str)  # measurement_id
    measurements_updated = Signal(List[str])  # measurement_ids
    
    # Available chart types
    CHART_TYPES = ['line', 'spline', 'scatter']
    
    def __init__(self, measurement_service: Optional['MeasurementService'] = None,
                 parent=None):
        """Initialize the comparison view."""
        super().__init__(parent)
        
        # State
        self._measurement_service = measurement_service
        self._series: Optional['ImageSeries'] = None
        self._chart: Optional[QChart] = None
        self._chart_view: Optional[QChartView] = None
        
        # Measurement data and display settings
        self._displayed_measurements: Dict[str, Dict[str, Any]] = {}
        self._available_series: List['ImageSeries'] = []
        self._chart_series: Dict[str, QAbstractSeries] = {}
        self._colors: List[QColor] = self._generate_default_colors()
        
        # Default settings
        self._current_chart_type = 'line'
        self._show_legend = True
        self._show_grid = True
        self._auto_scale = True
        
        # Setup UI
        self._setup_ui()
        self._connect_signals()
        
        # Apply styling
        self._apply_chart_styling()
    
    def _generate_default_colors(self) -> List[QColor]:
        """Generate a list of default colors for measurement curves."""
        return [
            QColor(255, 0, 0),      # Red
            QColor(0, 255, 0),      # Green
            QColor(0, 0, 255),      # Blue
            QColor(255, 255, 0),    # Yellow
            QColor(255, 0, 255),    # Magenta
            QColor(0, 255, 255),    # Cyan
            QColor(255, 128, 0),    # Orange
            QColor(128, 0, 255),    # Purple
            QColor(0, 128, 128),    # Teal
            QColor(128, 128, 0),    # Olive
            QColor(255, 192, 203),  # Pink
            QColor(165, 42, 42),    # Brown
        ]
    
    def _setup_ui(self):
        """Setup the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)
        
        # Create chart view
        self._create_chart()
        layout.addWidget(self._chart_view, 1)
        
        # Create control panels
        self._create_measurement_controls(layout)
        self._create_display_controls(layout)
        
        # Info label
        self._info_label = QLabel("No measurements to compare", self)
        self._info_label.setStyleSheet("color: #e0e0e0; font-style: italic;")
        layout.addWidget(self._info_label)
    
    def _create_chart(self):
        """Create the QtCharts chart and view."""
        # Create chart
        self._chart = QChart()
        self._chart.setTitle("Measurement Comparison")
        self._chart.setAnimationOptions(QChart.NoAnimation)
        self._chart.setBackgroundVisible(False)
        
        # Create chart view
        self._chart_view = QChartView(self._chart)
        self._chart_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Apply dark theme styling
        self._apply_chart_styling()
        
        # Create axes
        self._axis_x = QValueAxis()
        self._axis_x.setTitleText("Position (pixels)")
        self._axis_x.setLabelsColor(QColor(224, 224, 224))
        self._axis_x.setTitleBrush(QColor(224, 224, 224))
        
        self._axis_y = QValueAxis()
        self._axis_y.setTitleText("HU Value")
        self._axis_y.setLabelsColor(QColor(224, 224, 224))
        self._axis_y.setTitleBrush(QColor(224, 224, 224))
        
        self._chart.addAxis(self._axis_x, Qt.AlignBottom)
        self._chart.addAxis(self._axis_y, Qt.AlignLeft)
        
        # Configure legend
        self._legend = self._chart.legend()
        self._legend.setVisible(self._show_legend)
        self._legend.setLabelBrush(QColor(224, 224, 224))
    
    def _apply_chart_styling(self):
        """Apply dark theme styling to the chart."""
        if self._chart:
            # Chart background
            self._chart.setBackgroundBrush(QColor(43, 43, 43))
            
            # Chart title
            title_font = QFont()
            title_font.setPointSize(12)
            title_font.setBold(True)
            self._chart.setTitleFont(title_font)
            title_brush = self._chart.titleBrush()
            title_brush.setColor(QColor(224, 224, 224))
            self._chart.setTitleBrush(title_brush)
            
            # Plot area background
            plot_area = self._chart.plotArea()
            if hasattr(plot_area, 'setBackgroundBrush'):
                plot_area.setBackgroundBrush(QColor(30, 30, 30))
        
        if self._chart_view:
            self._chart_view.setStyleSheet("background-color: #2b2b2b; border: 1px solid #444;")
    
    def _create_measurement_controls(self, layout):
        """Create measurement selection controls."""
        # Measurement controls group
        controls_group = QGroupBox("Measurements", self)
        controls_layout = QVBoxLayout(controls_group)
        controls_layout.setSpacing(4)
        
        # Measurement selection area
        self._measurement_selection_scroll = QScrollArea()
        self._measurement_selection_scroll.setWidgetResizable(True)
        self._measurement_selection_scroll.setMaximumHeight(120)
        
        # Container for measurement checkboxes
        self._measurement_container = QWidget()
        self._measurement_layout = QVBoxLayout(self._measurement_container)
        self._measurement_layout.setContentsMargins(4, 4, 4, 4)
        self._measurement_layout.setSpacing(4)
        
        # Add a placeholder label
        self._no_measurements_label = QLabel("No measurements available", self)
        self._no_measurements_label.setStyleSheet("color: #888;")
        self._no_measurements_label.setAlignment(Qt.AlignCenter)
        self._measurement_layout.addWidget(self._no_measurements_label)
        self._measurement_layout.addStretch(1)
        
        self._measurement_selection_scroll.setWidget(self._measurement_container)
        controls_layout.addWidget(self._measurement_selection_scroll)
        
        # Control buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        # Select all / Clear all buttons
        self._select_all_button = QPushButton("Select All", self)
        self._select_all_button.clicked.connect(self._select_all_measurements)
        button_layout.addWidget(self._select_all_button)
        
        self._clear_all_button = QPushButton("Clear All", self)
        self._clear_all_button.clicked.connect(self._clear_all_measurements)
        button_layout.addWidget(self._clear_all_button)
        
        button_layout.addStretch(1)
        controls_layout.addLayout(button_layout)
        
        layout.addWidget(controls_group)
    
    def _create_display_controls(self, layout):
        """Create display and chart configuration controls."""
        # Display controls group
        display_group = QGroupBox("Display Options", self)
        display_layout = QHBoxLayout(display_group)
        display_layout.setSpacing(8)
        
        # Chart type selector
        display_layout.addWidget(QLabel("Chart Type:", self))
        self._chart_type_combo = QComboBox(self)
        self._chart_type_combo.addItems(self.CHART_TYPES)
        self._chart_type_combo.setCurrentText('line')
        self._chart_type_combo.currentTextChanged.connect(self._update_chart_type)
        display_layout.addWidget(self._chart_type_combo)
        
        # Legend toggle
        self._legend_checkbox = QCheckBox("Show Legend", self)
        self._legend_checkbox.setChecked(True)
        self._legend_checkbox.stateChanged.connect(self._toggle_legend)
        display_layout.addWidget(self._legend_checkbox)
        
        # Grid toggle
        self._grid_checkbox = QCheckBox("Show Grid", self)
        self._grid_checkbox.setChecked(True)
        self._grid_checkbox.stateChanged.connect(self._toggle_grid)
        display_layout.addWidget(self._grid_checkbox)
        
        # Auto scale toggle
        self._auto_scale_checkbox = QCheckBox("Auto Scale", self)
        self._auto_scale_checkbox.setChecked(True)
        self._auto_scale_checkbox.stateChanged.connect(self._toggle_auto_scale)
        display_layout.addWidget(self._auto_scale_checkbox)
        
        display_layout.addStretch(1)
        
        # Export button
        self._export_button = QPushButton("Export Chart", self)
        self._export_button.clicked.connect(self.export_chart_to_image)
        display_layout.addWidget(self._export_button)
        
        layout.addWidget(display_group)
    
    def _connect_signals(self):
        """Connect internal signals."""
        # Connect series changes to measurement updates
        pass
    
    def _generate_measurement_series(self, measurement: 'Measurement') -> Optional[List[Dict[str, Any]]]:
        """
        Generate HU profile data for a measurement.
        
        This extracts pixel data along a profile for the measurement.
        For now, it uses the measurement position and creates a simple profile.
        """
        # This is a simplified version - in a full implementation,
        # this would extract actual profile data from the series
        
        # For ROI measurements, create a circular profile
        size = measurement.roi_size
        if size <= 0:
            size = 3
        
        # Create synthetic profile data (replace with actual extraction)
        center_x, center_y = measurement.x, measurement.y
        profile_length = size * 2 + 1
        
        # Generate some test data
        x_values = list(range(profile_length))
        # Use HU mean value with some variation
        base_hu = measurement.hu_mean
        y_values = [base_hu + (i - profile_length/2) * 10 for i in range(profile_length)]
        
        return [
            {'x': x_values, 'y': y_values, 'name': measurement.name or f'M{len(self._displayed_measurements) + 1}'}
        ]
    
    def _get_measurement_profile_data(self, measurement: 'Measurement') -> Optional[Dict[str, Any]]:
        """
        Get profile data for a measurement.
        
        Returns:
            Dictionary with x and y values for the profile
        """
        # If measurement has profile data in statistics, use that
        if hasattr(measurement, 'statistics') and 'profile_data' in measurement.statistics:
            profile_data = measurement.statistics['profile_data']
            return {
                'x': list(range(len(profile_data))),
                'y': profile_data,
                'name': measurement.name or f'Profile {measurement.measurement_id[:8]}'
            }
        
        # If it's a point measurement, create simple profile
        if measurement.roi_form == 'point':
            return {
                'x': [0],
                'y': [measurement.hu_mean],
                'name': measurement.name or f'Point {measurement.measurement_id[:8]}'
            }
        
        # For ROI measurements, create a synthetic profile based on ROI form
        return self._generate_synthetic_roi_profile(measurement)
    
    def _generate_synthetic_roi_profile(self, measurement: 'Measurement') -> Dict[str, Any]:
        """Generate a synthetic profile for ROI measurements."""
        size = max(1, measurement.roi_size)
        profile_length = size * 2 + 1
        
        # Create profile centered at measurement position
        center = profile_length // 2
        base_value = measurement.hu_mean
        
        # Create a Gaussian-like profile
        x_values = list(range(profile_length))
        y_values = []
        for i in range(profile_length):
            distance = abs(i - center)
            # Gaussian falloff from center
            falloff = measurement.hu_std * np.exp(-(distance * distance) / (size * size))
            y_values.append(base_value + falloff)
        
        return {
            'x': x_values,
            'y': y_values,
            'name': measurement.name or f'ROI {measurement.measurement_id[:8]}'
        }
    
    def update_measurements(self, measurements: List['Measurement']):
        """Update the list of measurements to display."""
        self._clear_chart_series()
        
        if not measurements:
            self._show_no_measurements_message()
            return
        
        # Store measurements and create series
        for i, measurement in enumerate(measurements):
            measurement_id = measurement.measurement_id
            
            # Get color for this measurement
            color = self._colors[i % len(self._colors)]
            
            # Get profile data
            profile_data = self._get_measurement_profile_data(measurement)
            if not profile_data:
                continue
            
            # Store measurement info
            self._displayed_measurements[measurement_id] = {
                'measurement': measurement,
                'color': color,
                'profile_data': profile_data,
                'offset': 0,  # Vertical offset for comparison
                'visible': True
            }
            
            # Create series for this measurement
            self._create_measurement_series(measurement_id, profile_data, color)
        
        # Update chart display
        self._update_chart_display()
        self._update_measurement_selection_ui()
        self._update_info_label()
        
        # Emit signal
        self.measurements_updated.emit(list(self._displayed_measurements.keys()))
    
    def _create_measurement_series(self, measurement_id: str, 
                                  profile_data: Dict[str, Any], 
                                  color: QColor):
        """Create a series for a measurement."""
        # Determine series type based on current chart type
        if self._current_chart_type == 'line':
            series = QLineSeries()
        elif self._current_chart_type == 'spline':
            series = QSplineSeries()
        else:  # scatter
            series = QScatterSeries()
        
        # Set series properties
        series.setName(profile_data['name'])
        pen = QPen(color)
        pen.setWidth(2)
        series.setPen(pen)
        
        # For line/spline series, add points
        if self._current_chart_type in ['line', 'spline']:
            x_values = profile_data['x']
            y_values = [y + 0 for y in profile_data['y']]  # Add offset later
            
            for x, y in zip(x_values, y_values):
                series.append(x, y)
        else:  # scatter
            x_values = profile_data['x']
            y_values = profile_data['y']
            for x, y in zip(x_values, y_values):
                series.append(x, y)
        
        # Add series to chart
        self._chart.addSeries(series)
        series.attachAxis(self._axis_x)
        series.attachAxis(self._axis_y)
        
        # Store reference
        self._chart_series[measurement_id] = series
    
    def _clear_chart_series(self):
        """Clear all measurement series from the chart."""
        for series in self._chart_series.values():
            self._chart.removeSeries(series)
            if hasattr(series, 'deleteLater'):
                series.deleteLater()
        
        self._chart_series.clear()
        self._displayed_measurements.clear()
    
    def _update_chart_display(self):
        """Update the chart display with current series."""
        if not self._chart_series:
            self._show_no_measurements_message()
            return
        
        # Adjust axes based on data
        if self._auto_scale:
            self._auto_scale_axes()
        
        # Ensure legend is properly configured
        if self._legend:
            self._legend.setVisible(self._show_legend)
    
    def _update_measurement_selection_ui(self):
        """Update the measurement selection UI."""
        # Clear existing controls
        self._clear_measurement_selection_ui()
        
        if not self._displayed_measurements:
            self._show_no_measurements_message()
            return
        
        # Add checkboxes for each measurement
        for measurement_id, measurement_info in self._displayed_measurements.items():
            measurement = measurement_info['measurement']
            color = measurement_info['color']
            
            # Create control widget for this measurement
            control_widget = self._create_measurement_control_widget(
                measurement_id, measurement, color
            )
            self._measurement_layout.addWidget(control_widget)
        
        self._measurement_layout.addStretch(1)
    
    def _create_measurement_control_widget(self, measurement_id: str, 
                                         measurement: 'Measurement', 
                                         color: QColor) -> QWidget:
        """Create a control widget for a single measurement."""
        # Create container widget
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)
        
        # Color indicator
        color_label = QLabel()
        color_label.setFixedSize(16, 16)
        color_label.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #000;")
        layout.addWidget(color_label)
        
        # Measurement name/description
        name_label = QLabel(measurement.name or f"Measurement {measurement.measurement_id[:8]}")
        name_label.setToolTip(f"Form: {measurement.roi_form}, Size: {measurement.roi_size}")
        layout.addWidget(name_label, 1)
        
        # Visibility checkbox
        visible_checkbox = QCheckBox("Show", container)
        visible_checkbox.setChecked(True)
        visible_checkbox.setProperty("measurement_id", measurement_id)
        visible_checkbox.stateChanged.connect(self._on_measurement_visibility_changed)
        layout.addWidget(visible_checkbox)
        
        # Offset control (for vertical comparison)
        offset_spin = QSpinBox(container)
        offset_spin.setRange(-1000, 1000)
        offset_spin.setValue(0)
        offset_spin.setSingleStep(10)
        offset_spin.setSuffix(" HU")
        offset_spin.setProperty("measurement_id", measurement_id)
        offset_spin.valueChanged.connect(self._on_measurement_offset_changed)
        layout.addWidget(offset_spin)
        
        return container
    
    def _clear_measurement_selection_ui(self):
        """Clear the measurement selection UI."""
        # Remove all widgets except the no measurements label
        for i in reversed(range(self._measurement_layout.count())):
            item = self._measurement_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                widget.setParent(None)
        
        # Show no measurements message if no measurements
        if not self._displayed_measurements:
            self._measurement_layout.addWidget(self._no_measurements_label)
    
    def _show_no_measurements_message(self):
        """Show the no measurements message."""
        self._clear_chart_series()
        self._clear_measurement_selection_ui()
        self._measurement_layout.addWidget(self._no_measurements_label)
        self._update_info_label()
    
    def _update_info_label(self):
        """Update the info label."""
        count = len(self._displayed_measurements)
        if count == 0:
            self._info_label.setText("No measurements to compare")
        elif count == 1:
            self._info_label.setText(f"Showing 1 measurement curve")
        else:
            self._info_label.setText(f"Showing {count} measurement curves")
    
    def _auto_scale_axes(self):
        """Auto-scale the chart axes based on current data."""
        if not self._chart_series:
            return
        
        # Find min/max values across all series
        min_x, max_x = float('inf'), float('-inf')
        min_y, max_y = float('inf'), float('-inf')
        
        for series in self._chart_series.values():
            for point in series.points():
                x = point.x()
                y = point.y()
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)
        
        # Add some padding
        if min_x != float('inf'):
            x_range = max_x - min_x
            y_range = max_y - min_y
            
            min_x -= x_range * 0.1
            max_x += x_range * 0.1
            min_y -= y_range * 0.1
            max_y += y_range * 0.1
            
            # Update axes
            self._axis_x.setRange(min_x, max_x)
            self._axis_y.setRange(min_y, max_y)
    
    def _select_all_measurements(self):
        """Select all measurements for display."""
        for measurement_id in self._displayed_measurements:
            self._displayed_measurements[measurement_id]['visible'] = True
        self._update_chart_visibility()
    
    def _clear_all_measurements(self):
        """Clear all measurements from display."""
        for measurement_id in self._displayed_measurements:
            self._displayed_measurements[measurement_id]['visible'] = False
        self._update_chart_visibility()
    
    def _update_chart_visibility(self):
        """Update visibility of all chart series based on their state."""
        for measurement_id, series in self._chart_series.items():
            if measurement_id in self._displayed_measurements:
                visible = self._displayed_measurements[measurement_id]['visible']
                series.setVisible(visible)
    
    def _on_measurement_visibility_changed(self, state: int):
        """Handle measurement visibility checkbox changes."""
        checkbox = self.sender()
        if checkbox and hasattr(checkbox, 'measurement_id'):
            measurement_id = checkbox.measurement_id
            visible = state == Qt.Checked
            
            if measurement_id in self._displayed_measurements:
                self._displayed_measurements[measurement_id]['visible'] = visible
                
                if measurement_id in self._chart_series:
                    self._chart_series[measurement_id].setVisible(visible)
    
    def _on_measurement_offset_changed(self, value: int):
        """Handle measurement offset changes."""
        spin_box = self.sender()
        if spin_box and hasattr(spin_box, 'measurement_id'):
            measurement_id = spin_box.measurement_id
            
            if measurement_id in self._displayed_measurements:
                self._displayed_measurements[measurement_id]['offset'] = value
                # Update series data with new offset
                self._update_measurement_series_data(measurement_id)
    
    def _update_measurement_series_data(self, measurement_id: str):
        """Update the data for a specific measurement series with offset."""
        if (measurement_id not in self._displayed_measurements or 
            measurement_id not in self._chart_series):
            return
        
        measurement_info = self._displayed_measurements[measurement_id]
        series = self._chart_series[measurement_id]
        profile_data = measurement_info['profile_data']
        offset = measurement_info['offset']
        
        # Clear and recreate series with offset
        series.clear()
        
        for x, y in zip(profile_data['x'], profile_data['y']):
            series.append(x, y + offset)
    
    def _update_chart_type(self, chart_type: str):
        """Update the chart type for all series."""
        self._current_chart_type = chart_type
        
        # Recreate all series with new type
        current_measurement_ids = list(self._displayed_measurements.keys())
        self._clear_chart_series()
        
        for measurement_id in current_measurement_ids:
            if measurement_id in self._displayed_measurements:
                measurement_info = self._displayed_measurements[measurement_id]
                measurement = measurement_info['measurement']
                color = measurement_info['color']
                profile_data = measurement_info['profile_data']
                
                # Recreate series with new type
                self._create_measurement_series(measurement_id, profile_data, color)
                
                # Apply visibility and offset
                series = self._chart_series[measurement_id]
                series.setVisible(measurement_info['visible'])
                self._update_measurement_series_data(measurement_id)
        
        self._update_chart_display()
    
    def _toggle_legend(self, state: int):
        """Toggle legend visibility."""
        self._show_legend = state == Qt.Checked
        if self._legend:
            self._legend.setVisible(self._show_legend)
    
    def _toggle_grid(self, state: int):
        """Toggle grid visibility."""
        self._show_grid = state == Qt.Checked
        if self._axis_x:
            self._axis_x.setGridLineVisible(self._show_grid)
        if self._axis_y:
            self._axis_y.setGridLineVisible(self._show_grid)
    
    def _toggle_auto_scale(self, state: int):
        """Toggle auto scale."""
        self._auto_scale = state == Qt.Checked
        if self._auto_scale:
            self._auto_scale_axes()
    
    def export_chart_to_image(self):
        """Export the chart to an image file."""
        if not self._chart_view:
            return
        
        from PySide6.QtWidgets import QFileDialog
        from PySide6.QtGui import QPixmap
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Export Chart to Image", 
            "", 
            "PNG Files (*.png);;JPEG Files (*.jpg *.jpeg);;All Files (*)"
        )
        
        if file_path:
            try:
                # Render chart to pixmap
                pixmap = self._chart_view.grab()
                pixmap.save(file_path)
            except Exception as e:
                print(f"Error exporting chart: {e}")
    
    def clear(self):
        """Clear all measurements from the comparison view."""
        self._clear_chart_series()
        self._clear_measurement_selection_ui()
        self._measurement_layout.addWidget(self._no_measurements_label)
        self._update_info_label()
        self.measurements_updated.emit([])
    
    def refresh(self):
        """Refresh the comparison view."""
        if self._measurement_service:
            measurements = self._measurement_service.measurements
            self.update_measurements(measurements)
    
    @property
    def series(self) -> Optional['ImageSeries']:
        """Get the current series."""
        return self._series
    
    @series.setter
    def series(self, series: Optional['ImageSeries']):
        """Set the current series."""
        self._series = series
        # Refresh measurements for this series
        if self._measurement_service and series:
            measurements = self._measurement_service.get_measurements_for_series(series.series_uid)
            self.update_measurements(measurements)
        else:
            self.clear()
    
    @property
    def measurement_service(self) -> Optional['MeasurementService']:
        """Get the measurement service."""
        return self._measurement_service
    
    @measurement_service.setter
    def measurement_service(self, service: 'MeasurementService'):
        """Set the measurement service."""
        self._measurement_service = service