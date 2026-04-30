#!/usr/bin/env python3
"""
Pixel Array Table Widget for GUI Application

Displays DICOM pixel array data in a scrollable table with windowing.
Opens a separate image viewer window for navigation with 7x7 window tracking.
"""

from typing import Optional, List, Any
import numpy as np

from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QHBoxLayout, 
    QWidget, QLabel, QVBoxLayout, QTableView, QSpinBox, QTabWidget,
    QScrollArea, QSizePolicy, QFrame, QCheckBox, QPushButton, QColorDialog
)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal, QObject
from PySide6.QtGui import QColor, QImage, QPixmap, QPalette, QBrush, QPainter

try:
    import pydicom
    from pydicom.dataset import Dataset
    HAS_PYDICOM = True
except ImportError:
    HAS_PYDICOM = False

try:
    from gui.utils.image_utils import dicom_to_qimage
    HAS_IMAGE_UTILS = True
except ImportError:
    HAS_IMAGE_UTILS = False


class PixelArrayModel(QAbstractTableModel):
    """
    Custom table model for pixel array data with lazy loading and windowing.
    
    This allows efficient display of a window of pixel array without pre-creating
    all table items. Only loads the specified window region.
    """
    
    def __init__(self, pixel_array: np.ndarray, show_hu: bool = False, 
                 slope: float = 1.0, intercept: float = 0.0, parent=None):
        super().__init__(parent)
        self._pixel_array = pixel_array
        self._show_hu = show_hu
        self._slope = slope
        self._intercept = intercept
        # Window settings (_default to full array if not set)
        self._window_x = 0
        self._window_y = 0
        self._window_width = 0  # 0 means use full width
        self._window_height = 0  # 0 means use full height
        # Highlight settings for statistics region (circle or rectangle)
        self._highlight_circle = False  # False = rectangle (all cells), True = circle
        self._circle_diameter = 0  # Diameter of circle in cells
        self._circle_center_x = 0  # Center X within window (0-indexed)
        self._circle_center_y = 0  # Center Y within window (0-indexed)
        self._highlight_window_rows = 0  # Current window rows for highlighting
        self._highlight_window_cols = 0  # Current window cols for highlighting
    
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        if self._pixel_array is None:
            return 0
        # For 3D arrays, use first frame
        arr = self._pixel_array[0] if self._pixel_array.ndim == 3 else self._pixel_array
        
        # Apply windowing
        if self._window_height > 0:
            # Limited by window
            start_row = self._window_y
            end_row = min(start_row + self._window_height, arr.shape[0])
            return end_row - start_row
        else:
            # Full height
            return arr.shape[0] if arr.ndim >= 2 else 0
    
    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        if self._pixel_array is None:
            return 0
        # For 3D arrays, use first frame
        arr = self._pixel_array[0] if self._pixel_array.ndim == 3 else self._pixel_array
        
        # Apply windowing
        if self._window_width > 0:
            # Limited by window
            start_col = self._window_x
            end_col = min(start_col + self._window_width, arr.shape[1])
            return end_col - start_col
        else:
            # Full width
            return arr.shape[1] if arr.ndim >= 2 else (1 if arr.size > 0 else 0)
    
    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        
        row = index.row()
        col = index.column()
        
        # For 3D arrays, use first frame
        arr = self._pixel_array[0] if self._pixel_array.ndim == 3 else self._pixel_array
        
        # Calculate actual array position considering window
        actual_row = self._window_y + row
        actual_col = self._window_x + col
        
        if role == Qt.DisplayRole:
            if actual_row < arr.shape[0] and actual_col < arr.shape[1]:
                value = arr[actual_row, actual_col]
                
                # Apply HU conversion if requested
                if self._show_hu and (self._slope != 1 or self._intercept != 0):
                    value = float(value) * self._slope + self._intercept
                
                # Format value
                if isinstance(value, (float, np.floating)):
                    return f"{value:8.2f}"
                else:
                    return str(int(value))
        
        elif role == Qt.BackgroundRole:
            # Highlight cells used for statistics calculation
            if (actual_row < arr.shape[0] and actual_col < arr.shape[1] and
                self._pixel_array is not None):
                # Check if this cell is within the statistics region
                if self._highlight_circle and self._circle_diameter > 0:
                    # Circle mode: check if cell is within circle
                    # col, row are relative to window (0 to window_width-1, 0 to window_height-1)
                    dx = col - self._circle_center_x
                    dy = row - self._circle_center_y
                    radius = self._circle_diameter / 2
                    if dx * dx + dy * dy <= radius * radius:
                        # Cell is inside circle
                        return QBrush(QColor(200, 230, 201))  # Light green
                else:
                    # Rectangle mode: all cells in window are used
                    return QBrush(QColor(200, 230, 201))  # Light green
        
        return None
    
    def set_highlight_region(self, is_circle: bool, diameter: int = 0, 
                            center_x: int = 0, center_y: int = 0,
                            window_rows: int = 0, window_cols: int = 0):
        """Set the region to highlight in the table.
        
        Args:
            is_circle: True for circle mode, False for rectangle (all cells)
            diameter: Diameter of circle in cells (for circle mode)
            center_x: X center position within window (0-indexed)
            center_y: Y center position within window (0-indexed)
            window_rows: Number of rows in the current window
            window_cols: Number of columns in the current window
        """
        self._highlight_circle = is_circle
        if is_circle:
            self._circle_diameter = diameter
            self._circle_center_x = center_x
            self._circle_center_y = center_y
        # Store window dimensions for highlighting
        self._highlight_window_rows = window_rows
        self._highlight_window_cols = window_cols
        # Trigger a visual update
        if self._pixel_array is not None and window_rows > 0 and window_cols > 0:
            top_left = self.createIndex(0, 0)
            bottom_right = self.createIndex(window_rows - 1, window_cols - 1)
            self.dataChanged.emit(top_left, bottom_right)
    
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                # Column headers are relative to window
                return str(self._window_x + section)
            elif orientation == Qt.Vertical:
                # Row headers are relative to window
                return str(self._window_y + section)
        return None
    
    def update_data(self, pixel_array: np.ndarray, show_hu: bool, slope: float, intercept: float,
                    window_x: int = 0, window_y: int = 0, window_width: int = 0, window_height: int = 0):
        """Update the model with new data and window settings."""
        # Check if pixel array changed (structural change)
        array_changed = self._pixel_array is not pixel_array
        if not array_changed and pixel_array is not None and self._pixel_array is not None:
            array_changed = not np.array_equal(self._pixel_array, pixel_array)
        
        # Check if window settings changed (structural change) - BEFORE updating
        window_changed = (self._window_x != window_x or 
                         self._window_y != window_y or 
                         self._window_width != window_width or 
                         self._window_height != window_height)
        
        # Check if display settings changed (HU toggle, slope, intercept)
        display_changed = (self._show_hu != show_hu or 
                          self._slope != slope or 
                          self._intercept != intercept)
        
        # Update all data
        self._pixel_array = pixel_array
        self._show_hu = show_hu
        self._slope = slope
        self._intercept = intercept
        self._window_x = window_x
        self._window_y = window_y
        self._window_width = window_width
        self._window_height = window_height
        
        if array_changed or window_changed:
            # Structural change - reset model
            self.beginResetModel()
            self.endResetModel()
        elif display_changed:
            # Only display values changed (HU toggle, slope/intercept) - emit dataChanged
            if self._pixel_array is not None:
                arr = self._pixel_array[0] if self._pixel_array.ndim == 3 else self._pixel_array
                # Apply windowing to get the actual visible region
                if self._window_height > 0 and self._window_width > 0:
                    start_row = self._window_y
                    end_row = min(start_row + self._window_height, arr.shape[0])
                    start_col = self._window_x
                    end_col = min(start_col + self._window_width, arr.shape[1])
                    rows = end_row - start_row
                    cols = end_col - start_col
                else:
                    rows = arr.shape[0] if arr.ndim >= 2 else 0
                    cols = arr.shape[1] if arr.ndim >= 2 else (1 if arr.size > 0 else 0)
                
                if rows > 0 and cols > 0:
                    top_left = self.createIndex(0, 0)
                    bottom_right = self.createIndex(rows - 1, cols - 1)
                    self.dataChanged.emit(top_left, bottom_right)


class ImageLabelWithOverlay(QLabel):
    """QLabel that can draw a rectangle/circle overlay and image overlay."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._image: Optional[QImage] = None
        self._cursor_rect: Optional[tuple] = None  # (x, y, w, h) in image coordinates
        self._cursor_is_circle: bool = True  # Default to circle
        self._overlay: Optional[QImage] = None
        self._show_overlay: bool = True
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(1, 1)
        
        # Set background
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(50, 50, 50))
        self.setPalette(palette)
        self.setAutoFillBackground(True)
    
    def set_image(self, image: Optional[QImage]):
        """Set the image to display."""
        self._image = image
        pixmap = QPixmap.fromImage(image) if image is not None else QPixmap()
        super().setPixmap(pixmap)
    
    def set_overlay(self, overlay: Optional[QImage]):
        """Set the overlay image."""
        self._overlay = overlay
        self.update()
    
    def toggle_overlay(self, show: bool):
        """Toggle overlay visibility."""
        self._show_overlay = show
        self.update()
    
    def set_cursor_rect(self, x: int, y: int, w: int, h: int, is_circle: bool = True):
        """Set the cursor rectangle in image coordinates."""
        self._cursor_rect = (x, y, w, h)
        self._cursor_is_circle = is_circle
        self.update()
    
    def clear_cursor_rect(self):
        """Clear the cursor rectangle."""
        self._cursor_rect = None
        self.update()
    
    def paintEvent(self, event):
        """Paint the label with overlay and cursor rectangle."""
        super().paintEvent(event)
        
        painter = QPainter(self)
        
        # Draw image overlay if available
        if self._show_overlay and self._overlay is not None and self._image is not None:
            # Get label and pixmap dimensions
            label_rect = self.rect()
            pixmap_rect = self.pixmap().rect() if self.pixmap() else QPixmap().rect()
            
            # Calculate image position within label (centered)
            img_x = (label_rect.width() - pixmap_rect.width()) // 2
            img_y = (label_rect.height() - pixmap_rect.height()) // 2
            
            # Draw overlay at image position
            painter.drawImage(img_x, img_y, self._overlay)
        
        # Draw cursor overlay (rectangle or circle)
        if (self._cursor_rect is not None and self._image is not None and 
            self.pixmap() is not None and self.pixmap().width() > 0):
            x, y, w, h = self._cursor_rect
            
            # Calculate image position within label (centered)
            label_rect = self.rect()
            pixmap_rect = self.pixmap().rect()
            img_x = (label_rect.width() - pixmap_rect.width()) // 2
            img_y = (label_rect.height() - pixmap_rect.height()) // 2
            
            # Convert to label coordinates
            label_x = img_x + x
            label_y = img_y + y
            
            painter.setPen(QColor(255, 0, 0, 200))  # Red border with some transparency
            painter.setBrush(QColor(255, 255, 0, 60))  # Semi-transparent yellow fill
            
            if self._cursor_is_circle:
                # Draw circle centered at (label_x + w/2, label_y + h/2) with diameter = min(w, h)
                center_x = label_x + w // 2
                center_y = label_y + h // 2
                diameter = min(w, h)
                painter.drawEllipse(center_x - diameter // 2, center_y - diameter // 2, diameter, diameter)
            else:
                # Draw rectangle
                painter.drawRect(label_x, label_y, w, h)
        
        painter.end()


class ImageViewerWithMouseTracking(QWidget):
    """
    Simple image viewer with mouse tracking, cursor window rectangle, mousewheel navigation,
    and statistics display.
    Emits position_changed signal when mouse moves over the image.
    Emits next_requested/prev_requested signals when mouse wheel scrolls.
    """
    
    position_changed = Signal(int, int)
    next_requested = Signal()
    prev_requested = Signal()
    image_index_changed = Signal(int)  # For spinbox changes
    overlay_color_changed = Signal(object)  # RGB tuple
    cursor_size_changed = Signal(int)  # Request to change cursor window size
    cursor_mode_changed = Signal(bool)  # True = circle, False = rectangle
    measurement_mode_changed = Signal(bool)  # True = enabled, False = disabled
    measurement_captured = Signal(dict)  # Measurement data dictionary
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._image: Optional[QImage] = None
        self._pixmap: Optional[QPixmap] = None
        self._stats_label: Optional[QLabel] = None
        self._cursor_mode_circle: bool = True  # Default to circle
        self._overlay_color: tuple = (255, 0, 0)  # Default: red
        self._measurement_mode_enabled: bool = True  # Default: enabled
        self._cursor_window_size: int = 7  # Current cursor window size
        self._setup_ui()
        self.setMouseTracking(True)
        
        # Enable focus for wheel events
        self.setFocusPolicy(Qt.StrongFocus)
        self._scroll_area.viewport().setFocusPolicy(Qt.StrongFocus)
    
    def _setup_ui(self):
        """Setup the widget layout with image+stats on top, navigation at bottom."""
        # Main layout - vertical
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)
        
        # === Top: Image + Stats in two columns ===
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)
        
        # Left column: Image
        image_container = QWidget()
        image_layout = QVBoxLayout(image_container)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.setSpacing(0)
        
        # Scroll area for image
        self._scroll_area = QScrollArea(image_container)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Inner image container
        self._image_container = QWidget()
        self._image_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._image_container_layout = QVBoxLayout(self._image_container)
        self._image_container_layout.setContentsMargins(0, 0, 0, 0)
        
        # Custom image label with overlay support
        self._image_label = ImageLabelWithOverlay(self._image_container)
        self._image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        self._image_container_layout.addWidget(self._image_label, 1)
        self._scroll_area.setWidget(self._image_container)
        image_layout.addWidget(self._scroll_area, 1)
        
        # Enable mouse tracking on the label
        self._image_label.setMouseTracking(True)
        self._image_label.installEventFilter(self)
        
        # Right column: Statistics
        stats_container = QWidget()
        stats_container.setMinimumWidth(200)
        stats_container.setMaximumWidth(300)
        stats_layout = QVBoxLayout(stats_container)
        stats_layout.setContentsMargins(4, 4, 4, 4)
        stats_layout.setSpacing(4)
        
        stats_layout.addWidget(QLabel("<b>Window Statistics</b>", self))
        
        self._stats_label = QLabel("No data loaded", self)
        self._stats_label.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self._stats_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._stats_label.setWordWrap(True)
        stats_layout.addWidget(self._stats_label, 1)
        
        # Add columns to top row
        top_row.addWidget(image_container, 1)  # Image takes 2/3
        top_row.addWidget(stats_container, 0)  # Stats takes 1/3
        main_layout.addLayout(top_row, 1)
        
        # === Bottom: Navigation controls ===
        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(4, 4, 4, 4)
        nav_layout.setSpacing(8)
        
        # Previous button
        self._prev_button = QPushButton("←", self)
        self._prev_button.setToolTip("Previous image")
        self._prev_button.setMaximumWidth(40)
        self._prev_button.clicked.connect(self._on_nav_prev)
        nav_layout.addWidget(self._prev_button)
        
        # Image spinbox
        self._image_spinbox = QSpinBox(self)
        self._image_spinbox.setMinimum(1)
        self._image_spinbox.setMaximum(1)
        self._image_spinbox.setToolTip("Image index")
        self._image_spinbox.valueChanged.connect(self._on_nav_spinbox_changed)
        nav_layout.addWidget(self._image_spinbox)
        
        # Image count label
        self._image_count_label = QLabel("/1", self)
        self._image_count_label.setToolTip("Total images")
        nav_layout.addWidget(self._image_count_label)
        
        # Next button
        self._next_button = QPushButton("→", self)
        self._next_button.setToolTip("Next image")
        self._next_button.setMaximumWidth(40)
        self._next_button.clicked.connect(self._on_nav_next)
        nav_layout.addWidget(self._next_button)
        
        nav_layout.addStretch(1)
        
        # Overlay color button
        self._color_button = QPushButton("Color", self)
        self._color_button.setToolTip("Select overlay color")
        self._color_button.clicked.connect(self._on_color_button_clicked)
        nav_layout.addWidget(self._color_button)
        
        # Cursor mode toggle
        self._cursor_toggle = QCheckBox("Circle Mode", self)
        self._cursor_toggle.setChecked(self._cursor_mode_circle)
        self._cursor_toggle.setToolTip("Toggle between circle and rectangle cursor window")
        self._cursor_toggle.stateChanged.connect(self._on_cursor_mode_toggled)
        nav_layout.addWidget(self._cursor_toggle)
        
        # Measurement mode toggle
        self._measurement_toggle = QCheckBox("Measurement Mode", self)
        self._measurement_toggle.setChecked(self._measurement_mode_enabled)
        self._measurement_toggle.setToolTip("Enable/disable measurement mode. When enabled, mouse wheel changes cursor size.")
        self._measurement_toggle.stateChanged.connect(self._on_measurement_mode_toggled)
        nav_layout.addWidget(self._measurement_toggle)
        
        main_layout.addLayout(nav_layout, 0)
        
        # Update color button style
        self._update_color_button_style()
    
    def set_image(self, image: QImage):
        """Set the image to display."""
        self._image = image
        self._image_label.set_image(image)
    
    def set_overlay(self, overlay: Optional[QImage]):
        """Set the overlay image."""
        self._image_label.set_overlay(overlay)
    
    def toggle_overlay(self, show: bool):
        """Toggle overlay visibility."""
        self._image_label.toggle_overlay(show)
    
    def set_cursor_rect(self, x: int, y: int, w: int, h: int):
        """Set the cursor rectangle position and size in image coordinates."""
        self._image_label.set_cursor_rect(x, y, w, h, self._cursor_mode_circle)
    
    def clear_cursor_rect(self):
        """Clear the cursor rectangle."""
        self._image_label.clear_cursor_rect()
    
    def set_cursor_window_size(self, size: int):
        """Set the current cursor window size."""
        self._cursor_window_size = size
    
    def set_measurement_mode(self, enabled: bool):
        """Set measurement mode enabled/disabled."""
        self._measurement_mode_enabled = enabled
        if self._measurement_toggle is not None:
            self._measurement_toggle.setChecked(enabled)
        # Note: Don't emit signal here to avoid infinite loop
        # The signal is emitted from _on_measurement_mode_toggled when user interacts
    
    def set_stats_text(self, text: str):
        """Set the statistics display text."""
        if self._stats_label is not None:
            self._stats_label.setText(text)
    
    def set_cursor_mode_circle(self, is_circle: bool):
        """Set whether cursor is circle or rectangle."""
        self._cursor_mode_circle = is_circle
        if self._cursor_toggle is not None:
            self._cursor_toggle.setChecked(is_circle)
    
    def set_navigation(self, current: int, total: int):
        """Set navigation spinbox range and count label."""
        self._image_spinbox.setMinimum(1)
        self._image_spinbox.setMaximum(max(total, 1))
        self._image_spinbox.setValue(current)
        self._image_count_label.setText(f"/{total}")
    
    def set_overlay_color(self, color: tuple):
        """Set the overlay color."""
        self._overlay_color = color
        self._update_color_button_style()
    
    def _update_color_button_style(self):
        """Update color button style to show current overlay color."""
        r, g, b = self._overlay_color
        self._color_button.setStyleSheet(
            f"background-color: rgb({r}, {g}, {b}); color: {'white' if (r+g+b) < 380 else 'black'}; "
            f"border: 1px solid #888; padding: 2px 8px;"
        )
    
    def _on_nav_prev(self):
        """Handler for previous button."""
        self.prev_requested.emit()
    
    def _on_nav_next(self):
        """Handler for next button."""
        self.next_requested.emit()
    
    def _on_nav_spinbox_changed(self, value: int):
        """Handler for spinbox value changed."""
        self.image_index_changed.emit(value - 1)  # Convert to 0-based index
    
    def _on_color_button_clicked(self):
        """Handler for color button click."""
        color = QColorDialog.getColor(
            QColor(*self._overlay_color),
            self,
            "Select Overlay Color"
        )
        if color.isValid():
            self._overlay_color = (color.red(), color.green(), color.blue())
            self._update_color_button_style()
            self.overlay_color_changed.emit(self._overlay_color)
    
    def _on_cursor_mode_toggled(self, state: int):
        """Handler for cursor mode toggle."""
        self._cursor_mode_circle = (state == Qt.Checked)
        # Emit signal to notify PixelArrayTable
        self.cursor_mode_changed.emit(self._cursor_mode_circle)
        # Update cursor shape on the label
        if self._image is not None and self._image_label.pixmap() is not None:
            # Get current cursor rect from label if it exists
            if self._image_label._cursor_rect is not None:
                x, y, w, h = self._image_label._cursor_rect
                # Update with new shape mode
                self._image_label.set_cursor_rect(x, y, w, h, self._cursor_mode_circle)
    
    def _on_measurement_mode_toggled(self, state: int):
        """Handler for measurement mode toggle."""
        self._measurement_mode_enabled = (state == Qt.Checked)
        # Emit signal to notify PixelArrayTable
        self.measurement_mode_changed.emit(self._measurement_mode_enabled)
        # When measurement mode is disabled, clear the cursor rectangle
        # When enabled, restore the cursor rectangle if we have a valid position
        if not self._measurement_mode_enabled:
            # Clear cursor rectangle
            self.clear_cursor_rect()
        elif self._last_cursor_x >= 0 and self._last_cursor_y >= 0:
            # Restore cursor rectangle at last position
            self.set_cursor_rect(self._last_cursor_x, self._last_cursor_y,
                                self._cursor_window_size, self._cursor_window_size)
        # Note: The PixelArrayTable handles whether to update on cursor position
    
    def eventFilter(self, obj, event):
        """Filter events to track mouse position on the image label."""
        if obj == self._image_label and event.type() == event.Type.MouseMove:
            if self._image is not None and self._image_label.pixmap() is not None:
                # Get mouse position relative to the label
                pos = event.position().toPoint()
                
                # Get label and pixmap dimensions
                label_rect = self._image_label.rect()
                pixmap = self._image_label.pixmap()
                if pixmap is None:
                    return True
                pixmap_rect = pixmap.rect()
                
                # Calculate the actual image position within the label
                # The image is centered in the label
                img_x = (label_rect.width() - pixmap_rect.width()) // 2
                img_y = (label_rect.height() - pixmap_rect.height()) // 2
                
                # Only emit if mouse is over the actual image area
                if (img_x <= pos.x() < img_x + pixmap_rect.width() and
                    img_y <= pos.y() < img_y + pixmap_rect.height()):
                    # Convert to image coordinates
                    img_pos_x = pos.x() - img_x
                    img_pos_y = pos.y() - img_y
                    # Emit position in image coordinates
                    self.position_changed.emit(img_pos_x, img_pos_y)
        return super().eventFilter(obj, event)
    
    def wheelEvent(self, event):
        """Handle mouse wheel for image navigation or cursor size adjustment.
        When measurement mode is enabled, wheel changes cursor size.
        When disabled, wheel navigates to previous/next image."""
        if self._measurement_mode_enabled:
            # Change cursor size
            if event.angleDelta().y() > 0:
                # Increase cursor size
                new_size = min(self._cursor_window_size + 1, 50)
            else:
                # Decrease cursor size
                new_size = max(self._cursor_window_size - 1, 1)
            
            if new_size != self._cursor_window_size:
                self._cursor_window_size = new_size
                self.cursor_size_changed.emit(new_size)
            event.accept()
        else:
            # Navigate images
            if event.angleDelta().y() > 0:
                self.next_requested.emit()
            else:
                self.prev_requested.emit()
            event.accept()
    
    def mousePressEvent(self, event):
        """Handle mouse press events for measurement capture."""
        if (event.button() == Qt.LeftButton and 
            self._measurement_mode_enabled and 
            self._image is not None and 
            self._image_label.pixmap() is not None):
            # Get mouse position relative to the label
            pos = event.position().toPoint()
            
            # Get label and pixmap dimensions
            label_rect = self._image_label.rect()
            pixmap = self._image_label.pixmap()
            if pixmap is not None:
                pixmap_rect = pixmap.rect()
                
                # Calculate the actual image position within the label
                img_x = (label_rect.width() - pixmap_rect.width()) // 2
                img_y = (label_rect.height() - pixmap_rect.height()) // 2
                
                # Check if mouse is over the actual image area
                if (img_x <= pos.x() < img_x + pixmap_rect.width() and
                    img_y <= pos.y() < img_y + pixmap_rect.height()):
                    # Convert to image coordinates
                    img_pos_x = pos.x() - img_x
                    img_pos_y = pos.y() - img_y
                    
                    # Emit measurement captured signal with position and mode
                    # PixelArrayTable will calculate statistics and emit full measurement
                    self.measurement_captured.emit({
                        'x': img_pos_x,
                        'y': img_pos_y,
                        'cursor_size': self._cursor_window_size,
                        'is_circle': self._cursor_mode_circle
                    })
                    event.accept()
                    return
        
        super().mousePressEvent(event)


class PixelArrayTable(QWidget):
    """
    Widget for displaying DICOM pixel array as a scrollable table with windowing.
    
    Features:
    - Displays a window of pixel values in a table
    - Configurable window size (default 30x30) and position
    - Two tabs: Raw pixel data and Hounsfield Units (HU) data
    - Shows Photometric Interpretation
    - Vertically and horizontally scrollable
    - Opens image viewer window on dataset load
    - Mouse tracking on image updates table with configurable cursor window (default 7x7)
    - Shows rectangle cursor overlay on image matching the table window
    - Mouse wheel on image viewer navigates to previous/next image
    - Statistics box showing mean, std dev, min, max of current window
    
    Signals:
    - next_image_requested(): Emitted when mouse wheel scrolls forward
    - prev_image_requested(): Emitted when mouse wheel scrolls backward
    """
    
    # Signals for image navigation
    next_image_requested = Signal()
    prev_image_requested = Signal()
    image_index_changed = Signal(int)  # 0-based index
    overlay_color_changed = Signal(tuple)  # RGB tuple
    # Signals for internal state sync
    cursor_mode_changed = Signal(bool)  # Forward from viewer
    measurement_mode_changed = Signal(bool)  # Forward from viewer
    measurement_captured = Signal(dict)  # Measurement data dictionary (forwarded from viewer)
    add_measurement_requested = Signal(dict)  # Request to add measurement to main window
    viewer_reopened = Signal()  # Emitted when image viewer window is reopened
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # State
        self._pixel_array: Optional[np.ndarray] = None
        self._dataset: Optional[Dataset] = None
        self._raw_model: Optional[PixelArrayModel] = None
        self._hu_model: Optional[PixelArrayModel] = None
        
        # Window settings
        self._window_x: int = 0
        self._window_y: int = 0
        self._window_width: int = 30
        self._window_height: int = 30
        
        # Cursor window size (configurable, default 7x7)
        self._cursor_window_size: int = 7
        self._cursor_size_spin: Optional[QSpinBox] = None
        
        # HU stats last calculated values (passed to external viewer)
        self._last_stats_text: str = "No data loaded"
        
        # Overlay color
        self._overlay_color: tuple = (255, 0, 0)  # Default: red
        
        # HU conversion parameters
        self._slope: float = 1.0
        self._intercept: float = 0.0
        self._has_hu: bool = False
        
        # Image viewer for cursor tracking
        self._image_viewer: Optional[ImageViewerWithMouseTracking] = None
        self._image_viewer_window = None
        
        # Last cursor position for redrawing when size changes
        self._last_cursor_x: int = -1
        self._last_cursor_y: int = -1
        
        # Measurement mode state
        self._measurement_mode_enabled: bool = True
        
        # Cursor mode state (circle or rectangle)
        self._cursor_mode_circle: bool = True  # Default to circle
        
        # Setup UI
        self._setup_ui()
    
    def _on_cursor_position_changed(self, x: int, y: int):
        """Handler for cursor position changes on the image viewer.
        Updates the table window to show a region centered at the cursor.
        Only processes updates when measurement mode is enabled."""
        if self._pixel_array is None or not self._measurement_mode_enabled:
            return
        
        # Store last cursor position
        self._last_cursor_x = x
        self._last_cursor_y = y
        
        # Get array dimensions
        arr = self._pixel_array[0] if self._pixel_array.ndim == 3 else self._pixel_array
        rows = arr.shape[0]
        cols = arr.shape[1]
        
        # Calculate center position (cursor is at x, y in image coordinates)
        center_x = x
        center_y = y
        
        # Calculate cursor window size (must be odd for proper centering)
        cursor_size = max(1, self._cursor_window_size)
        if cursor_size % 2 == 0:
            cursor_size += 1  # Ensure odd number for center pixel
        half_size = cursor_size // 2
        
        # Calculate top-left of window
        win_x = center_x - half_size
        win_y = center_y - half_size
        
        # Clamp to valid range (ensure window stays within image bounds)
        win_x = max(0, min(win_x, cols - cursor_size)) if cols >= cursor_size else 0
        win_y = max(0, min(win_y, rows - cursor_size)) if rows >= cursor_size else 0
        
        # Set window size
        win_w = min(cursor_size, cols)
        win_h = min(cursor_size, rows)
        
        # Update window controls and models
        self._window_x = win_x
        self._window_y = win_y
        self._window_width = win_w
        self._window_height = win_h
        
        # Update spin boxes
        self._win_x_spin.setValue(win_x)
        self._win_y_spin.setValue(win_y)
        self._win_width_spin.setValue(win_w)
        self._win_height_spin.setValue(win_h)
        
        # Update image viewer with cursor rectangle
        if self._image_viewer is not None:
            self._image_viewer.set_cursor_rect(win_x, win_y, win_w, win_h)
        
        # Update highlight region on both models
        # Determine if we're in circle mode
        is_circle = False
        diameter = 0
        center_x_in_window = win_w // 2  # Center of window
        center_y_in_window = win_h // 2
        if self._image_viewer is not None and hasattr(self._image_viewer, '_cursor_mode_circle'):
            is_circle = self._image_viewer._cursor_mode_circle
            if is_circle:
                diameter = min(win_w, win_h)
        
        # Update highlight on both models
        if self._raw_model is not None:
            self._raw_model.set_highlight_region(is_circle, diameter, center_x_in_window, center_y_in_window)
        if self._hu_model is not None:
            self._hu_model.set_highlight_region(is_circle, diameter, center_x_in_window, center_y_in_window)
        
        # Update models without triggering signal loop
        # (don't call _on_window_changed as it would update spin boxes again)
        self._update_models()
    
    def _update_statistics(self):
        """Calculate statistics for the current window (Raw and HU) and pass to external viewer.
        For circle mode, only pixels within the circle are included in statistics."""
        if self._pixel_array is None:
            self._last_stats_text = "No data loaded"
        else:
            # Get array (use first frame for 3D)
            arr = self._pixel_array[0] if self._pixel_array.ndim == 3 else self._pixel_array
            
            # Get window region
            win_x = self._window_x
            win_y = self._window_y
            win_w = self._window_width
            win_h = self._window_height
            
            # Clamp to actual array bounds
            win_x = max(0, min(win_x, arr.shape[1] - 1))
            win_y = max(0, min(win_y, arr.shape[0] - 1))
            win_w = min(win_w, arr.shape[1] - win_x)
            win_h = min(win_h, arr.shape[0] - win_y)
            
            if win_w <= 0 or win_h <= 0:
                self._last_stats_text = "Window: 0x0"
            else:
                # Extract window region
                region = arr[win_y:win_y + win_h, win_x:win_x + win_w]
                
                # Check if we're in circle mode and have a viewer
                is_circle = False
                if (self._image_viewer is not None and 
                    hasattr(self._image_viewer, '_cursor_mode_circle')):
                    is_circle = self._image_viewer._cursor_mode_circle
                
                if is_circle and win_w > 0 and win_h > 0:
                    # For circle mode, only use pixels within the circle
                    # Circle is centered at (win_w/2, win_h/2) with diameter = min(win_w, win_h)
                    center_x = win_w / 2
                    center_y = win_h / 2
                    diameter = min(win_w, win_h)
                    radius = diameter / 2
                    radius_sq = radius * radius
                    
                    # Create mask for circle
                    yy, xx = np.ogrid[:win_h, :win_w]
                    mask = (xx - center_x)**2 + (yy - center_y)**2 <= radius_sq
                    
                    # Extract pixels within circle
                    circle_pixels = region[mask]
                    total_pixels = len(circle_pixels)
                    window_desc = f"Circle: {diameter}x{diameter} = {total_pixels} pixels"
                    
                    if total_pixels > 0:
                        # Calculate Raw statistics for circle pixels
                        raw_mean = float(np.mean(circle_pixels))
                        raw_std = float(np.std(circle_pixels))
                        raw_min = float(np.min(circle_pixels))
                        raw_max = float(np.max(circle_pixels))
                    else:
                        raw_mean = raw_std = raw_min = raw_max = 0.0
                else:
                    # For rectangle mode, use all pixels in the region
                    total_pixels = region.size
                    window_desc = f"Window: {win_w}x{win_h} = {total_pixels} pixels"
                    
                    # Calculate Raw statistics for rectangular region
                    raw_mean = float(np.mean(region))
                    raw_std = float(np.std(region))
                    raw_min = float(np.min(region))
                    raw_max = float(np.max(region))
                
                # Format raw stats
                stats_text = f"""<b>{window_desc}</b><br>
<br>
<b>Raw Pixel Data:</b><br>
Mean: {raw_mean:8.2f}<br>
Std Dev: {raw_std:8.2f}<br>
Min: {raw_min:8.2f}<br>
Max: {raw_max:8.2f}"""
                
                # Calculate HU statistics if HU conversion is available
                if self._has_hu:
                    # Apply HU conversion to the appropriate pixel set (circle or rectangle)
                    if is_circle:
                        if total_pixels > 0:
                            hu_pixels = circle_pixels.astype(np.float32) * self._slope + self._intercept
                        else:
                            hu_pixels = np.array([])
                    else:
                        hu_pixels = region.astype(np.float32) * self._slope + self._intercept
                    
                    if len(hu_pixels) > 0:
                        hu_mean = float(np.mean(hu_pixels))
                        hu_std = float(np.std(hu_pixels))
                        hu_min = float(np.min(hu_pixels))
                        hu_max = float(np.max(hu_pixels))
                    else:
                        hu_mean = hu_std = hu_min = hu_max = 0.0
                    
                    stats_text += f"""<br>
<br>
<b>Hounsfield Units (HU):</b><br>
Mean: {hu_mean:8.2f}<br>
Std Dev: {hu_std:8.2f}<br>
Min: {hu_min:8.2f}<br>
Max: {hu_max:8.2f}"""
                else:
                    stats_text += "<br><br><i>HU: Not available</i>"
                
                self._last_stats_text = stats_text
        
        # Update external viewer's stats display
        if self._image_viewer is not None:
            self._image_viewer.set_stats_text(self._last_stats_text)
    
    def _update_highlight_region(self):
        """Update the highlight region on both models based on current window and cursor mode."""
        if (self._raw_model is not None and self._hu_model is not None and
            self._window_width > 0 and self._window_height > 0):
            # Determine if we're in circle mode
            is_circle = False
            diameter = 0
            center_x = self._window_width // 2
            center_y = self._window_height // 2
            
            if self._image_viewer is not None and hasattr(self._image_viewer, '_cursor_mode_circle'):
                is_circle = self._image_viewer._cursor_mode_circle
                if is_circle:
                    diameter = min(self._window_width, self._window_height)
            
            self._raw_model.set_highlight_region(is_circle, diameter, center_x, center_y,
                                                  self._window_height, self._window_width)
            self._hu_model.set_highlight_region(is_circle, diameter, center_x, center_y,
                                                  self._window_height, self._window_width)
    
    def _on_viewer_cursor_mode_changed(self, is_circle: bool):
        """Handler for cursor mode change from external viewer."""
        # Store the cursor mode state
        self._cursor_mode_circle = is_circle
        
        # Update the viewer's cursor rectangle with new shape
        if (self._image_viewer is not None and 
            hasattr(self._image_viewer, '_image_label') and 
            self._image_viewer._image_label is not None and
            hasattr(self._image_viewer._image_label, '_cursor_rect') and
            self._image_viewer._image_label._cursor_rect is not None):
            x, y, w, h = self._image_viewer._image_label._cursor_rect
            self._image_viewer._image_label.set_cursor_rect(x, y, w, h, is_circle)
        
        # Update highlight region and statistics
        self._update_highlight_region()
        if self._pixel_array is not None and self._dataset is not None:
            self._update_statistics()
        self.cursor_mode_changed.emit(is_circle)
    
    def _on_viewer_measurement_mode_changed(self, enabled: bool):
        """Handler for measurement mode change from external viewer."""
        self._measurement_mode_enabled = enabled
        # When measurement mode is re-enabled, restore the cursor position if we have one
        if enabled and self._last_cursor_x >= 0 and self._last_cursor_y >= 0:
            # Trigger a cursor position update to sync table window with cursor
            # Note: _on_cursor_position_changed checks both _pixel_array and _measurement_mode_enabled
            # Since we just set _measurement_mode_enabled=True, we need to also check _pixel_array
            if self._pixel_array is not None:
                self._on_cursor_position_changed(self._last_cursor_x, self._last_cursor_y)
            else:
                # No pixel array loaded, just update the cursor rectangle on the viewer
                if self._image_viewer is not None:
                    self._image_viewer.set_cursor_rect(
                        self._last_cursor_x, self._last_cursor_y,
                        self._cursor_window_size, self._cursor_window_size
                    )
        else:
            # Just update the highlight region
            self._update_highlight_region()
        self.measurement_mode_changed.emit(enabled)
    
    def _on_measurement_captured(self, data: dict):
        """Handler for measurement capture from external viewer.
        
        Args:
            data: Dictionary with x, y, cursor_size, is_circle
        """
        x = data.get('x', 0)
        y = data.get('y', 0)
        cursor_size = data.get('cursor_size', 7)
        is_circle = data.get('is_circle', False)
        
        if self._pixel_array is not None and self._dataset is not None:
            # Calculate the window region based on cursor position and size
            arr = self._pixel_array[0] if self._pixel_array.ndim == 3 else self._pixel_array
            rows = arr.shape[0]
            cols = arr.shape[1]
            
            # Ensure cursor_size is odd for proper centering
            actual_cursor_size = max(1, cursor_size)
            if actual_cursor_size % 2 == 0:
                actual_cursor_size += 1
            half_size = actual_cursor_size // 2
            
            # Calculate window bounds
            win_x = max(0, min(x - half_size, cols - actual_cursor_size)) if cols >= actual_cursor_size else 0
            win_y = max(0, min(y - half_size, rows - actual_cursor_size)) if rows >= actual_cursor_size else 0
            win_w = min(actual_cursor_size, cols - win_x)
            win_h = min(actual_cursor_size, rows - win_y)
            
            # Extract the window region
            region = arr[win_y:win_y + win_h, win_x:win_x + win_w]
            
            # Calculate statistics for this region
            if is_circle and win_w > 0 and win_h > 0:
                # Circle mode: only use pixels within the circle
                center_x = win_w / 2
                center_y = win_h / 2
                diameter = min(win_w, win_h)
                radius = diameter / 2
                radius_sq = radius * radius
                
                yy, xx = np.ogrid[:win_h, :win_w]
                mask = (xx - center_x)**2 + (yy - center_y)**2 <= radius_sq
                circle_pixels = region[mask]
                
                if len(circle_pixels) > 0:
                    raw_mean = float(np.mean(circle_pixels))
                    raw_std = float(np.std(circle_pixels))
                    raw_min = float(np.min(circle_pixels))
                    raw_max = float(np.max(circle_pixels))
                    
                    if self._has_hu:
                        hu_pixels = circle_pixels.astype(np.float32) * self._slope + self._intercept
                        hu_mean = float(np.mean(hu_pixels))
                        hu_std = float(np.std(hu_pixels))
                        hu_min = float(np.min(hu_pixels))
                        hu_max = float(np.max(hu_pixels))
                    else:
                        hu_mean = hu_std = hu_min = hu_max = 0.0
                else:
                    raw_mean = raw_std = raw_min = raw_max = 0.0
                    hu_mean = hu_std = hu_min = hu_max = 0.0
            else:
                # Rectangle mode: use all pixels
                raw_mean = float(np.mean(region))
                raw_std = float(np.std(region))
                raw_min = float(np.min(region))
                raw_max = float(np.max(region))
                
                if self._has_hu:
                    hu_region = region.astype(np.float32) * self._slope + self._intercept
                    hu_mean = float(np.mean(hu_region))
                    hu_std = float(np.std(hu_region))
                    hu_min = float(np.min(hu_region))
                    hu_max = float(np.max(hu_region))
                else:
                    hu_mean = hu_std = hu_min = hu_max = 0.0
            
            # Create measurement entry
            measurement = {
                'x': x,
                'y': y,
                'cursor_size': actual_cursor_size,
                'is_circle': is_circle,
                'raw_mean': raw_mean,
                'raw_std': raw_std,
                'raw_min': raw_min,
                'raw_max': raw_max,
                'hu_mean': hu_mean,
                'hu_std': hu_std,
                'hu_min': hu_min,
                'hu_max': hu_max,
                'note': ''  # Free text field
            }
            
            # Emit signal to main window to add to measurements list
            self.add_measurement_requested.emit(measurement)
    
    def _on_cursor_window_size_changed(self, size: int):
        """Handler for cursor window size spin box changes."""
        self._cursor_window_size = size
        self._update_highlight_region()
        
    def _on_viewer_cursor_size_changed(self, size: int):
        """Handler for cursor size change from external viewer (wheel in measurement mode)."""
        # Update the spinbox and trigger the same logic as spinbox change
        if self._cursor_size_spin is not None:
            self._cursor_size_spin.setValue(size)
        # Redraw cursor rectangle with new size if we have a valid position
        if (self._pixel_array is not None and self._image_viewer is not None and
            self._last_cursor_x >= 0 and self._last_cursor_y >= 0):
            # Recalculate and update with new size
            arr = self._pixel_array[0] if self._pixel_array.ndim == 3 else self._pixel_array
            rows = arr.shape[0]
            cols = arr.shape[1]
            
            cursor_size = max(1, self._cursor_window_size)
            if cursor_size % 2 == 0:
                cursor_size += 1
            half_size = cursor_size // 2
            
            center_x = self._last_cursor_x
            center_y = self._last_cursor_y
            
            win_x = max(0, min(center_x - half_size, cols - cursor_size)) if cols >= cursor_size else 0
            win_y = max(0, min(center_y - half_size, rows - cursor_size)) if rows >= cursor_size else 0
            win_w = min(cursor_size, cols)
            win_h = min(cursor_size, rows)
            
            self._image_viewer.set_cursor_rect(win_x, win_y, win_w, win_h)
            
            # Also update the table window
            self._window_x = win_x
            self._window_y = win_y
            self._window_width = win_w
            self._window_height = win_h
            self._win_x_spin.setValue(win_x)
            self._win_y_spin.setValue(win_y)
            self._win_width_spin.setValue(win_w)
            self._win_height_spin.setValue(win_h)
            self._update_highlight_region()
            self._update_models()
    
    def _setup_ui(self):
        """Setup the widget layout."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)
        
        # Header row: Photometric Interpretation
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Photometric Interpretation label
        self._photo_label = QLabel("Photometric Interpretation: N/A", self)
        self._photo_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(self._photo_label, 1)
        header_layout.addStretch(0)
        
        main_layout.addLayout(header_layout)
        
        # Window controls row
        window_layout = QHBoxLayout()
        window_layout.setContentsMargins(0, 0, 0, 0)
        window_layout.setSpacing(8)
        
        # Window position controls
        window_layout.addWidget(QLabel("Window:", self))
        
        self._win_x_spin = QSpinBox(self)
        self._win_x_spin.setMinimum(0)
        self._win_x_spin.setMaximum(10000)
        self._win_x_spin.setValue(0)
        self._win_x_spin.setToolTip("Window X position (column)")
        self._win_x_spin.valueChanged.connect(self._on_window_changed)
        window_layout.addWidget(QLabel("X:", self))
        window_layout.addWidget(self._win_x_spin)
        
        self._win_y_spin = QSpinBox(self)
        self._win_y_spin.setMinimum(0)
        self._win_y_spin.setMaximum(10000)
        self._win_y_spin.setValue(0)
        self._win_y_spin.setToolTip("Window Y position (row)")
        self._win_y_spin.valueChanged.connect(self._on_window_changed)
        window_layout.addWidget(QLabel("Y:", self))
        window_layout.addWidget(self._win_y_spin)
        
        # Window size controls
        self._win_width_spin = QSpinBox(self)
        self._win_width_spin.setMinimum(1)
        self._win_width_spin.setMaximum(1000)
        self._win_width_spin.setValue(30)
        self._win_width_spin.setToolTip("Window width")
        self._win_width_spin.valueChanged.connect(self._on_window_changed)
        window_layout.addWidget(QLabel("W:", self))
        window_layout.addWidget(self._win_width_spin)
        
        self._win_height_spin = QSpinBox(self)
        self._win_height_spin.setMinimum(1)
        self._win_height_spin.setMaximum(1000)
        self._win_height_spin.setValue(30)
        self._win_height_spin.setToolTip("Window height")
        self._win_height_spin.valueChanged.connect(self._on_window_changed)
        window_layout.addWidget(QLabel("H:", self))
        window_layout.addWidget(self._win_height_spin)
        
        # Cursor window size control (for image navigation)
        window_layout.addWidget(QLabel("Cursor:", self))
        self._cursor_size_spin = QSpinBox(self)
        self._cursor_size_spin.setMinimum(1)
        self._cursor_size_spin.setMaximum(50)
        self._cursor_size_spin.setValue(7)
        self._cursor_size_spin.setToolTip("Cursor window size (odd number recommended for centering)")
        self._cursor_size_spin.valueChanged.connect(self._on_cursor_window_size_changed)
        window_layout.addWidget(self._cursor_size_spin)
        
        window_layout.addStretch(1)
        main_layout.addLayout(window_layout)
        
        # Create tab widget for Raw and HU data
        self._tab_widget = QTabWidget(self)
        
        # Raw data tab
        self._raw_table = QTableView(self)
        self._raw_model = PixelArrayModel(None, False, 1.0, 0.0, self)
        self._raw_table.setModel(self._raw_model)
        self._configure_table(self._raw_table)
        
        # HU data tab
        self._hu_table = QTableView(self)
        self._hu_model = PixelArrayModel(None, True, 1.0, 0.0, self)
        self._hu_table.setModel(self._hu_model)
        self._configure_table(self._hu_table)
        
        self._tab_widget.addTab(self._raw_table, "Raw Pixel Data")
        self._tab_widget.addTab(self._hu_table, "Hounsfield Units (HU)")
        
        main_layout.addWidget(self._tab_widget, 1)
    
    def _configure_table(self, table: QTableView):
        """Configure a table view with common settings."""
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        
        vertical_header = table.verticalHeader()
        vertical_header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        
        # Enable scrolling
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Read-only (view-only by default)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
    
    def set_dataset(self, ds: Optional[Dataset]):
        """
        Set the DICOM dataset to display pixel data from.
        
        Args:
            ds: pydicom Dataset, or None to clear
        """
        self._dataset = ds
        
        # Clear existing image viewer but keep window open
        if ds is None:
            if self._image_viewer is not None:
                self._image_viewer.set_image(QImage())
                self._image_viewer.clear_cursor_rect()
                self._last_cursor_x = -1
                self._last_cursor_y = -1
            self._photo_label.setText("Photometric Interpretation: N/A")
            self._win_x_spin.setValue(0)
            self._win_y_spin.setValue(0)
            self._win_width_spin.setValue(30)
            self._win_height_spin.setValue(30)
            self._cursor_size_spin.setValue(7)
            self._window_x = 0
            self._window_y = 0
            self._window_width = 30
            self._window_height = 30
            self._cursor_window_size = 7
            self._slope = 1.0
            self._intercept = 0.0
            self._has_hu = False
            self._clear_tables()
            return
        
        # Update Photometric Interpretation
        photo = getattr(ds, 'PhotometricInterpretation', 'N/A')
        self._photo_label.setText(f"Photometric Interpretation: {photo}")
        
        # Get HU conversion parameters
        self._slope = getattr(ds, 'RescaleSlope', 1.0)
        self._intercept = getattr(ds, 'RescaleIntercept', 0.0)
        self._has_hu = self._slope != 1.0 or self._intercept != 0.0
        
        # Try to get pixel array
        try:
            if hasattr(ds, 'pixel_array'):
                self._pixel_array = ds.pixel_array
                # Update window spin box maxima based on array dimensions
                arr = self._pixel_array[0] if self._pixel_array.ndim == 3 else self._pixel_array
                self._win_x_spin.setMaximum(max(arr.shape[1] - 1, 0))
                self._win_y_spin.setMaximum(max(arr.shape[0] - 1, 0))
                self._win_width_spin.setMaximum(arr.shape[1])
                self._win_height_spin.setMaximum(arr.shape[0])
                # Reset window to top-left corner with default size
                self._window_x = 0
                self._window_y = 0
                self._window_width = self._win_width_spin.value()
                self._window_height = self._win_height_spin.value()
                self._win_x_spin.setValue(0)
                self._win_y_spin.setValue(0)
                self._update_models()
                
                # Update or open image viewer
                self._open_or_update_image_viewer(ds)
            else:
                self._pixel_array = None
                self._clear_tables()
        except Exception as e:
            print(f"Error loading pixel array: {e}")
            self._pixel_array = None
            self._clear_tables()
    
    def _on_viewer_window_destroyed(self, obj=None):
        """Handler for when the viewer window is destroyed/closed by user."""
        # Clean up references so we know to recreate the window next time
        self._image_viewer_window = None
        self._image_viewer = None
    
    def open_image_viewer_window(self, dataset=None):
        """Public method to open/reopen the image viewer window.
        Called from main window's Show Image Window button.
        
        Args:
            dataset: Optional dataset to display. If None, uses self._dataset.
        """
        # Use provided dataset or fall back to current dataset
        ds = dataset if dataset is not None else self._dataset
        
        if ds is not None and hasattr(ds, 'pixel_array') and ds.pixel_array is not None:
            # Check if window exists but is not visible (was closed by user)
            window_was_closed = (self._image_viewer_window is not None and 
                               not self._image_viewer_window.isVisible())
            
            # Clear viewer references so set_dataset will create a new window
            if window_was_closed:
                self._image_viewer_window = None
                self._image_viewer = None
            
            # Call set_dataset which will update all state and open viewer
            self.set_dataset(ds)
            
            # Emit signal if window was recreated so main window can update navigation
            if window_was_closed and self._image_viewer_window is not None:
                self.viewer_reopened.emit()
        elif self._image_viewer_window is not None and self._image_viewer_window.isVisible():
            # Window exists and is visible, just raise it
            self._image_viewer_window.raise_()
            self._image_viewer_window.activateWindow()
    
    def _open_or_update_image_viewer(self, ds: Dataset):
        """Open or update the image viewer window for the current dataset.
        Reuses existing window if available."""
        if not HAS_IMAGE_UTILS:
            print("Warning: image_utils not available, cannot open image viewer")
            return
        
        try:
            # Convert DICOM to QImage
            qimage = dicom_to_qimage(ds)
            if qimage is None:
                print("Warning: Could not convert DICOM to QImage")
                return
            
            # If viewer doesn't exist yet, or window was closed, create new one
            if self._image_viewer is None or self._image_viewer_window is None:
                # Create image viewer
                self._image_viewer = ImageViewerWithMouseTracking()
                
                # Connect signals
                self._image_viewer.position_changed.connect(self._on_cursor_position_changed)
                self._image_viewer.next_requested.connect(self.next_image_requested)
                self._image_viewer.prev_requested.connect(self.prev_image_requested)
                self._image_viewer.image_index_changed.connect(self.image_index_changed)
                self._image_viewer.overlay_color_changed.connect(self.overlay_color_changed)
                self._image_viewer.cursor_size_changed.connect(self._on_viewer_cursor_size_changed)
                self._image_viewer.cursor_mode_changed.connect(self._on_viewer_cursor_mode_changed)
                self._image_viewer.measurement_mode_changed.connect(self._on_viewer_measurement_mode_changed)
                self._image_viewer.measurement_captured.connect(self._on_measurement_captured)
                # Set initial overlay color
                self._image_viewer.set_overlay_color(self._overlay_color if hasattr(self, '_overlay_color') else (255, 0, 0))
                # Set initial cursor window size
                self._image_viewer.set_cursor_window_size(self._cursor_window_size)
                # Set initial cursor mode
                self._image_viewer.set_cursor_mode_circle(self._cursor_mode_circle)
                # Set initial measurement mode
                self._image_viewer.set_measurement_mode(self._measurement_mode_enabled)
                # Sync last cursor position from PixelArrayTable to viewer
                if self._last_cursor_x >= 0 and self._last_cursor_y >= 0:
                    self._image_viewer._last_cursor_x = self._last_cursor_x
                    self._image_viewer._last_cursor_y = self._last_cursor_y
                
                # Create a simple window (no parent = top-level window)
                self._image_viewer_window = QWidget(None)
                self._image_viewer_window.setWindowTitle("DICOM Image - Move cursor to update table, Wheel: size (Measurement) / navigate (Disabled)")
                self._image_viewer_window.setGeometry(100, 100, 800, 600)
                layout = QVBoxLayout(self._image_viewer_window)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.addWidget(self._image_viewer)
                
                # Set up close event handler for the window
                self._image_viewer_window.destroyed.connect(self._on_viewer_window_destroyed)
                
                # Show window
                self._image_viewer_window.show()
            
            # Update image in existing viewer
            self._image_viewer.set_image(qimage)
            self._image_viewer.clear_cursor_rect()
            self._last_cursor_x = -1
            self._last_cursor_y = -1
            
        except Exception as e:
            print(f"Error opening/updating image viewer: {e}")
            import traceback
            traceback.print_exc()
            self._image_viewer = None
            self._image_viewer_window = None
    
    def _on_window_changed(self):
        """Handler for window position/size spin box changes."""
        self._window_x = self._win_x_spin.value()
        self._window_y = self._win_y_spin.value()
        self._window_width = self._win_width_spin.value()
        self._window_height = self._win_height_spin.value()
        
        # Update cursor rectangle on image viewer to match new window
        if self._image_viewer is not None:
            self._image_viewer.set_cursor_rect(
                self._window_x, self._window_y,
                self._window_width, self._window_height
            )
            # Update last cursor position for measurement mode re-enable
            self._last_cursor_x = self._window_x + self._window_width // 2
            self._last_cursor_y = self._window_y + self._window_height // 2
        
        self._update_highlight_region()
        if self._pixel_array is not None and self._dataset is not None:
            self._update_models()
        else:
            # Still update stats even if no dataset (to show empty state)
            self._update_statistics()
    
    def _update_models(self):
        """Update both models with current pixel data and settings."""
        if self._pixel_array is None or self._dataset is None:
            return
        
        try:
            # Update label with dimensions
            if self._pixel_array.ndim == 3:
                rows, cols = self._pixel_array[0].shape
            elif self._pixel_array.ndim == 2:
                rows, cols = self._pixel_array.shape
            else:
                rows, cols = 0, 0
            
            photo = getattr(self._dataset, 'PhotometricInterpretation', 'N/A')
            self._photo_label.setText(f"Photometric Interpretation: {photo} ({rows}x{cols})")
            
            # Update highlight region before updating models
            self._update_highlight_region()
            
            # Update both models
            self._raw_model.update_data(self._pixel_array, False, 1.0, 0.0,
                                        self._window_x, self._window_y,
                                        self._window_width, self._window_height)
            
            if self._has_hu:
                self._hu_model.update_data(self._pixel_array, True, self._slope, self._intercept,
                                            self._window_x, self._window_y,
                                            self._window_width, self._window_height)
            else:
                # If no HU conversion available, show raw values in HU tab too
                self._hu_model.update_data(self._pixel_array, False, 1.0, 0.0,
                                            self._window_x, self._window_y,
                                            self._window_width, self._window_height)
            
            # Update statistics
            self._update_statistics()
        except Exception as e:
            print(f"Error updating pixel models: {e}")
            import traceback
            traceback.print_exc()
    
    def _clear_tables(self):
        """Clear both pixel tables."""
        # Clear highlight region
        if self._raw_model is not None:
            self._raw_model.set_highlight_region(False, 0, 0, 0, 0, 0)
        if self._hu_model is not None:
            self._hu_model.set_highlight_region(False, 0, 0, 0, 0, 0)
        self._raw_model.update_data(None, False, 1.0, 0.0, 0, 0, 0, 0)
        self._hu_model.update_data(None, False, 1.0, 0.0, 0, 0, 0, 0)
        self._pixel_array = None
        self._update_statistics()
    
    def set_viewer_overlay(self, overlay_qimage):
        """Set overlay on the external image viewer.
        
        Args:
            overlay_qimage: QImage with overlay, or None
        """
        if self._image_viewer is not None:
            self._image_viewer.set_overlay(overlay_qimage)
    
    def clear(self):
        """Clear the entire widget."""
        self._clear_tables()
        self._photo_label.setText("Photometric Interpretation: N/A")
        self._win_x_spin.setValue(0)
        self._win_y_spin.setValue(0)
        self._win_width_spin.setValue(30)
        self._win_height_spin.setValue(30)
        self._cursor_size_spin.setValue(7)
        self._window_x = 0
        self._window_y = 0
        self._window_width = 30
        self._window_height = 30
        self._cursor_window_size = 7
        self._last_cursor_x = -1
        self._last_cursor_y = -1
        self._slope = 1.0
        self._intercept = 0.0
        self._has_hu = False
        self._dataset = None
        self._measurement_mode_enabled = True
        self._cursor_mode_circle = True  # Reset to circle mode
        
        # Clear external viewer
        if self._image_viewer is not None:
            self._image_viewer.set_image(QImage())
            self._image_viewer.clear_cursor_rect()
            self._image_viewer.set_stats_text("No data loaded")
            self._image_viewer.set_navigation(0, 0)
            self._image_viewer.set_measurement_mode(True)
