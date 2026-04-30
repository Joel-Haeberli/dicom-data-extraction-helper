#!/usr/bin/env python3
"""
Image Viewer Widget for GUI Application

Displays DICOM images with optional overlay and toggle control.
Preserves original image size.
"""

from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QLabel, QCheckBox, QVBoxLayout, 
    QScrollArea, QSizePolicy
)
from PySide6.QtGui import QImage, QPixmap, QPalette, QBrush, QColor
from PySide6.QtCore import Qt, Signal

from gui.utils.image_utils import apply_overlay_to_base


class ImageViewer(QWidget):
    """
    Widget for displaying DICOM images with overlay support.
    
    Features:
    - Displays image at original size (no scaling initially)
    - Optional overlay display with toggle
    - Scroll area for large images
    - Centered display for small images
    """
    
    overlay_toggled = Signal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # State
        self._base_image: Optional[QImage] = None
        self._overlay_image: Optional[QImage] = None
        self._show_overlay: bool = True
        
        # Setup UI
        self._setup_ui()
        
        # Make scroll area viewport accept focus for wheel events
        self._scroll_area.viewport().setFocusPolicy(Qt.StrongFocus)
        
        # Default background
        self._update_display()
    
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
            # When overlay is set, show it by default
            self._overlay_checkbox.setChecked(True)
            self._show_overlay = True
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
            display_image = apply_overlay_to_base(self._base_image, self._overlay_image)
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
        self._base_image = None
        self._overlay_image = None
        self._show_overlay = True
        self._overlay_checkbox.setChecked(True)
        self._overlay_checkbox.setEnabled(False)
        self._update_display()
