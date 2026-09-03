#!/usr/bin/env python3
"""
Series-Aware Image Viewer for DICOM Data Extraction Helper.

This refactored version inherits from SeriesViewerWidget to work with
ImageSeries objects instead of individual QImage objects.
"""

from typing import Optional, List, TYPE_CHECKING, Dict, Any
import numpy as np

from PySide6.QtWidgets import (
    QWidget, QLabel, QCheckBox, QVBoxLayout, 
    QScrollArea, QSizePolicy, QHBoxLayout
)
from PySide6.QtGui import QImage, QPixmap, QPalette, QBrush, QColor, QPainter, QPen
from PySide6.QtCore import Qt, Signal, QPoint

try:
    from gui.utils.image_utils import apply_overlay_to_base
    HAS_IMAGE_UTILS = True
except ImportError:
    HAS_IMAGE_UTILS = False

if TYPE_CHECKING:
    from models.image_series import ImageSeries, ImageSlice
    from services.measurement_service import MeasurementService
    from models.measurement import Measurement

from .base import SeriesViewerWidget


class SeriesImageViewer(SeriesViewerWidget):
    """
    Series-aware image viewer widget.
    
    This widget displays DICOM images from an ImageSeries with optional overlay support.
    It inherits from SeriesViewerWidget to provide series navigation functionality.
    
    Features:
    - Displays image at original size (no scaling initially)
    - Optional overlay display with toggle
    - Scroll area for large images
    - Centered display for small images
    - Inherits series navigation from SeriesViewerWidget
    
    Signals:
    - Inherits signals from SeriesViewerWidget
    - overlay_toggled: Emitted when overlay visibility changes
    """
    
    # Additional signals
    overlay_toggled = Signal(bool)
    measurement_selected = Signal(str)  # measurement_id
    cursor_moved = Signal(int, int)  # x, y
    
    def __init__(self, parent=None, measurement_service: Optional['MeasurementService'] = None):
        """Initialize the series image viewer."""
        # Call parent with call_setup_widget=False to avoid double setup
        super().__init__(parent, call_setup_widget=False)
        
        # Additional state for image display
        self._base_image: Optional[QImage] = None
        self._overlay_image: Optional[QImage] = None
        self._show_overlay: bool = True
        
        # Measurement overlay state
        self._measurement_overlay: Optional[QImage] = None
        self._show_measurement_overlay: bool = True
        self._cursor_x: int = 0
        self._cursor_y: int = 0
        self._cursor_size: int = 3
        self._roi_form: str = 'square'
        self._measurement_mode_enabled: bool = False
        self._highlighted_measurement_id: Optional[str] = None
        
        # Measurement service integration
        self._measurement_service = measurement_service
        
        # List of measurements to display
        self._displayed_measurements: List['Measurement'] = []
        
        # Setup UI
        self._setup_ui()
        
        # Make scroll area viewport accept focus for wheel events
        self._scroll_area.viewport().setFocusPolicy(Qt.StrongFocus)
        
        # Default background
        self._update_display()
    
    def _setup_widget(self):
        """Setup the widget appearance (called by parent if call_setup_widget=True)."""
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the widget layout."""
        # Main layout
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        
        # Scroll area for image
        self._scroll_area = QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Image label container
        self._image_container = QWidget()
        self._image_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._image_container_layout = QVBoxLayout(self._image_container)
        self._image_container_layout.setContentsMargins(0, 0, 0, 0)
        
        # Image label
        self._image_label = QLabel(self._image_container)
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._image_label.setMinimumSize(1, 1)
        
        # Set a neutral background for the image area
        palette = self._image_label.palette()
        palette.setColor(QPalette.Window, QColor(50, 50, 50))
        self._image_label.setPalette(palette)
        self._image_label.setAutoFillBackground(True)
        
        self._image_container_layout.addWidget(self._image_label, 1)
        self._scroll_area.setWidget(self._image_container)
        
        # Overlay toggle checkbox
        self._overlay_checkbox = QCheckBox("Show Overlay", self)
        self._overlay_checkbox.setChecked(True)
        self._overlay_checkbox.stateChanged.connect(self._on_overlay_toggle)
        
        # Measurement controls panel
        self._measurement_controls = QHBoxLayout()
        self._measurement_controls.setSpacing(8)
        self._measurement_controls.setContentsMargins(0, 0, 0, 0)
        
        # Measurement mode toggle
        self._measurement_mode_checkbox = QCheckBox("Measurement", self)
        self._measurement_mode_checkbox.setChecked(False)
        self._measurement_mode_checkbox.stateChanged.connect(self._on_measurement_mode_changed)
        self._measurement_controls.addWidget(self._measurement_mode_checkbox)
        
        # Show measurements toggle
        self._show_measurements_checkbox = QCheckBox("Show Measurements", self)
        self._show_measurements_checkbox.setChecked(True)
        self._show_measurements_checkbox.stateChanged.connect(self._on_show_measurements_changed)
        self._measurement_controls.addWidget(self._show_measurements_checkbox)
        
        self._measurement_controls.addStretch(1)
        
        # Control panel for both overlays and measurements
        control_panel = QHBoxLayout()
        control_panel.setSpacing(8)
        control_panel.setContentsMargins(0, 0, 0, 0)
        
        control_panel.addWidget(self._overlay_checkbox)
        control_panel.addLayout(self._measurement_controls)
        control_panel.addStretch(1)
        
        # Add widgets to layout
        self._layout.addWidget(self._scroll_area, 1)
        self._layout.addLayout(control_panel)
    
    def _on_series_changed(self):
        """Called when series is set - update display."""
        # Update base image from current slice
        if self.current_slice_object:
            self.set_base_image_from_slice(self.current_slice_object)
        else:
            self._base_image = None
        
        self._generate_measurement_overlay()
        self._update_display()
    
    def _on_slice_changed(self):
        """Called when current slice changes - update display."""
        # Update base image from new current slice
        if self.current_slice_object:
            self.set_base_image_from_slice(self.current_slice_object)
        else:
            self._base_image = None
        
        self._update_display()
    
    def set_image(self, image: QImage):
        """
        Set the base image to display.
        
        Args:
            image: QImage to display at original size
        """
        self._base_image = image
        self._update_display()
    
    def set_overlay(self, overlay: Optional[QImage]):
        """
        Set the overlay image.
        
        Args:
            overlay: QImage overlay, or None to remove
        """
        self._overlay_image = overlay
        self._overlay_checkbox.setEnabled(overlay is not None)
        if overlay is None:
            self._overlay_checkbox.setChecked(False)
            self._show_overlay = False
        else:
            # Restore user's last preference; default to shown on first overlay
            self._overlay_checkbox.setChecked(self._show_overlay)
        self._update_display()
    
    def toggle_overlay(self, show: bool):
        """
        Programmatically toggle overlay visibility.
        
        Args:
            show: True to show overlay, False to hide
        """
        self._show_overlay = show
        self._overlay_checkbox.setChecked(show)
        self._update_display()
    
    def _on_overlay_toggle(self, state: int):
        """
        Handler for overlay checkbox state change.
        
        Args:
            state: Qt.CheckState (Checked or Unchecked)
        """
        self._show_overlay = (state == Qt.Checked.value)
        self._update_display()
        self.overlay_toggled.emit(self._show_overlay)
    
    def _update_display(self):
        """Update the displayed image based on current state."""
        if self._base_image is None:
            self._image_label.setPixmap(QPixmap())
            self._image_label.setText("No image loaded")
            return
        
        # Start with base image
        display_image = self._base_image.copy()
        
        # Apply regular overlay if enabled
        if self._show_overlay and self._overlay_image is not None:
            if HAS_IMAGE_UTILS:
                display_image = apply_overlay_to_base(display_image, self._overlay_image)
        
        # Apply measurement overlay if enabled
        if self._show_measurement_overlay and self._measurement_overlay is not None:
            # Create a composite image with measurements
            display_image = self._composite_with_measurements(display_image)
        
        # Convert to pixmap and display
        if display_image is not None:
            pixmap = QPixmap.fromImage(display_image)
            self._image_label.setPixmap(pixmap)
            self._image_label.setText("")
        else:
            self._image_label.setPixmap(QPixmap())
            self._image_label.setText("Error rendering image")
    
    def clear(self):
        """Clear the displayed image and overlay."""
        super().clear()
        self._base_image = None
        self._overlay_image = None
        self._show_overlay = True
        self._overlay_checkbox.setChecked(True)
        self._overlay_checkbox.setEnabled(False)
        self._update_display()
    
    # Backward compatibility methods
    def set_dataset(self, ds):
        """
        Set image from a pydicom dataset.
        
        This provides backward compatibility with the existing codebase.
        """
        try:
            from gui.utils.image_utils import dicom_to_qimage
            if hasattr(dicom_to_qimage, '__call__'):
                qimage = dicom_to_qimage(ds)
                self.set_image(qimage)
        except ImportError:
            print("Warning: dicom_to_qimage not available")
    
    def set_base_image_from_slice(self, slice_obj: Optional['ImageSlice']):
        """
        Set the base image from an ImageSlice object.
        
        This converts the slice's pixel array to a QImage for display.
        """
        if slice_obj is None or slice_obj.pixel_array is None:
            self._base_image = None
        else:
            try:
                # Convert numpy array to QImage
                pixel_array = slice_obj.pixel_array
                height, width = pixel_array.shape
                
                # Convert to 8-bit if needed for display
                if pixel_array.dtype != np.uint8:
                    # Normalize to 0-255 range for display
                    if pixel_array.max() > 255:
                        # Scale down for display
                        display_array = (pixel_array / pixel_array.max() * 255).astype(np.uint8)
                    else:
                        display_array = pixel_array.astype(np.uint8)
                else:
                    display_array = pixel_array
                
                # Create QImage from numpy array
                qimage = QImage(display_array.data, width, height, QImage.Format_Grayscale8)
                self._base_image = qimage
                
            except Exception as e:
                print(f"Error converting slice to QImage: {e}")
                self._base_image = None
        
        self._update_display()
    
    # Measurement-related methods
    def _on_measurement_mode_changed(self, state: int):
        """Handle measurement mode toggle."""
        self._measurement_mode_enabled = (state == Qt.Checked)
        self._update_display()
        if self._measurement_service:
            self._measurement_service.measurement_mode_enabled = self._measurement_mode_enabled
    
    def _on_show_measurements_changed(self, state: int):
        """Handle show measurements toggle."""
        self._show_measurement_overlay = (state == Qt.Checked)
        self._generate_measurement_overlay()
        self._update_display()
    
    def set_measurement_service(self, service: 'MeasurementService'):
        """Set the measurement service."""
        self._measurement_service = service
        if service:
            # Sync state with service
            self._measurement_mode_enabled = service.measurement_mode_enabled
            self._cursor_size = service.cursor_size
            self._roi_form = service.roi_form
            self._cursor_x, self._cursor_y = service.cursor_position
            self._measurement_mode_checkbox.setChecked(self._measurement_mode_enabled)
            self._update_display()
    
    def _generate_measurement_overlay(self):
        """Generate an overlay with current measurements."""
        if not self._base_image or not self.has_series:
            self._measurement_overlay = None
            return
        
        # Create a transparent overlay image
        width = self._base_image.width()
        height = self._base_image.height()
        overlay = QImage(width, height, QImage.Format_ARGB32)
        overlay.fill(Qt.transparent)
        
        # Create painter for overlay
        painter = QPainter(overlay)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Set up colors
        roi_color = QColor(0, 200, 255, 128)  # Semi-transparent blue
        center_color = QColor(0, 255, 0, 200)  # Bright green for center
        highlighted_color = QColor(255, 255, 0, 200)  # Yellow for highlighted measurement
        
        # Draw cursor position if measurement mode is enabled
        if self._measurement_mode_enabled and self._cursor_x > 0 and self._cursor_y > 0:
            self._draw_roi(painter, self._cursor_x, self._cursor_y, 
                         self._cursor_size, self._roi_form, 
                         center_color, roi_color, 2)
        
        # Draw all measurements for current slice
        if self.series:
            measurements = self._get_measurements_for_current_slice()
            for measurement in measurements:
                # Use different color for highlighted measurement
                is_highlighted = (measurement.measurement_id == self._highlighted_measurement_id)
                fill_color = highlighted_color if is_highlighted else QColor(255, 0, 0, 150)
                border_color = QColor(255, 0, 0) if is_highlighted else QColor(100, 100, 255)
                
                self._draw_measurement(painter, measurement, fill_color, border_color)
        
        painter.end()
        self._measurement_overlay = overlay
    
    def _draw_roi(self, painter: QPainter, x: int, y: int, size: int, form: str,
                 center_color: QColor, roi_color: QColor, line_width: int):
        """Draw an ROI at the specified position."""
        if form == 'square':
            half_size = size // 2
            min_x = max(0, x - half_size)
            max_x = min(self._base_image.width() - 1, x + half_size)
            min_y = max(0, y - half_size)
            max_y = min(self._base_image.height() - 1, y + half_size)
            
            # Draw filled rectangle
            painter.fillRect(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1, roi_color)
            
            # Draw border
            pen = QPen(center_color, line_width)
            painter.setPen(pen)
            painter.drawRect(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)
            
            # Draw center marker
            painter.fillRect(x - 1, y - 1, 3, 3, center_color)
            
        elif form == 'circle':
            radius = size / 2.0
            
            # Draw filled circle
            painter.setBrush(QBrush(roi_color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPoint(x, y), int(radius), int(radius))
            
            # Draw border
            pen = QPen(center_color, line_width)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPoint(x, y), int(radius), int(radius))
            
            # Draw center marker
            painter.fillRect(x - 1, y - 1, 3, 3, center_color)
            
        elif form == 'cross':
            half_size = size // 2
            
            # Draw horizontal line
            painter.setBrush(QBrush(roi_color))
            painter.setPen(Qt.NoPen)
            min_x = max(0, x - half_size)
            max_x = min(self._base_image.width() - 1, x + half_size)
            painter.drawRect(min_x, y - 1, max_x - min_x + 1, 3)
            
            # Draw vertical line
            min_y = max(0, y - half_size)
            max_y = min(self._base_image.height() - 1, y + half_size)
            painter.drawRect(x - 1, min_y, 3, max_y - min_y + 1)
            
            # Draw center marker
            painter.fillRect(x - 1, y - 1, 3, 3, center_color)
    
    def _draw_measurement(self, painter: QPainter, measurement: 'Measurement', 
                         fill_color: QColor, border_color: QColor):
        """Draw a measurement on the overlay."""
        x, y = measurement.x, measurement.y
        size = measurement.roi_size
        form = measurement.roi_form or 'square'
        
        # Use slightly smaller size for measurement display to avoid overlap
        display_size = max(1, size)
        
        if form == 'square':
            half_size = display_size // 2
            min_x = max(0, x - half_size)
            max_x = min(self._base_image.width() - 1, x + half_size)
            min_y = max(0, y - half_size)
            max_y = min(self._base_image.height() - 1, y + half_size)
            
            # Draw filled rectangle
            painter.fillRect(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1, fill_color)
            
            # Draw border
            pen = QPen(border_color, 1)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)
            
        elif form == 'circle':
            radius = display_size / 2.0
            
            # Draw filled circle
            painter.setBrush(QBrush(fill_color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPoint(x, y), int(radius), int(radius))
            
            # Draw border
            pen = QPen(border_color, 1)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPoint(x, y), int(radius), int(radius))
            
        elif form == 'cross':
            half_size = display_size // 2
            
            # Draw cross lines
            painter.setBrush(QBrush(fill_color))
            painter.setPen(Qt.NoPen)
            
            # Horizontal line
            min_x = max(0, x - half_size)
            max_x = min(self._base_image.width() - 1, x + half_size)
            painter.drawRect(min_x, y - 1, max_x - min_x + 1, 3)
            
            # Vertical line
            min_y = max(0, y - half_size)
            max_y = min(self._base_image.height() - 1, y + half_size)
            painter.drawRect(x - 1, min_y, 3, max_y - min_y + 1)
    
    def _get_measurements_for_current_slice(self) -> List['Measurement']:
        """Get measurements for the current slice."""
        if self._measurement_service and self.series:
            return self._measurement_service.get_measurements_for_slice(
                self.series.series_uid, self.current_slice
            )
        return []
    
    def _composite_with_measurements(self, base_image: QImage) -> QImage:
        """Composite the base image with measurement overlays."""
        if self._measurement_overlay is None:
            return base_image
        
        # Create a copy of the base image
        result = base_image.copy()
        
        # Paint measurement overlay onto base image
        painter = QPainter(result)
        painter.drawImage(0, 0, self._measurement_overlay)
        painter.end()
        
        return result
    
    def highlight_measurement(self, measurement: 'Measurement'):
        """Highlight a specific measurement."""
        self._highlighted_measurement_id = measurement.measurement_id
        self._generate_measurement_overlay()
        self._update_display()
    
    def clear_highlight(self):
        """Clear measurement highlighting."""
        self._highlighted_measurement_id = None
        self._generate_measurement_overlay()
        self._update_display()
    
    def refresh_overlays(self):
        """Refresh all overlays."""
        self._generate_measurement_overlay()
        self._update_display()
    
    def set_cursor_position(self, x: int, y: int):
        """Set the cursor position."""
        self._cursor_x = x
        self._cursor_y = y
        self.cursor_moved.emit(x, y)
        
        if self._measurement_mode_enabled:
            self._generate_measurement_overlay()
            self._update_display()
        
        if self._measurement_service:
            self._measurement_service.cursor_position = (x, y)
            self._measurement_service.current_slice_index = self.current_slice
    
    def set_measurement_mode(self, enabled: bool):
        """Set whether measurement mode is enabled."""
        self._measurement_mode_enabled = enabled
        self._measurement_mode_checkbox.setChecked(enabled)
        if enabled:
            self._generate_measurement_overlay()
        self._update_display()
        if self._measurement_service:
            self._measurement_service.measurement_mode_enabled = enabled
    
    def set_measurement_parameters(self, cursor_size: int, roi_form: str):
        """Set measurement parameters."""
        self._cursor_size = cursor_size
        self._roi_form = roi_form
        if self._measurement_mode_enabled:
            self._generate_measurement_overlay()
            self._update_display()
    
    def _on_slice_changed(self):
        """Called when current slice changes - update display."""
        self._generate_measurement_overlay()
        self._update_display()
    
    def keyPressEvent(self, event):
        """Handle key press events."""
        # Let the parent handle navigation keys
        super().keyPressEvent(event)


# For backward compatibility, create an alias
ImageViewer = SeriesImageViewer


# Keep the original imports available for backward compatibility
__all__ = ['SeriesImageViewer', 'ImageViewer']