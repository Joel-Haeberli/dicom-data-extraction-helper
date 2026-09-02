#!/usr/bin/env python3
"""
Series Viewer Base Class for DICOM Data Extraction Helper.

This module provides the abstract base class that all series viewers inherit from,
establishing a consistent interface for working with ImageSeries objects.
"""

from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from models.image_series import ImageSeries, ImageSlice

from PySide6.QtCore import Signal, QObject


class SeriesViewerInterface(ABC):
    """
    Abstract interface for series viewers (no Qt dependencies).
    
    This defines the common interface that all series viewers should implement.
    """
    
    @abstractmethod
    def set_series(self, series: Optional['ImageSeries']):
        """Set the series to display."""
        pass
    
    @abstractmethod
    def get_series(self) -> Optional['ImageSeries']:
        """Get the current series."""
        pass
    
    @abstractmethod
    def set_current_slice(self, index: int):
        """Set the current slice index."""
        pass
    
    @abstractmethod
    def get_current_slice(self) -> int:
        """Get the current slice index."""
        pass
    
    @abstractmethod
    def next_slice(self):
        """Navigate to next slice."""
        pass
    
    @abstractmethod
    def prev_slice(self):
        """Navigate to previous slice."""
        pass
    
    @abstractmethod
    def refresh(self):
        """Refresh the display."""
        pass
    
    @abstractmethod
    def clear(self):
        """Clear the current series."""
        pass


class SeriesViewer(QObject):
    """
    Base class for all image series viewers with Qt support.
    
    This class provides a consistent interface for all viewers
    that display and interact with ImageSeries data. All viewers should
    inherit from this class.
    
    Features:
    - Series property with automatic slice change handling
    - Current slice navigation (next/previous)
    - Signal emission for series and slice changes
    - Common interface for all viewers
    
    Signals:
        series_changed: Emitted when the series is changed
        slice_changed: Emitted when the current slice changes
        navigation_requested: Emitted when navigation is requested (for coordination)
    """
    
    # Signals
    series_changed = Signal(object)  # Emitted with new ImageSeries
    slice_changed = Signal(int)      # Emitted with new slice index
    navigation_requested = Signal(str)  # Emitted with 'next' or 'prev'
    
    def __init__(self, parent=None):
        """Initialize the series viewer."""
        super().__init__(parent)
        self._series: Optional[ImageSeries] = None
        self._current_slice: int = 0
    
    @property
    def series(self) -> Optional['ImageSeries']:
        """Get the current series."""
        return self._series
    
    @series.setter
    def series(self, series: Optional['ImageSeries']):
        """Set the current series and trigger updates."""
        if series is not self._series:
            self._series = series
            self._current_slice = 0  # Reset to first slice when series changes
            self._on_series_changed()
            self.series_changed.emit(series)
            # Also emit slice change since we reset to 0
            if series and series.num_slices > 0:
                self.slice_changed.emit(self._current_slice)
    
    @property
    def current_slice(self) -> int:
        """Get the current slice index."""
        return self._current_slice
    
    @current_slice.setter
    def current_slice(self, index: int):
        """Set the current slice index with bounds checking."""
        if self._series:
            # Ensure index is within valid range
            max_slice = max(0, self._series.num_slices - 1)
            new_index = max(0, min(index, max_slice))
            
            if new_index != self._current_slice:
                self._current_slice = new_index
                self._on_slice_changed()
                self.slice_changed.emit(new_index)
        else:
            # No series, reset to 0
            if index != 0:
                self._current_slice = 0
    
    @property
    def current_slice_object(self) -> Optional['ImageSlice']:
        """Get the current ImageSlice object."""
        if self._series:
            return self._series.get_slice(self._current_slice)
        return None
    
    @property
    def has_series(self) -> bool:
        """Check if a series is loaded."""
        return self._series is not None
    
    @property
    def num_slices(self) -> int:
        """Get the number of slices in the current series."""
        if self._series:
            return self._series.num_slices
        return 0
    
    @property
    def can_go_next(self) -> bool:
        """Check if we can navigate to the next slice."""
        if self._series:
            return self._current_slice < self._series.num_slices - 1
        return False
    
    @property
    def can_go_prev(self) -> bool:
        """Check if we can navigate to the previous slice."""
        return self._current_slice > 0
    
    def next_slice(self):
        """Navigate to the next slice."""
        if self.can_go_next:
            self.current_slice += 1
            self.navigation_requested.emit('next')
    
    def prev_slice(self):
        """Navigate to the previous slice."""
        if self.can_go_prev:
            self.current_slice -= 1
            self.navigation_requested.emit('prev')
    
    def go_to_slice(self, index: int):
        """Go to a specific slice by index."""
        self.current_slice = index
    
    def go_to_first_slice(self):
        """Go to the first slice."""
        self.current_slice = 0
    
    def go_to_last_slice(self):
        """Go to the last slice."""
        if self._series:
            self.current_slice = self._series.num_slices - 1
    
    def _on_series_changed(self):
        """
        Called when series is set.
        
        Subclasses should override this to update their display
        when a new series is loaded.
        """
        pass
    
    def _on_slice_changed(self):
        """
        Called when current slice changes.
        
        Subclasses should override this to update their display
        when the current slice changes.
        """
        pass
    
    def refresh(self):
        """Refresh the viewer display."""
        if self._series:
            self._on_series_changed()
            self._on_slice_changed()
    
    def clear(self):
        """Clear the current series and reset the viewer."""
        self.series = None
        self._current_slice = 0


# Concrete base class for viewers that need to be QWidgets
from PySide6.QtWidgets import QWidget

class SeriesViewerWidget(QWidget):
    """
    Base class for series viewers that are also QWidgets.
    
    This provides a convenient base for most viewer implementations
    that need to be both SeriesViewer and QWidget.
    
    Note: This inherits from QWidget first to ensure proper Qt initialization.
    SeriesViewer functionality is implemented directly in this class.
    """
    
    # Signals
    series_changed = Signal(object)  # Emitted with new ImageSeries
    slice_changed = Signal(int)      # Emitted with new slice index
    navigation_requested = Signal(str)  # Emitted with 'next' or 'prev'
    
    def __init__(self, parent=None, call_setup_widget=True):
        """Initialize the series viewer widget."""
        super().__init__(parent)
        
        # Initialize SeriesViewer state
        self._series: Optional[ImageSeries] = None
        self._current_slice: int = 0
        
        # Set up the widget if requested
        if call_setup_widget:
            self._setup_widget()
    
    @property
    def series(self) -> Optional['ImageSeries']:
        """Get the current series."""
        return self._series
    
    @series.setter
    def series(self, series: Optional['ImageSeries']):
        """Set the current series and trigger updates."""
        if series is not self._series:
            self._series = series
            self._current_slice = 0  # Reset to first slice when series changes
            self._on_series_changed()
            self.series_changed.emit(series)
            # Also emit slice change since we reset to 0
            if series and series.num_slices > 0:
                self.slice_changed.emit(self._current_slice)
    
    @property
    def current_slice(self) -> int:
        """Get the current slice index."""
        return self._current_slice
    
    @current_slice.setter
    def current_slice(self, index: int):
        """Set the current slice index with bounds checking."""
        if self._series:
            # Ensure index is within valid range
            max_slice = max(0, self._series.num_slices - 1)
            new_index = max(0, min(index, max_slice))
            
            if new_index != self._current_slice:
                self._current_slice = new_index
                self._on_slice_changed()
                self.slice_changed.emit(new_index)
        else:
            # No series, reset to 0
            if index != 0:
                self._current_slice = 0
    
    @property
    def current_slice_object(self) -> Optional['ImageSlice']:
        """Get the current ImageSlice object."""
        if self._series:
            return self._series.get_slice(self._current_slice)
        return None
    
    @property
    def has_series(self) -> bool:
        """Check if a series is loaded."""
        return self._series is not None
    
    @property
    def num_slices(self) -> int:
        """Get the number of slices in the current series."""
        if self._series:
            return self._series.num_slices
        return 0
    
    @property
    def can_go_next(self) -> bool:
        """Check if we can navigate to the next slice."""
        if self._series:
            return self._current_slice < self._series.num_slices - 1
        return False
    
    @property
    def can_go_prev(self) -> bool:
        """Check if we can navigate to the previous slice."""
        return self._current_slice > 0
    
    def next_slice(self):
        """Navigate to the next slice."""
        if self.can_go_next:
            self.current_slice += 1
            self.navigation_requested.emit('next')
    
    def prev_slice(self):
        """Navigate to the previous slice."""
        if self.can_go_prev:
            self.current_slice -= 1
            self.navigation_requested.emit('prev')
    
    def go_to_slice(self, index: int):
        """Go to a specific slice by index."""
        self.current_slice = index
    
    def go_to_first_slice(self):
        """Go to the first slice."""
        self.current_slice = 0
    
    def go_to_last_slice(self):
        """Go to the last slice."""
        if self._series:
            self.current_slice = self._series.num_slices - 1
    
    def _on_series_changed(self):
        """
        Called when series is set.
        
        Subclasses should override this to update their display
        when a new series is loaded.
        """
        pass
    
    def _on_slice_changed(self):
        """
        Called when current slice changes.
        
        Subclasses should override this to update their display
        when the current slice changes.
        """
        pass
    
    def refresh(self):
        """Refresh the viewer display."""
        if self._series:
            self._on_series_changed()
            self._on_slice_changed()
    
    def clear(self):
        """Clear the current series and reset the viewer."""
        self.series = None
        self._current_slice = 0
    
    def _setup_widget(self):
        """Setup the widget appearance and layout."""
        # Default implementation does nothing
        # Subclasses should override this
        pass