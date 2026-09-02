#!/usr/bin/env python3
"""
Series-Aware Volume View for DICOM Data Extraction Helper.

This module provides a series-aware wrapper for volume viewing functionality.
It demonstrates how to adapt the existing complex VolumeView to work with
ImageSeries objects while maintaining backward compatibility.
"""

from typing import Optional, Dict, Any, TYPE_CHECKING
import numpy as np

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Signal

if TYPE_CHECKING:
    from models.image_series import ImageSeries, ImageSlice

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
    
    volume_info_updated = Signal(str)
    
    def __init__(self, parent=None):
        """Initialize the series volume viewer."""
        # Call parent with call_setup_widget=False to avoid double setup
        super().__init__(parent, call_setup_widget=False)
        
        # Additional state
        self._volume_info_label = None
        self._slice_info_label = None
        
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
    
    def _on_series_changed(self):
        """Called when series is set - update volume information."""
        self._update_volume_info()
    
    def _on_slice_changed(self):
        """Called when current slice changes - update slice information."""
        self._update_slice_info()
    
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