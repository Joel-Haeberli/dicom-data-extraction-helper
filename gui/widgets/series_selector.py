#!/usr/bin/env python3
"""
Series Selector Widget for DICOM Data Extraction Helper.

This widget allows users to select from available image series and displays
series metadata.
"""

from typing import Optional, List
from pathlib import Path

from PySide6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont

try:
    from models.image_series import ImageSeries
    from models.observable_series_manager import ObservableImageSeriesManager
    HAS_MODELS = True
except ImportError:
    # Fallback for testing without models
    HAS_MODELS = False
    ImageSeries = Any
    ObservableImageSeriesManager = Any


class SeriesSelector(QWidget):
    """
    Widget for selecting from available image series.
    
    This widget displays a list of available ImageSeries and allows
    the user to select one. It automatically updates when the series
    manager's available series change.
    
    Signals:
        series_selected: Emitted when user selects a series
    """
    
    series_selected = Signal(object)  # Emitted with selected ImageSeries
    
    def __init__(self, series_manager: Optional[ObservableImageSeriesManager] = None, parent=None):
        """Initialize the series selector."""
        super().__init__(parent)
        self._series_manager = series_manager
        self._setup_ui()
        
        if series_manager:
            self._connect_to_series_manager()
    
    def _setup_ui(self):
        """Setup the widget UI."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Title label
        title_label = QLabel("Available Series:", self)
        title_label.setStyleSheet("font-weight: bold; color: #e0e0e0;")
        layout.addWidget(title_label)
        
        # Series list
        self._series_list_widget = QListWidget(self)
        self._series_list_widget.setMinimumHeight(100)
        self._series_list_widget.setMaximumHeight(300)
        self._series_list_widget.setSelectionMode(QListWidget.SingleSelection)
        self._series_list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self._series_list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        
        # Set styling for dark mode
        self._series_list_widget.setStyleSheet("""
            QListWidget {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #444;
                padding: 4px;
            }
            QListWidget::item:selected {
                background-color: #0078d7;
                color: #ffffff;
            }
            QListWidget::item:hover {
                background-color: #3c3c3c;
            }
        """)
        
        layout.addWidget(self._series_list_widget, 1)
        
        # No series label
        self._no_series_label = QLabel("No series available", self)
        self._no_series_label.setStyleSheet("color: #666; font-style: italic;")
        self._no_series_label.setAlignment(Qt.AlignCenter)
        self._no_series_label.setVisible(False)
        layout.addWidget(self._no_series_label)
        
        # Update the list
        self._update_series_list()
    
    def _connect_to_series_manager(self):
        """Connect to series manager signals."""
        if self._series_manager:
            self._series_manager.series_list_changed.connect(self._on_series_list_changed)
            self._series_manager.current_series_changed.connect(self._on_current_series_changed)
    
    def set_series_manager(self, series_manager: ObservableImageSeriesManager):
        """Set the series manager to use."""
        self._series_manager = series_manager
        self._connect_to_series_manager()
        self._update_series_list()
    
    def _on_series_list_changed(self, series_list: List[ImageSeries]):
        """Handle series list changes from the manager."""
        self._update_series_list()
    
    def _on_current_series_changed(self, series: Optional[ImageSeries]):
        """Handle current series changes from the manager."""
        if series is not None:
            self._select_series_in_list(series)
    
    def _update_series_list(self):
        """Update the list of available series."""
        self._series_list_widget.clear()
        
        if not self._series_manager:
            self._no_series_label.setVisible(True)
            return
        
        series_list = self._series_manager.available_series
        
        if not series_list:
            self._no_series_label.setVisible(True)
            self._series_list_widget.setVisible(False)
            return
        
        self._no_series_label.setVisible(False)
        self._series_list_widget.setVisible(True)
        
        for series in series_list:
            item = self._create_series_item(series)
            self._series_list_widget.addItem(item)
    
    def _create_series_item(self, series: ImageSeries) -> QListWidgetItem:
        """Create a list item for a series."""
        item = QListWidgetItem()
        
        # Set display text with series information
        display_text = self._format_series_display_text(series)
        item.setText(display_text)
        
        # Store reference to the series
        item.setData(Qt.UserRole, series)
        
        # Set tooltip with more details
        tooltip = self._format_series_tooltip(series)
        item.setToolTip(tooltip)
        
        return item
    
    def _format_series_display_text(self, series: ImageSeries) -> str:
        """Format series information for display."""
        parts = []
        
        if series.series_description:
            parts.append(f"{series.series_description}")
        if series.modality:
            parts.append(f"[{series.modality}]")
        parts.append(f"{series.num_slices} slices")
        
        # Add shape information
        if series.shape[0] > 0:
            parts.append(f"{series.slice_shape[0]}x{series.slice_shape[1]}")
        
        return " ".join(parts)
    
    def _format_series_tooltip(self, series: ImageSeries) -> str:
        """Format series information for tooltip."""
        lines = [
            f"Series UID: {series.series_uid}",
            f"Study UID: {series.study_uid}",
            f"Patient ID: {series.patient_id}",
            f"Modality: {series.modality}",
            f"Description: {series.series_description}",
            f"Slices: {series.num_slices}",
            f"Shape: {series.shape}",
        ]
        
        if series.patient_name:
            lines.append(f"Patient Name: {series.patient_name}")
        if series.study_date:
            lines.append(f"Study Date: {series.study_date}")
        
        return "\n".join(lines)
    
    def _select_series_in_list(self, series: ImageSeries):
        """Select a series in the list by finding its item."""
        for i in range(self._series_list_widget.count()):
            item = self._series_list_widget.item(i)
            item_series = item.data(Qt.UserRole)
            if item_series == series:
                self._series_list_widget.setCurrentItem(item)
                break
    
    def _on_selection_changed(self):
        """Handle selection changes in the list."""
        selected_items = self._series_list_widget.selectedItems()
        if selected_items:
            item = selected_items[0]
            series = item.data(Qt.UserRole)
            if series is not None:
                self.series_selected.emit(series)
    
    def _on_item_double_clicked(self, item: QListWidgetItem):
        """Handle double-click on a series item."""
        series = item.data(Qt.UserRole)
        if series is not None:
            self.series_selected.emit(series)
    
    def get_selected_series(self) -> Optional[ImageSeries]:
        """Get the currently selected series."""
        selected_items = self._series_list_widget.selectedItems()
        if selected_items:
            item = selected_items[0]
            return item.data(Qt.UserRole)
        return None
    
    def select_series(self, series: ImageSeries):
        """Programmatically select a series."""
        if self._series_manager:
            self._series_manager.set_current_series(series)
        else:
            # If no manager, just select in the UI
            self._select_series_in_list(series)
            self.series_selected.emit(series)
    
    def refresh(self):
        """Refresh the series list."""
        self._update_series_list()
    
    def clear(self):
        """Clear the series list."""
        self._series_list_widget.clear()
        self._no_series_label.setVisible(True)
        self._series_list_widget.setVisible(False)
    
    def set_enabled(self, enabled: bool):
        """Enable or disable the widget."""
        self._series_list_widget.setEnabled(enabled)
        self.setVisible(enabled)