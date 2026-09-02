#!/usr/bin/env python3
"""
Measurement Model for DICOM Data Extraction Helper.

This module defines the measurement data model for storing ROI measurements
and analysis results on DICOM image series.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
import uuid
import json
from datetime import datetime


@dataclass
class Measurement:
    """
    Represents a measurement on an image series.
    
    A measurement contains:
    - Position information (slice index, x, y coordinates)
    - Statistical data (mean, std, min, max values)
    - Metadata (study info, measurement type, etc.)
    - Unique identifier for tracking
    
    Attributes:
        name: Human-readable name for this measurement
        position: Tuple of (x, y) pixel coordinates
        slice_index: Index of the slice in the series
        z_position: Z coordinate if available
        value: Primary measurement value
        metadata: Additional measurement metadata
        statistics: Dict containing statistical data
        study_uid: Study UID for linking to series
        series_uid: Series UID for linking to series
        created_at: Timestamp when measurement was created
        measurement_id: Unique identifier
        notes: User notes about this measurement
    """
    name: str = "Measurement"
    position: Tuple[int, int] = (0, 0)
    slice_index: int = 0
    z_position: float = 0.0
    value: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    statistics: Dict[str, float] = field(default_factory=dict)
    study_uid: str = ""
    series_uid: str = ""
    created_at: str = ""
    measurement_id: str = ""
    notes: str = ""
    
    # ROI information
    roi_size: int = 0  # Size of the region of interest
    roi_form: str = ""  # Shape/form of the ROI
    
    # Window information for HU measurements
    window_center: Optional[float] = None
    window_width: Optional[float] = None
    
    def __post_init__(self):
        # Generate ID if not provided
        if not self.measurement_id:
            self.measurement_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    @property
    def x(self) -> int:
        """X coordinate of the measurement position."""
        return self.position[0]
    
    @property
    def y(self) -> int:
        """Y coordinate of the measurement position."""
        return self.position[1]
    
    @property
    def raw_mean(self) -> float:
        """Raw mean value from statistics."""
        return self.statistics.get('raw_mean', 0.0)
    
    @property
    def raw_std(self) -> float:
        """Raw standard deviation from statistics."""
        return self.statistics.get('raw_std', 0.0)
    
    @property
    def raw_min(self) -> float:
        """Raw minimum value from statistics."""
        return self.statistics.get('raw_min', 0.0)
    
    @property
    def raw_max(self) -> float:
        """Raw maximum value from statistics."""
        return self.statistics.get('raw_max', 0.0)
    
    @property
    def hu_mean(self) -> float:
        """Hounsfield Unit mean from statistics."""
        return self.statistics.get('hu_mean', 0.0)
    
    @property
    def hu_std(self) -> float:
        """Hounsfield Unit standard deviation from statistics."""
        return self.statistics.get('hu_std', 0.0)
    
    @property
    def hu_min(self) -> float:
        """Hounsfield Unit minimum from statistics."""
        return self.statistics.get('hu_min', 0.0)
    
    @property
    def hu_max(self) -> float:
        """Hounsfield Unit maximum from statistics."""
        return self.statistics.get('hu_max', 0.0)
    
    @property
    def mm_per_pixel(self) -> float:
        """Millimeters per pixel from metadata."""
        return self.metadata.get('mm_per_pixel', 0.0)
    
    def set_raw_statistics(self, mean: float, std: float, min_val: float, max_val: float):
        """Set raw pixel value statistics."""
        self.statistics['raw_mean'] = mean
        self.statistics['raw_std'] = std
        self.statistics['raw_min'] = min_val
        self.statistics['raw_max'] = max_val
    
    def set_hu_statistics(self, mean: float, std: float, min_val: float, max_val: float):
        """Set Hounsfield Unit statistics."""
        self.statistics['hu_mean'] = mean
        self.statistics['hu_std'] = std
        self.statistics['hu_min'] = min_val
        self.statistics['hu_max'] = max_val
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert measurement to dictionary for serialization."""
        return {
            'name': self.name,
            'position': list(self.position),
            'slice_index': self.slice_index,
            'z_position': self.z_position,
            'value': self.value,
            'metadata': self.metadata.copy(),
            'statistics': self.statistics.copy(),
            'study_uid': self.study_uid,
            'series_uid': self.series_uid,
            'created_at': self.created_at,
            'measurement_id': self.measurement_id,
            'notes': self.notes,
            'roi_size': self.roi_size,
            'roi_form': self.roi_form,
            'window_center': self.window_center,
            'window_width': self.window_width,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Measurement':
        """Create measurement from dictionary."""
        return cls(
            name=data.get('name', 'Measurement'),
            position=tuple(data.get('position', [0, 0])),
            slice_index=data.get('slice_index', 0),
            z_position=data.get('z_position', 0.0),
            value=data.get('value', 0.0),
            metadata=data.get('metadata', {}),
            statistics=data.get('statistics', {}),
            study_uid=data.get('study_uid', ''),
            series_uid=data.get('series_uid', ''),
            created_at=data.get('created_at', ''),
            measurement_id=data.get('measurement_id', ''),
            notes=data.get('notes', ''),
            roi_size=data.get('roi_size', 0),
            roi_form=data.get('roi_form', ''),
            window_center=data.get('window_center'),
            window_width=data.get('window_width'),
        )
    
    def to_json(self) -> str:
        """Convert measurement to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Measurement':
        """Create measurement from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)


class MeasurementCollection:
    """
    Collection of measurements for managing multiple measurements.
    
    Provides functionality for:
    - Adding/removing measurements
    - Filtering measurements by study/series
    - Export/import functionality
    """
    
    def __init__(self):
        self._measurements: List[Measurement] = []
    
    @property
    def measurements(self) -> List[Measurement]:
        """Get all measurements."""
        return self._measurements.copy()
    
    @property
    def count(self) -> int:
        """Get number of measurements."""
        return len(self._measurements)
    
    def add_measurement(self, measurement: Measurement) -> Measurement:
        """Add a measurement to the collection."""
        self._measurements.append(measurement)
        return measurement
    
    def remove_measurement(self, measurement_id: str) -> bool:
        """Remove a measurement by ID."""
        initial_count = len(self._measurements)
        self._measurements = [m for m in self._measurements if m.measurement_id != measurement_id]
        return len(self._measurements) < initial_count
    
    def remove_measurement_by_index(self, index: int) -> bool:
        """Remove a measurement by index."""
        if 0 <= index < len(self._measurements):
            self._measurements.pop(index)
            return True
        return False
    
    def clear(self):
        """Clear all measurements."""
        self._measurements.clear()
    
    def get_measurements_by_series(self, series_uid: str) -> List[Measurement]:
        """Get measurements for a specific series."""
        return [m for m in self._measurements if m.series_uid == series_uid]
    
    def get_measurements_by_study(self, study_uid: str) -> List[Measurement]:
        """Get measurements for a specific study."""
        return [m for m in self._measurements if m.study_uid == study_uid]
    
    def get_measurements_by_slice(self, series_uid: str, slice_index: int) -> List[Measurement]:
        """Get measurements for a specific slice in a series."""
        return [m for m in self._measurements 
                if m.series_uid == series_uid and m.slice_index == slice_index]
    
    def get_measurement_by_id(self, measurement_id: str) -> Optional[Measurement]:
        """Get a specific measurement by ID."""
        for measurement in self._measurements:
            if measurement.measurement_id == measurement_id:
                return measurement
        return None
    
    def to_list_of_dicts(self) -> List[Dict[str, Any]]:
        """Convert all measurements to list of dictionaries."""
        return [m.to_dict() for m in self._measurements]
    
    def to_json(self) -> str:
        """Convert all measurements to JSON string."""
        return json.dumps([m.to_dict() for m in self._measurements], indent=2)
    
    def from_json(self, json_str: str):
        """Load measurements from JSON string."""
        data = json.loads(json_str)
        if isinstance(data, list):
            self._measurements = [Measurement.from_dict(d) for d in data]
        else:
            self._measurements = [Measurement.from_dict(data)]
    
    def export_to_csv_row(self, measurement: Measurement) -> Dict[str, Any]:
        """Convert a measurement to a CSV row format."""
        return {
            'study_uid': measurement.study_uid,
            'series_uid': measurement.series_uid,
            'slice_index': measurement.slice_index,
            'z_position': measurement.z_position,
            'x': measurement.x,
            'y': measurement.y,
            'roi_size': measurement.roi_size,
            'roi_form': measurement.roi_form,
            'raw_mean': measurement.raw_mean,
            'raw_std': measurement.raw_std,
            'raw_min': measurement.raw_min,
            'raw_max': measurement.raw_max,
            'hu_mean': measurement.hu_mean,
            'hu_std': measurement.hu_std,
            'hu_min': measurement.hu_min,
            'hu_max': measurement.hu_max,
            'mm_per_pixel': measurement.mm_per_pixel,
            'notes': measurement.notes,
            'created_at': measurement.created_at,
        }