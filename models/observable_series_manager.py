#!/usr/bin/env python3
"""
Observable Image Series Manager for DICOM Data Extraction Helper.

This module provides an observable version of ImageSeriesManager that emits
signals when the series list or current series changes.
"""

from typing import List, Optional
from pathlib import Path

from PySide6.QtCore import Signal, QObject

from .image_series import ImageSeries, ImageSeriesManager


class ObservableImageSeriesManager(ImageSeriesManager, QObject):
    """
    ImageSeriesManager with signal support for Qt applications.
    
    This class extends ImageSeriesManager to emit signals when:
    - The list of available series changes
    - The current series selection changes
    
    This allows GUI components to react to changes in the series data
    without direct coupling to the manager.
    
    Signals:
        series_list_changed: Emitted when the list of available series changes
        current_series_changed: Emitted when the current series selection changes
    """
    
    # Signals
    series_list_changed = Signal(object)  # Emitted when series list changes (with list)
    current_series_changed = Signal(object)  # Emitted when current series changes
    series_loaded = Signal(object)  # Emitted when new series are loaded (with list)
    series_cleared = Signal()  # Emitted when all series are cleared
    
    def __init__(self, parent=None):
        """Initialize the observable series manager."""
        ImageSeriesManager.__init__(self)
        QObject.__init__(self, parent)
    
    def load_series_list(self, series_list: List[ImageSeries]):
        """Load a list of series, replacing current list and emitting signals."""
        super().load_series_list(series_list)
        self.series_list_changed.emit(self._series_list.copy())
        self.current_series_changed.emit(self._current_series)
        self.series_loaded.emit(series_list)
    
    def add_series_list(self, series_list: List[ImageSeries]):
        """Add series to the current list and emit signals."""
        super().add_series_list(series_list)
        self.series_list_changed.emit(self._series_list.copy())
        self.series_loaded.emit(series_list)
    
    def set_current_series(self, series: ImageSeries):
        """Set the currently selected series and emit signal."""
        super().set_current_series(series)
        self.current_series_changed.emit(self._current_series)
    
    def set_current_series_by_index(self, index: int):
        """Set current series by index and emit signal."""
        super().set_current_series_by_index(index)
        self.current_series_changed.emit(self._current_series)
    
    def set_current_series_by_uid(self, series_uid: str):
        """Set current series by Series UID and emit signal."""
        super().set_current_series_by_uid(series_uid)
        self.current_series_changed.emit(self._current_series)
    
    def clear(self):
        """Clear all loaded series and emit signals."""
        super().clear()
        self.series_list_changed.emit([])
        self.current_series_changed.emit(None)
        self.series_cleared.emit()
    
    def clear_current_series(self):
        """Clear only the current series selection and emit signal."""
        super().clear_current_series()
        self.current_series_changed.emit(None)
    
    def register_directory_series(self, path: Path, series_list: List[ImageSeries]):
        """Register series as loaded from a directory and emit signals."""
        super().register_directory_series(path, series_list)
        self.series_loaded.emit(series_list)
    
    def remove_series(self, series: ImageSeries) -> bool:
        """Remove a series from the list."""
        if series in self._series_list:
            self._series_list.remove(series)
            self._series_index_map.pop(series.series_uid, None)
            
            # Update current series if it was the one being removed
            if self._current_series == series:
                self._current_series = self._series_list[0] if self._series_list else None
            
            self.series_list_changed.emit(self._series_list.copy())
            self.current_series_changed.emit(self._current_series)
            return True
        return False
    
    def remove_series_by_uid(self, series_uid: str) -> bool:
        """Remove a series by its UID."""
        series = self.get_series_by_uid(series_uid)
        if series:
            return self.remove_series(series)
        return False

    # CRITICAL FIX: Override the current_series property to add signal emission
    # This ensures that direct assignment (manager.current_series = series) emits signals
    @property
    def current_series(self) -> Optional["ImageSeries"]:
        """Get the currently selected series."""
        return self._current_series
    
    @current_series.setter
    def current_series(self, series: Optional["ImageSeries"]):
        """Set current series with signal emission."""
        if series != self._current_series:
            # Call the ImageSeriesManager's set_current_series method directly to avoid double signaling
            ImageSeriesManager.set_current_series(self, series)
            # Emit signal for UI updates
            self.current_series_changed.emit(self._current_series)