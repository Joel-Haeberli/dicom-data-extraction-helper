#!/usr/bin/env python3
"""
Series-Aware Image Viewer for DICOM Data Extraction Helper.

This refactored version inherits from SeriesViewerWidget to work with
ImageSeries objects instead of individual QImage objects.
"""

from typing import Optional, TYPE_CHECKING
import numpy as np

from PySide6.QtWidgets import (
    QWidget, QLabel, QCheckBox, QVBoxLayout, 
    QScrollArea, QSizePolicy
)
from PySide6.QtGui import QImage, QPixmap, QPalette, QBrush, QColor
from PySide6.QtCore import Qt, Signal

try:
    from gui.utils.image_utils import apply_overlay_to_base
    HAS_IMAGE_UTILS = True
except ImportError:
    HAS_IMAGE_UTILS = False

if TYPE_CHECKING:
    from models.image_series import ImageSeries, ImageSlice

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
    
    overlay_toggled = Signal(bool)
    
    def __init__(self, parent=None):
        """Initialize the series image viewer."""
        # Call parent with call_setup_widget=False to avoid double setup
        super().__init__(parent, call_setup_widget=False)
        
        # Additional state for image display
        self._base_image: Optional[QImage] = None
        self._overlay_image: Optional[QImage] = None
        self._show_overlay: bool = True
        
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
        
        # Add widgets to layout
        self._layout.addWidget(self._scroll_area, 1)
        self._layout.addWidget(self._overlay_checkbox, 0, Qt.AlignRight)
    
    def _on_series_changed(self):
        """Called when series is set - update display."""
        self._update_display()
    
    def _on_slice_changed(self):
        """Called when current slice changes - update display."""
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
        
        # Determine which image to display
        if self._show_overlay and self._overlay_image is not None:
            # Composite base + overlay
            if HAS_IMAGE_UTILS:
                display_image = apply_overlay_to_base(self._base_image, self._overlay_image)
            else:
                display_image = self._base_image
        else:
            # Just base image
            display_image = self._base_image
        
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


# For backward compatibility, create an alias
ImageViewer = SeriesImageViewer


# Keep the original imports available for backward compatibility
__all__ = ['SeriesImageViewer', 'ImageViewer']