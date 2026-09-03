#!/usr/bin/env python3
"""
Series-Aware Volume View for DICOM Data Extraction Helper.

This module provides a series-aware wrapper for volume viewing functionality.
It demonstrates how to adapt the existing complex VolumeView to work with
ImageSeries objects while maintaining backward compatibility.
"""

from typing import Optional, Dict, Any, List, Tuple, TYPE_CHECKING
import numpy as np

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGroupBox, QHBoxLayout, QPushButton, QSpinBox, QCheckBox
from PySide6.QtCore import Signal

if TYPE_CHECKING:
    from models.image_series import ImageSeries, ImageSlice
    from services.measurement_service import MeasurementService
    from models.measurement import Measurement

from .base import SeriesViewerWidget


class SeriesVolumeView(SeriesViewerWidget):
    """
    Series-aware volume viewer widget.
    
    This widget displays 3D volume data from an ImageSeries and provides
    basic volume viewing functionality with slice navigation.
    
    For more advanced 3D visualization, this can be extended to integrate
    with VisPy or other 3D rendering libraries.
    
    Features:
    - Displays current slice from the series
    - Shows volume information
    - Supports slice navigation
    - Can be extended for full 3D rendering
    
    Signals:
    - Inherits signals from SeriesViewerWidget
    - volume_info_updated: Emitted when volume information is updated
    """
    
    # Signals
    volume_info_updated = Signal(str)
    volume_measurement_captured = Signal(str)  # measurement_id
    multi_slice_measurement_captured = Signal(str)  # measurement_id
    
    def __init__(self, parent=None, measurement_service: Optional['MeasurementService'] = None):
        """Initialize the series volume viewer."""
        # Call parent with call_setup_widget=False to avoid double setup
        super().__init__(parent, call_setup_widget=False)
        
        # Measurement service integration
        self._measurement_service = measurement_service
        
        # Additional state
        self._volume_info_label = None
        self._slice_info_label = None
        
        # 3D measurement state
        self._3d_measurement_mode = False
        self._cube_size = 3  # Size of 3D cube for measurements
        self._through_all_slices = False  # Whether to measure through all slices
        self._measurement_z_range = (0, 0)  # Z range for measurements
        
        # Setup UI
        self._setup_ui()
    
    def _setup_widget(self):
        """Setup the widget appearance (called by parent if call_setup_widget=True)."""
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Volume information label
        self._volume_info_label = QLabel("No volume data", self)
        self._volume_info_label.setStyleSheet("color: #e0e0e0; font-weight: bold;")
        layout.addWidget(self._volume_info_label)
        
        # Slice information label
        self._slice_info_label = QLabel("No slice data", self)
        self._slice_info_label.setStyleSheet("color: #e0e0e0;")
        layout.addWidget(self._slice_info_label)
        
        # Placeholder for actual volume rendering
        # This would be replaced with a proper 3D viewer in production
        self._placeholder_label = QLabel("3D Volume Viewer - Series Aware", self)
        self._placeholder_label.setStyleSheet(
            "color: #666; "
            "background-color: #2b2b2b; "
            "border: 1px dashed #444; "
            "qproperty-alignment: AlignCenter;"
        )
        self._placeholder_label.setMinimumSize(200, 200)
        layout.addWidget(self._placeholder_label, 1)
        
        # 3D measurement controls
        self._create_3d_measurement_controls(layout)
    
    def _on_series_changed(self):
        """Called when series is set - update volume information."""
        self._update_volume_info()
        self._update_z_range_controls()
    
    def _on_slice_changed(self):
        """Called when current slice changes - update slice information."""
        self._update_slice_info()
    
    def _create_3d_measurement_controls(self, layout):
        """Create 3D measurement controls."""
        # 3D measurement controls group
        measurement_group = QGroupBox("3D Measurements", self)
        measurement_layout = QHBoxLayout(measurement_group)
        measurement_layout.setContentsMargins(4, 4, 4, 4)
        measurement_layout.setSpacing(8)
        
        # 3D measurement mode toggle
        self._3d_measurement_checkbox = QCheckBox("3D Mode", self)
        self._3d_measurement_checkbox.setChecked(False)
        self._3d_measurement_checkbox.setToolTip("Enable 3D measurement mode")
        self._3d_measurement_checkbox.stateChanged.connect(self._on_3d_measurement_mode_changed)
        measurement_layout.addWidget(self._3d_measurement_checkbox)
        
        # Cube size for 3D measurements
        measurement_layout.addWidget(QLabel("Cube Size:", self))
        self._cube_size_spin = QSpinBox(self)
        self._cube_size_spin.setRange(1, 20)
        self._cube_size_spin.setValue(3)
        self._cube_size_spin.setToolTip("Size of 3D cube for measurements")
        self._cube_size_spin.valueChanged.connect(self._on_cube_size_changed)
        measurement_layout.addWidget(self._cube_size_spin)
        
        # Through all slices toggle
        self._through_all_slices_checkbox = QCheckBox("All Slices", self)
        self._through_all_slices_checkbox.setChecked(False)
        self._through_all_slices_checkbox.setToolTip("Measure through all slices at current XY position")
        self._through_all_slices_checkbox.stateChanged.connect(self._on_through_all_slices_changed)
        measurement_layout.addWidget(self._through_all_slices_checkbox)
        
        # Z range controls for multi-slice measurements
        measurement_layout.addWidget(QLabel("Z Range:", self))
        self._z_start_spin = QSpinBox(self)
        self._z_start_spin.setRange(0, 0)  # Will be updated based on series
        self._z_start_spin.setValue(0)
        self._z_start_spin.setToolTip("Start Z index for measurement")
        measurement_layout.addWidget(self._z_start_spin)
        
        measurement_layout.addWidget(QLabel("to", self))
        self._z_end_spin = QSpinBox(self)
        self._z_end_spin.setRange(0, 0)  # Will be updated based on series
        self._z_end_spin.setValue(0)
        self._z_end_spin.setToolTip("End Z index for measurement")
        measurement_layout.addWidget(self._z_end_spin)
        
        # Capture 3D measurement button
        self._capture_3d_button = QPushButton("Capture 3D", self)
        self._capture_3d_button.setEnabled(False)
        self._capture_3d_button.setToolTip("Capture 3D measurement")
        self._capture_3d_button.clicked.connect(self._on_capture_3d_clicked)
        measurement_layout.addWidget(self._capture_3d_button)
        
        # 3D volume statistics button
        self._volume_stats_button = QPushButton("Volume Stats", self)
        self._volume_stats_button.setEnabled(False)
        self._volume_stats_button.setToolTip("Calculate volume statistics")
        self._volume_stats_button.clicked.connect(self._on_volume_stats_clicked)
        measurement_layout.addWidget(self._volume_stats_button)
        
        layout.addWidget(measurement_group)
    
    def _update_volume_info(self):
        """Update volume information display."""
        if not self.has_series:
            self._volume_info_label.setText("No volume data")
            self._update_slice_info()
            return
        
        series = self.series
        
        info_parts = []
        info_parts.append(f"Series: {series.series_description or series.series_uid}")
        info_parts.append(f"Shape: {series.shape}")
        info_parts.append(f"Slices: {series.num_slices}")
        
        if series.num_slices > 0:
            volume = series.volume
            if volume.size > 0:
                info_parts.append(f"Volume size: {volume.size:,} voxels")
                info_parts.append(f"Volume mean: {np.mean(volume):.2f}")
                info_parts.append(f"Volume range: [{np.min(volume):.1f}, {np.max(volume):.1f}]")
        
        self._volume_info_label.setText(" | ".join(info_parts))
        self._update_slice_info()
        
        # Emit signal with volume info
        self.volume_info_updated.emit(self._volume_info_label.text())
    
    def _update_slice_info(self):
        """Update slice information display."""
        if not self.has_series:
            self._slice_info_label.setText("No slice data")
            return
        
        slice_obj = self.current_slice_object
        if slice_obj is None:
            self._slice_info_label.setText("No current slice")
            return
        
        info_parts = []
        info_parts.append(f"Current slice: {self.current_slice + 1}/{self.num_slices}")
        
        if slice_obj.pixel_array is not None:
            pixel_array = slice_obj.pixel_array
            info_parts.append(f"Slice shape: {pixel_array.shape}")
            info_parts.append(f"Z position: {slice_obj.z_position:.2f}")
            info_parts.append(f"Slice mean: {np.mean(pixel_array):.2f}")
            info_parts.append(f"Slice range: [{np.min(pixel_array):.1f}, {np.max(pixel_array):.1f}]")
        
        self._slice_info_label.setText(" | ".join(info_parts))
    
    def _update_z_range_controls(self):
        """Update Z range controls based on current series."""
        if not self.has_series:
            self._z_start_spin.setRange(0, 0)
            self._z_end_spin.setRange(0, 0)
            self._z_start_spin.setValue(0)
            self._z_end_spin.setValue(0)
            self._capture_3d_button.setEnabled(False)
            self._volume_stats_button.setEnabled(False)
            return

        num_slices = self.num_slices
        if num_slices <= 0:
            self._z_start_spin.setRange(0, 0)
            self._z_end_spin.setRange(0, 0)
            self._z_start_spin.setValue(0)
            self._z_end_spin.setValue(0)
            self._capture_3d_button.setEnabled(False)
            self._volume_stats_button.setEnabled(False)
            return

        # Set ranges for Z spin boxes
        self._z_start_spin.setRange(0, num_slices - 1)
        self._z_end_spin.setRange(0, num_slices - 1)

        # Set default values - full range
        self._z_start_spin.setValue(0)
        self._z_end_spin.setValue(num_slices - 1)

        # Update measurement z range
        self._measurement_z_range = (0, num_slices - 1)

        # Enable buttons if we have data
        self._capture_3d_button.setEnabled(True)
        self._volume_stats_button.setEnabled(True)

    def _on_3d_measurement_mode_changed(self, state):
        """Handle 3D measurement mode toggle."""
        self._3d_measurement_mode = state == 2  # Qt.Checked is 2
        # Enable/disable related controls based on mode
        self._cube_size_spin.setEnabled(self._3d_measurement_mode)
        self._through_all_slices_checkbox.setEnabled(self._3d_measurement_mode)
        self._z_start_spin.setEnabled(self._3d_measurement_mode)
        self._z_end_spin.setEnabled(self._3d_measurement_mode)

    def _on_cube_size_changed(self, value):
        """Handle cube size changes."""
        self._cube_size = value

    def _on_through_all_slices_changed(self, state):
        """Handle through all slices toggle."""
        self._through_all_slices = state == 2  # Qt.Checked is 2

    def _on_capture_3d_clicked(self):
        """Handle 3D measurement capture."""
        if not self.has_series or not self._measurement_service:
            return

        series = self.series
        volume = self.get_volume_array()
        if volume is None:
            return

        # Get current cursor position - for now use center of slice
        current_slice = self.current_slice_object
        if current_slice is None or current_slice.pixel_array is None:
            return

        # Use center position by default
        height, width = current_slice.pixel_array.shape
        center_x, center_y = width // 2, height // 2

        # Get Z range
        z_start = self._z_start_spin.value()
        z_end = self._z_end_spin.value()
        z_range = range(z_start, z_end + 1)

        # Create 3D measurement
        measurement = self._create_3d_cube_measurement(
            series=series,
            x=center_x,
            y=center_y,
            z_range=z_range,
            cube_size=self._cube_size,
            through_all_slices=self._through_all_slices
        )

        if measurement:
            self.volume_measurement_captured.emit(measurement.measurement_id)

    def _on_volume_stats_clicked(self):
        """Handle volume statistics calculation."""
        if not self.has_series:
            return

        stats = self.get_volume_statistics()
        if not stats:
            return

        # Create a volume statistics measurement
        if self._measurement_service:
            series = self.series
            # Use center position for the measurement
            current_slice = self.current_slice_object
            if current_slice and current_slice.pixel_array is not None:
                height, width = current_slice.pixel_array.shape
                center_x, center_y = width // 2, height // 2

                measurement = self._create_volume_statistics_measurement(
                    series=series,
                    stats=stats,
                    x=center_x,
                    y=center_y
                )

                if measurement:
                    self.volume_measurement_captured.emit(measurement.measurement_id)

    def _create_3d_cube_measurement(self, series: 'ImageSeries', x: int, y: int,
                                    z_range: range, cube_size: int = 3,
                                    through_all_slices: bool = False) -> Optional['Measurement']:
        """Create a 3D cube measurement across multiple slices."""
        if not self._measurement_service:
            return None

        volume = self.get_volume_array()
        if volume is None:
            return None

        # Get metadata from first slice for HU conversion
        first_slice = series.get_slice(0)
        if first_slice is None:
            return None

        slope = first_slice.metadata.get('RescaleSlope', 1.0)
        intercept = first_slice.metadata.get('RescaleIntercept', 0.0)

        # Extract 3D cube data
        cube_data, valid_z_indices = self._extract_3d_cube(
            volume, x, y, z_range, cube_size, through_all_slices
        )

        if cube_data is None or cube_data.size == 0:
            return None

        # Calculate statistics for the cube
        cube_stats = self._calculate_3d_cube_statistics(
            cube_data, series, valid_z_indices, x, y, slope, intercept
        )

        # Create measurement using the measurement service
        # We'll create a multi-slice ROI measurement
        measurement = self._measurement_service.create_roi_measurement(
            series=series,
            slice_index=valid_z_indices[0] if valid_z_indices else 0,
            x=x, y=y,
            size=cube_size,
            roi_form='cube_3d',
            name=f'3D Cube ({cube_size}x{cube_size}x{len(valid_z_indices)})',
            slope=slope,
            intercept=intercept
        )

        if measurement:
            # Update measurement with 3D-specific statistics
            measurement.statistics.update(cube_stats)
            measurement.metadata.update({
                'measurement_type': '3d_cube',
                'z_range': list(z_range),
                'valid_z_indices': list(valid_z_indices),
                'cube_size': cube_size,
                'through_all_slices': through_all_slices,
                'voxel_count': int(cube_data.size)
            })

        return measurement

    def _create_volume_statistics_measurement(self, series: 'ImageSeries', 
                                              stats: Dict[str, float],
                                              x: int, y: int) -> Optional['Measurement']:
        """Create a volume statistics measurement."""
        if not self._measurement_service:
            return None

        current_slice = series.get_slice(self.current_slice)
        if current_slice is None:
            return None

        slope = current_slice.metadata.get('RescaleSlope', 1.0)
        intercept = current_slice.metadata.get('RescaleIntercept', 0.0)

        # Create measurement
        measurement = self._measurement_service.create_roi_measurement(
            series=series,
            slice_index=self.current_slice,
            x=x, y=y,
            size=1,  # Point measurement for volume stats
            roi_form='volume_stats',
            name='Volume Statistics',
            slope=slope,
            intercept=intercept
        )

        if measurement:
            # Update with volume statistics
            hu_stats = {
                'hu_mean': stats['mean'] * slope + intercept,
                'hu_std': stats['std'] * slope,
                'hu_min': stats['min'] * slope + intercept,
                'hu_max': stats['max'] * slope + intercept,
                'hu_sum': stats['sum'] * slope + intercept * stats['voxels']
            }
            measurement.statistics.update(stats)
            measurement.statistics.update(hu_stats)
            measurement.metadata.update({
                'measurement_type': 'volume_statistics',
                'volume_voxels': stats['voxels'],
                'volume_size': f"{series.shape[0]}x{series.shape[1]}x{series.shape[2]}"
            })
            measurement.value = hu_stats['hu_mean']

        return measurement

    def _extract_3d_cube(self, volume: np.ndarray, x: int, y: int, z_range: range,
                        cube_size: int, through_all_slices: bool) -> Tuple[Optional[np.ndarray], List[int]]:
        """Extract a 3D cube from the volume."""
        try:
            if volume.ndim != 3:
                return None, []

            depth, height, width = volume.shape
            half_size = cube_size // 2

            # Calculate X and Y bounds
            x_start = max(0, x - half_size)
            x_end = min(width, x + half_size + (1 if cube_size % 2 != 0 else 0))
            y_start = max(0, y - half_size)
            y_end = min(height, y + half_size + (1 if cube_size % 2 != 0 else 0))

            if x_end <= x_start or y_end <= y_start:
                return None, []

            # Get valid Z indices
            if through_all_slices:
                valid_z_indices = list(range(depth))
            else:
                valid_z_indices = [z for z in z_range if 0 <= z < depth]

            if not valid_z_indices:
                return None, []

            # Extract cube data
            cube_slices = []
            for z in valid_z_indices:
                slice_data = volume[z, y_start:y_end, x_start:x_end]
                cube_slices.append(slice_data)

            if not cube_slices:
                return None, []

            # Stack to create 3D cube
            cube_data = np.stack(cube_slices, axis=0)
            return cube_data, valid_z_indices

        except Exception as e:
            print(f"Error extracting 3D cube: {e}")
            return None, []

    def _calculate_3d_cube_statistics(self, cube_data: np.ndarray, series: 'ImageSeries',
                                      z_indices: List[int], x: int, y: int,
                                      slope: float, intercept: float) -> Dict[str, float]:
        """Calculate statistics for a 3D cube measurement."""
        try:
            raw_stats = {
                '3d_raw_mean': float(np.mean(cube_data)),
                '3d_raw_std': float(np.std(cube_data)),
                '3d_raw_min': float(np.min(cube_data)),
                '3d_raw_max': float(np.max(cube_data)),
                '3d_raw_sum': float(np.sum(cube_data)),
                '3d_raw_median': float(np.median(cube_data)),
                '3d_voxel_count': int(cube_data.size)
            }

            # Calculate HU statistics
            hu_stats = {
                '3d_hu_mean': raw_stats['3d_raw_mean'] * slope + intercept,
                '3d_hu_std': raw_stats['3d_raw_std'] * slope,
                '3d_hu_min': raw_stats['3d_raw_min'] * slope + intercept,
                '3d_hu_max': raw_stats['3d_raw_max'] * slope + intercept,
                '3d_hu_sum': raw_stats['3d_raw_sum'] * slope + intercept * raw_stats['3d_voxel_count'],
                '3d_hu_median': raw_stats['3d_raw_median'] * slope + intercept
            }

            return {**raw_stats, **hu_stats}

        except Exception as e:
            print(f"Error calculating 3D cube statistics: {e}")
            return {}

    def get_volume_array(self) -> Optional[np.ndarray]:
        """
        Get the current volume as a numpy array.
        
        Returns:
            3D numpy array (z, y, x) or None if no series loaded
        """
        if not self.has_series:
            return None
        
        return self.series.volume
    
    def get_current_slice_array(self) -> Optional[np.ndarray]:
        """
        Get the current slice as a numpy array.
        
        Returns:
            2D numpy array or None if no slice available
        """
        slice_obj = self.current_slice_object
        if slice_obj is None:
            return None
        
        return slice_obj.pixel_array
    
    def get_volume_statistics(self) -> Dict[str, float]:
        """
        Get statistics for the entire volume.
        
        Returns:
            Dictionary with volume statistics
        """
        volume = self.get_volume_array()
        if volume is None or volume.size == 0:
            return {
                'mean': 0.0, 'std': 0.0, 'min': 0.0, 'max': 0.0,
                'sum': 0.0, 'voxels': 0
            }
        
        return {
            'mean': float(np.mean(volume)),
            'std': float(np.std(volume)),
            'min': float(np.min(volume)),
            'max': float(np.max(volume)),
            'sum': float(np.sum(volume)),
            'voxels': int(volume.size)
        }
    
    def get_slice_spacing_info(self) -> Dict[str, Any]:
        """
        Get information about slice spacing.
        
        Returns:
            Dictionary with slice spacing information
        """
        if not self.has_series:
            return {'z_positions': [], 'spacings': [], 'is_regular': False}
        
        z_positions = self.series.z_positions
        spacings = []
        
        for i in range(1, len(z_positions)):
            spacing = abs(z_positions[i] - z_positions[i-1])
            spacings.append(spacing)
        
        is_regular = len(set(spacings)) <= 1 if spacings else True
        
        return {
            'z_positions': z_positions,
            'spacings': spacings,
            'is_regular': is_regular,
            'mean_spacing': float(np.mean(spacings)) if spacings else 0.0,
            'std_spacing': float(np.std(spacings)) if spacings else 0.0
        }
    
    def next_slice(self):
        """Go to next slice and update display."""
        super().next_slice()
    
    def prev_slice(self):
        """Go to previous slice and update display."""
        super().prev_slice()
    
    def clear(self):
        """Clear the current series and volume data."""
        super().clear()
        self._volume_info_label.setText("No volume data")
        self._slice_info_label.setText("No slice data")
    
    def refresh(self):
        """Refresh the display."""
        self._update_volume_info()
        self._update_slice_info()


# For backward compatibility, create an alias if the original VolumeView exists
try:
    from gui.volume_view import SliceDisplayWidget, VolumeView as OriginalVolumeView
    VolumeView = SeriesVolumeView
    HAS_ORIGINAL_VOLUME_VIEW = True
except ImportError:
    VolumeView = SeriesVolumeView
    HAS_ORIGINAL_VOLUME_VIEW = False


__all__ = ['SeriesVolumeView', 'VolumeView']