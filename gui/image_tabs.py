#!/usr/bin/env python3
"""
Image Tabs Widget for GUI Application

Combines image viewer and pixel array table in a tabbed interface.
Only loads pixel data when the Pixel Data tab is selected.
"""

from typing import Optional

from PySide6.QtWidgets import QTabWidget, QWidget, QVBoxLayout
from PySide6.QtCore import Qt

from gui.pixel_array_table import PixelArrayTable


class ImageTabs(QTabWidget):
    """
    Tab widget containing pixel array table.
    
    Tabs:
    - "Pixel Data": Shows the pixel array table with external image viewer
    
    Note: Image viewing is handled by the external window opened by PixelArrayTable
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Create pixel data tab
        self._pixel_tab = QWidget(self)
        
        # Create pixel array table (which opens external image viewer)
        self._pixel_array_table = PixelArrayTable(self._pixel_tab)
        
        # Layout for pixel tab
        pixel_layout = QVBoxLayout(self._pixel_tab)
        pixel_layout.setContentsMargins(0, 0, 0, 0)
        pixel_layout.addWidget(self._pixel_array_table, 1)
        
        # Add tab (only Pixel Data tab remains)
        self.addTab(self._pixel_tab, "Pixel Data")
        
        # State
        self._dataset_pending: Optional = None
    
    @property
    def pixel_array_table(self):
        """Access the pixel array table widget."""
        return self._pixel_array_table

    def create_image_viewer(self):
        """Create and return the image viewer widget (delegates to PixelArrayTable)."""
        return self._pixel_array_table.create_image_viewer()
    
    def set_dataset(self, ds):
        """
        Set the DICOM dataset for the pixel data tab.
        The PixelArrayTable will open its own external image viewer.
        
        Args:
            ds: pydicom Dataset
        """
        self._dataset_pending = ds
        # Always load pixel data - external image viewer opens automatically
        self._pixel_array_table.set_dataset(ds)
    
    def set_overlay(self, overlay_qimage):
        """
        Set overlay for the external image viewer.
        
        Args:
            overlay_qimage: QImage with overlay, or None
        """
        # Pass overlay to the pixel array table's external image viewer if available
        if hasattr(self._pixel_array_table, 'set_viewer_overlay'):
            self._pixel_array_table.set_viewer_overlay(overlay_qimage)
    
    def toggle_overlay(self, show: bool):
        """
        Toggle overlay visibility in the external image viewer.
        
        Args:
            show: True to show overlay, False to hide
        """
        if hasattr(self._pixel_array_table, '_image_viewer') and self._pixel_array_table._image_viewer is not None:
            self._pixel_array_table._image_viewer.toggle_overlay(show)
    
    def clear(self):
        """Clear the pixel data tab."""
        self._pixel_array_table.clear()
        self._dataset_pending = None
    
    def _on_tab_changed(self, index: int):
        """
        Handler for tab change.
        Not used anymore (only one tab), but kept for compatibility.
        
        Args:
            index: New current tab index
        """
        pass
