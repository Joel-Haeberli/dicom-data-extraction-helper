#!/usr/bin/env python3
"""
Core Image Series Model for DICOM Data Extraction Helper.

This module defines the central data model representing DICOM image series,
which is the foundation of the series-centric architecture.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    # Avoid circular imports by using TYPE_CHECKING
    from .measurement import Measurement

try:
    import pydicom
    from pydicom.dataset import Dataset
    HAS_PYDICOM = True
except ImportError:
    HAS_PYDICOM = False
    Dataset = Any


@dataclass
class ImageSlice:
    """
    Represents a single DICOM slice within an image series.
    
    Attributes:
        filepath: Path to the DICOM file
        dataset: The pydicom Dataset containing all DICOM metadata
        pixel_array: The 2D numpy array containing pixel data
        slice_index: Position within the series (0-indexed)
        z_position: Z coordinate from ImagePositionPatient
        metadata: Additional extracted metadata as a dictionary
    """
    filepath: Path
    dataset: Optional[Dataset] = None
    pixel_array: Optional[np.ndarray] = None
    slice_index: int = 0
    z_position: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        # Ensure pixel_array is at least 2D
        if self.pixel_array is not None and self.pixel_array.ndim == 0:
            self.pixel_array = None
    
    @property
    def shape(self) -> Tuple[int, int]:
        """Return (height, width) of the pixel array."""
        if self.pixel_array is not None:
            return self.pixel_array.shape
        return (0, 0)
    
    @property
    def has_pixel_data(self) -> bool:
        """Check if this slice has valid pixel data."""
        return self.pixel_array is not None and self.pixel_array.size > 0


@dataclass 
class ImageSeries:
    """
    Central model representing a DICOM image series.
    
    This is the core data structure in the series-centric architecture.
    All viewers and analysis tools operate on ImageSeries objects.
    
    Attributes:
        series_uid: Series Instance UID (0020, 000E)
        study_uid: Study Instance UID (0020, 000D)
        patient_id: Patient ID (0010, 0020)
        series_description: Series Description (0008, 103E)
        modality: Modality (0008, 0060)
        slices: List of ImageSlice objects that make up this series
    """
    series_uid: str
    study_uid: str
    patient_id: str
    series_description: str = ""
    modality: str = ""
    slices: List[ImageSlice] = field(default_factory=list)
    
    # Additional metadata
    study_date: str = ""
    study_time: str = ""
    patient_name: str = ""
    
    # Measurement storage
    _measurements: List[Any] = field(default_factory=list, repr=False)
    
    # Volume data (can be cached)
    _volume_cache: Optional[np.ndarray] = field(default=None, repr=False)
    
    # Sort slices by z_position when adding
    def add_slice(self, slice_obj: ImageSlice):
        """Add a slice to the series, maintaining Z-order."""
        self.slices.append(slice_obj)
        # Sort by z_position for consistent ordering
        self.slices.sort(key=lambda s: s.z_position)
        # Invalidate volume cache
        self._volume_cache = None
    
    @property
    def volume(self) -> np.ndarray:
        """Return 3D volume array (z, y, x) by stacking slices."""
        if self._volume_cache is not None:
            return self._volume_cache
        
        if not self.slices:
            return np.array([])
        
        # Sort slices by z_position and stack them
        sorted_slices = sorted(self.slices, key=lambda s: s.z_position)
        
        try:
            # Stack all pixel arrays along the first axis (z)
            volume_data = np.stack([s.pixel_array for s in sorted_slices if s.pixel_array is not None])
            self._volume_cache = volume_data
            return volume_data
        except (ValueError, AttributeError):
            # Handle case where pixel arrays have incompatible shapes
            return np.array([])
    
    @property
    def num_slices(self) -> int:
        """Return the number of slices in this series."""
        return len(self.slices)
    
    @property
    def shape(self) -> Tuple[int, int, int]:
        """Return (depth, height, width) of the volume."""
        if not self.slices:
            return (0, 0, 0)
        
        sample_slice = self.slices[0]
        if sample_slice.pixel_array is not None:
            return (len(self.slices), sample_slice.pixel_array.shape[0], 
                    sample_slice.pixel_array.shape[1])
        return (len(self.slices), 0, 0)
    
    @property
    def slice_shape(self) -> Tuple[int, int]:
        """Return (height, width) of individual slices."""
        if self.slices:
            return self.slices[0].shape
        return (0, 0)
    
    @property
    def z_positions(self) -> List[float]:
        """Return list of Z positions for all slices."""
        return [slice_obj.z_position for slice_obj in self.slices]
    
    @property
    def sorted_slices(self) -> List[ImageSlice]:
        """Return slices sorted by Z position."""
        return sorted(self.slices, key=lambda s: s.z_position)
    
    def get_slice(self, index: int) -> Optional[ImageSlice]:
        """Get slice by index (0-indexed)."""
        if 0 <= index < len(self.slices):
            return self.sorted_slices[index]
        return None
    
    def get_slice_at_z(self, z_position: float, tolerance: float = 0.1) -> Optional[ImageSlice]:
        """Get slice closest to specific Z position."""
        if not self.slices:
            return None
        
        # Find closest slice to z_position
        closest_slice = None
        min_distance = float('inf')
        
        for slice_obj in self.slices:
            distance = abs(slice_obj.z_position - z_position)
            if distance < min_distance and distance <= tolerance:
                min_distance = distance
                closest_slice = slice_obj
        
        return closest_slice
    
    def get_slice_by_index_in_sorted_order(self, index: int) -> Optional[ImageSlice]:
        """Get slice by index in the sorted (Z-ordered) list."""
        sorted_slices = self.sorted_slices
        if 0 <= index < len(sorted_slices):
            return sorted_slices[index]
        return None
    
    def clear_volume_cache(self):
        """Clear the cached volume data."""
        self._volume_cache = None
    
    # Measurement methods
    @property
    def measurements(self) -> List[Any]:
        """Get all measurements for this series."""
        return self._measurements.copy()
    
    def add_measurement(self, measurement: Any):
        """Add a measurement to this series."""
        self._measurements.append(measurement)
        
    def remove_measurement(self, measurement_id: str) -> bool:
        """Remove a measurement by ID."""
        initial_count = len(self._measurements)
        self._measurements = [m for m in self._measurements 
                           if not hasattr(m, 'measurement_id') or m.measurement_id != measurement_id]
        return len(self._measurements) < initial_count
    
    def clear_measurements(self):
        """Clear all measurements from this series."""
        self._measurements.clear()
    
    def get_measurements_by_slice(self, slice_index: int) -> List[Any]:
        """Get measurements for a specific slice."""
        return [m for m in self._measurements 
                if hasattr(m, 'slice_index') and m.slice_index == slice_index]
    
    def get_measurement_count(self) -> int:
        """Get the number of measurements in this series."""
        return len(self._measurements)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert series metadata to a dictionary."""
        return {
            'series_uid': self.series_uid,
            'study_uid': self.study_uid,
            'patient_id': self.patient_id,
            'series_description': self.series_description,
            'modality': self.modality,
            'num_slices': self.num_slices,
            'shape': self.shape,
            'slice_shape': self.slice_shape,
            'study_date': self.study_date,
            'study_time': self.study_time,
            'patient_name': self.patient_name,
            'measurement_count': self.get_measurement_count(),
        }


class ImageSeriesManager:
    """
    Manages loading and selection of image series.
    
    This class is responsible for:
    - Loading DICOM series from directories
    - Managing multiple loaded series
    - Tracking the currently selected series
    - Providing access to available series
    """
    
    def __init__(self):
        self._series_list: List[ImageSeries] = []
        self._current_series: Optional[ImageSeries] = None
        self._loaded_directories: Dict[Path, List[ImageSeries]] = {}
        self._series_index_map: Dict[str, ImageSeries] = {}  # series_uid -> ImageSeries
    
    @property
    def current_series(self) -> Optional[ImageSeries]:
        """Get the currently selected series."""
        return self._current_series
    
    @property
    def available_series(self) -> List[ImageSeries]:
        """Get list of all loaded series."""
        return self._series_list.copy()
    
    @property
    def has_series(self) -> bool:
        """Check if any series are loaded."""
        return len(self._series_list) > 0
    
    @property
    def current_series_index(self) -> Optional[int]:
        """Get the index of the current series in the available series list."""
        if self._current_series is None:
            return None
        try:
            return self._series_list.index(self._current_series)
        except ValueError:
            return None
    
    def load_series_list(self, series_list: List[ImageSeries]):
        """Load a list of series, replacing current list."""
        self._series_list = series_list.copy()
        self._series_index_map.clear()
        
        for series in series_list:
            self._series_index_map[series.series_uid] = series
        
        # Set current series to first if available
        if series_list:
            self._current_series = series_list[0]
        else:
            self._current_series = None
    
    def add_series_list(self, series_list: List[ImageSeries]):
        """Add series to the current list."""
        self._series_list.extend(series_list)
        
        for series in series_list:
            self._series_index_map[series.series_uid] = series
    
    def set_current_series(self, series: ImageSeries):
        """Set the currently selected series."""
        if series in self._series_list or series.series_uid in self._series_index_map:
            self._current_series = series
        else:
            # If series is not in our list, add it
            self._series_list.append(series)
            self._series_index_map[series.series_uid] = series
            self._current_series = series
    
    def set_current_series_by_index(self, index: int):
        """Set current series by index."""
        if 0 <= index < len(self._series_list):
            self._current_series = self._series_list[index]
    
    def set_current_series_by_uid(self, series_uid: str):
        """Set current series by Series UID."""
        if series_uid in self._series_index_map:
            self._current_series = self._series_index_map[series_uid]
    
    def get_series_by_uid(self, series_uid: str) -> Optional[ImageSeries]:
        """Get a series by its UID."""
        return self._series_index_map.get(series_uid)
    
    def clear(self):
        """Clear all loaded series."""
        self._series_list.clear()
        self._series_index_map.clear()
        self._loaded_directories.clear()
        self._current_series = None
    
    def clear_current_series(self):
        """Clear only the current series selection."""
        self._current_series = None
    
    def get_series_for_directory(self, path: Path) -> List[ImageSeries]:
        """Get series loaded from a specific directory."""
        return self._loaded_directories.get(path, [])
    
    def register_directory_series(self, path: Path, series_list: List[ImageSeries]):
        """Register series as loaded from a directory."""
        self._loaded_directories[path] = series_list.copy()