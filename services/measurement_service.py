#!/usr/bin/env python3
"""
Measurement Service for DICOM Data Extraction Helper.

This service provides measurement operations on ImageSeries data, separate from the UI components.
It handles ROI measurements, statistics calculation, and measurement management.
"""

from typing import Optional, List, Dict, Any, Tuple, Union
import numpy as np
from pathlib import Path

try:
    from models.image_series import ImageSeries, ImageSlice
    from models.measurement import Measurement, MeasurementCollection
    HAS_MODELS = True
except ImportError:
    HAS_MODELS = False
    ImageSeries = Any
    ImageSlice = Any
    Measurement = Any
    MeasurementCollection = Any


class MeasurementService:
    """
    Service for performing measurement operations on ImageSeries data.
    
    This service provides:
    - ROI measurements with various shapes
    - Automatic statistics calculation
    - HU conversion for measurements
    - Measurement collection management
    - Measurement storage and retrieval
    - Cursor size configuration and mouse wheel support
    - Measurement mode state management
    - Coordinated cursor positioning support
    """
    
    def __init__(self):
        """Initialize the measurement service."""
        self._measurement_collection = MeasurementCollection()
        
        # Measurement mode state
        self._measurement_mode_enabled = False
        self._cursor_size = 3  # Default cursor size
        self._roi_form = 'square'  # Default ROI form (square, circle, cross)
        self._cursor_position = (0, 0)  # Current cursor position (x, y)
        self._current_slice_index = 0  # Current slice index for measurements
        
        # Cursor position history for coordination
        self._cursor_position_history = []
        self._max_history_size = 10
    
    @property
    def measurements(self) -> List[Measurement]:
        """Get all measurements."""
        return self._measurement_collection.measurements
    
    @property
    def measurement_collection(self) -> MeasurementCollection:
        """Get the measurement collection."""
        return self._measurement_collection
    
    def create_roi_measurement(self, series: ImageSeries, slice_index: int,
                             x: int, y: int, size: int = 3,
                             roi_form: str = 'square', name: str = 'ROI Measurement',
                             study_uid: Optional[str] = None,
                             series_uid: Optional[str] = None,
                             slope: float = 1.0, intercept: float = 0.0) -> Optional[Measurement]:
        """
        Create a measurement for a region of interest (ROI) on a slice.
        
        Args:
            series: ImageSeries containing the slice
            slice_index: Index of the slice to measure
            x: X coordinate of ROI center
            y: Y coordinate of ROI center
            size: Size of the ROI (diameter for circle, side length for square)
            roi_form: Shape of ROI ('square', 'circle', 'cross')
            name: Name for this measurement
            study_uid: Study UID to associate with measurement
            series_uid: Series UID to associate with measurement
            slope: Rescale slope for HU conversion
            intercept: Rescale intercept for HU conversion
            
        Returns:
            Measurement object if successful, None otherwise
        """
        # Get slice and pixel data
        slice_obj = series.get_slice(slice_index)
        if slice_obj is None or slice_obj.pixel_array is None:
            return None
        
        pixel_array = slice_obj.pixel_array
        
        # Calculate ROI statistics
        roi_statistics = self._calculate_roi_statistics(
            pixel_array, x, y, size, roi_form
        )
        
        if roi_statistics is None:
            return None
        
        # Calculate HU statistics
        hu_statistics = self._calculate_hu_statistics(
            roi_statistics, slope, intercept
        )
        
        # Combine statistics
        all_statistics = {**roi_statistics, **hu_statistics}
        
        # Get metadata from slice
        metadata = slice_obj.metadata.copy()
        metadata.update({
            'slope': slope,
            'intercept': intercept,
            'roi_form': roi_form,
            'roi_size': size
        })
        
        # Create measurement
        measurement = Measurement(
            name=name,
            position=(x, y),
            slice_index=slice_index,
            z_position=slice_obj.z_position,
            value=all_statistics['mean'],  # Primary value is mean
            metadata=metadata,
            statistics=all_statistics,
            study_uid=study_uid or series.study_uid,
            series_uid=series_uid or series.series_uid,
            roi_size=size,
            roi_form=roi_form,
            window_center=slope if 'WindowCenter' not in metadata else metadata.get('WindowCenter'),
            window_width=intercept if 'WindowWidth' not in metadata else metadata.get('WindowWidth'),
            mm_per_pixel=self._get_mm_per_pixel(slice_obj)
        )
        
        # Add to collection
        self._measurement_collection.add_measurement(measurement)
        
        return measurement
    
    def _calculate_roi_statistics(self, pixel_array: np.ndarray, x: int, y: int,
                                  size: int, roi_form: str) -> Optional[Dict[str, float]]:
        """Calculate statistics for a region of interest."""
        try:
            height, width = pixel_array.shape
            
            if roi_form == 'square':
                roi, x_start, y_start = self._extract_square_roi(pixel_array, x, y, size)
            elif roi_form == 'circle':
                roi, x_start, y_start = self._extract_circular_roi(pixel_array, x, y, size)
            elif roi_form == 'cross':
                roi, x_start, y_start = self._extract_cross_roi(pixel_array, x, y, size)
            else:
                roi, x_start, y_start = self._extract_square_roi(pixel_array, x, y, size)
            
            if roi is None or roi.size == 0:
                return None
            
            return {
                'raw_mean': float(np.mean(roi)),
                'raw_std': float(np.std(roi)),
                'raw_min': float(np.min(roi)),
                'raw_max': float(np.max(roi)),
                'raw_sum': float(np.sum(roi)),
                'raw_median': float(np.median(roi)) if roi.size > 0 else 0.0,
                'pixel_count': int(roi.size),
                'x': x, 'y': y,
                'roi_width': roi.shape[1] if len(roi.shape) > 1 else 1,
                'roi_height': roi.shape[0] if len(roi.shape) > 0 else 1
            }
            
        except Exception as e:
            print(f"Error calculating ROI statistics: {e}")
            return None
    
    def _calculate_hu_statistics(self, roi_stats: Dict[str, Any], 
                                slope: float, intercept: float) -> Dict[str, float]:
        """Calculate HU statistics from raw statistics."""
        return {
            'hu_mean': roi_stats['raw_mean'] * slope + intercept,
            'hu_std': roi_stats['raw_std'] * slope,
            'hu_min': roi_stats['raw_min'] * slope + intercept,
            'hu_max': roi_stats['raw_max'] * slope + intercept,
            'hu_sum': roi_stats['raw_sum'] * slope + intercept * roi_stats['pixel_count'],
            'hu_median': roi_stats['raw_median'] * slope + intercept,
            'slope': slope,
            'intercept': intercept
        }
    
    def _extract_square_roi(self, pixel_array: np.ndarray, x: int, y: int, 
                          size: int) -> Tuple[Optional[np.ndarray], int, int]:
        """Extract a square ROI centered at (x, y)."""
        height, width = pixel_array.shape
        
        # Calculate bounds
        half_size = size // 2
        x_start = max(0, x - half_size)
        x_end = min(width, x + half_size + (1 if size % 2 != 0 else 0))
        y_start = max(0, y - half_size)
        y_end = min(height, y + half_size + (1 if size % 2 != 0 else 0))
        
        if x_end <= x_start or y_end <= y_start:
            return None, 0, 0
        
        roi = pixel_array[y_start:y_end, x_start:x_end]
        return roi, x_start, y_start
    
    def _extract_circular_roi(self, pixel_array: np.ndarray, x: int, y: int,
                            diameter: int) -> Tuple[Optional[np.ndarray], int, int]:
        """Extract a circular ROI centered at (x, y)."""
        radius = diameter / 2.0
        
        # Create square region around center
        half_size = int(np.ceil(diameter / 2))
        x_start = max(0, x - half_size)
        x_end = min(pixel_array.shape[1], x + half_size + 1)
        y_start = max(0, y - half_size)
        y_end = min(pixel_array.shape[0], y + half_size + 1)
        
        if x_end <= x_start or y_end <= y_start:
            return None, 0, 0
        
        # Extract square region
        square_roi = pixel_array[y_start:y_end, x_start:x_end]
        
        # Create circular mask
        center_x = (x_end - x_start) / 2.0
        center_y = (y_end - y_start) / 2.0
        
        yy, xx = np.ogrid[:square_roi.shape[0], :square_roi.shape[1]]
        mask = (xx - center_x + 0.5)**2 + (yy - center_y + 0.5)**2 <= radius**2
        
        # Apply mask
        if np.any(mask):
            circular_roi = square_roi[mask]
            return circular_roi, x_start, y_start
        else:
            return None, 0, 0
    
    def _extract_cross_roi(self, pixel_array: np.ndarray, x: int, y: int,
                          size: int) -> Tuple[Optional[np.ndarray], int, int]:
        """Extract a cross-shaped ROI centered at (x, y)."""
        half_size = size // 2
        
        # Create cross mask
        height, width = pixel_array.shape
        y_min = max(0, y - half_size)
        y_max = min(height, y + half_size + 1)
        x_min = max(0, x - half_size)
        x_max = min(width, x + half_size + 1)
        
        if y_max <= y_min or x_max <= x_min:
            return None, 0, 0
        
        # Create a cross shape (horizontal and vertical lines)
        cross_mask = np.zeros((y_max - y_min, x_max - x_min), dtype=bool)
        
        # Vertical line
        center_x = half_size
        cross_mask[:, center_x] = True
        
        # Horizontal line
        center_y = half_size
        cross_mask[center_y, :] = True
        
        # Apply mask to pixel array
        roi_region = pixel_array[y_min:y_max, x_min:x_max]
        cross_pixels = roi_region[cross_mask]
        
        return cross_pixels, x_min, y_min
    
    def _get_mm_per_pixel(self, slice_obj: ImageSlice) -> float:
        """Get millimeters per pixel from slice metadata."""
        try:
            metadata = slice_obj.metadata
            if 'PixelSpacing' in metadata:
                spacing = metadata['PixelSpacing']
                if isinstance(spacing, (list, tuple)) and len(spacing) >= 1:
                    return float(spacing[0])  # Row spacing
                elif isinstance(spacing, str):
                    parts = spacing.split('\\')
                    if len(parts) >= 1:
                        return float(parts[0])
            return 0.0
        except (ValueError, TypeError):
            return 0.0
    
    def create_profile_measurement(self, series: ImageSeries, slice_index: int,
                                   start_pos: Tuple[int, int], end_pos: Tuple[int, int],
                                   profile_width: int = 1,
                                   name: str = 'Profile Measurement',
                                   slope: float = 1.0, intercept: float = 0.0) -> Optional[Measurement]:
        """
        Create a profile measurement along a line between two points.
        
        Args:
            series: ImageSeries containing the slice
            slice_index: Index of the slice to measure
            start_pos: (x, y) start position of profile
            end_pos: (x, y) end position of profile
            profile_width: Width of the profile line in pixels
            name: Name for this measurement
            slope: Rescale slope for HU conversion
            intercept: Rescale intercept for HU conversion
            
        Returns:
            Measurement object if successful, None otherwise
        """
        slice_obj = series.get_slice(slice_index)
        if slice_obj is None or slice_obj.pixel_array is None:
            return None
        
        pixel_array = slice_obj.pixel_array
        start_x, start_y = start_pos
        end_x, end_y = end_pos
        
        # Extract profile pixels
        profile_pixels = self._extract_profile_pixels(
            pixel_array, start_x, start_y, end_x, end_y, profile_width
        )
        
        if profile_pixels is None or profile_pixels.size == 0:
            return None
        
        # Calculate statistics
        profile_stats = {
            'raw_mean': float(np.mean(profile_pixels)),
            'raw_std': float(np.std(profile_pixels)),
            'raw_min': float(np.min(profile_pixels)),
            'raw_max': float(np.max(profile_pixels)),
            'raw_sum': float(np.sum(profile_pixels)),
            'raw_median': float(np.median(profile_pixels)),
            'pixel_count': int(profile_pixels.size),
            'profile_length': float(np.sqrt((end_x - start_x)**2 + (end_y - start_y)**2)),
            'start_x': start_x, 'start_y': start_y,
            'end_x': end_x, 'end_y': end_y
        }
        
        # Calculate HU statistics
        hu_stats = self._calculate_hu_statistics(profile_stats, slope, intercept)
        all_stats = {**profile_stats, **hu_stats}
        
        # Create measurement
        measurement = Measurement(
            name=name,
            position=((start_x + end_x) // 2, (start_y + end_y) // 2),  # Midpoint
            slice_index=slice_index,
            z_position=slice_obj.z_position,
            value=all_stats['raw_mean'],
            metadata={'slope': slope, 'intercept': intercept, 'profile_width': profile_width},
            statistics=all_stats,
            study_uid=series.study_uid,
            series_uid=series.series_uid,
            roi_size=profile_width,
            roi_form='profile',
            mm_per_pixel=self._get_mm_per_pixel(slice_obj)
        )
        
        self._measurement_collection.add_measurement(measurement)
        return measurement
    
    def _extract_profile_pixels(self, pixel_array: np.ndarray, start_x: int, start_y: int,
                               end_x: int, end_y: int, width: int) -> Optional[np.ndarray]:
        """Extract pixels along a line profile."""
        try:
            height, width = pixel_array.shape
            
            # Use Bresenham's line algorithm to get points along the line
            line_points = self._get_line_points(start_x, start_y, end_x, end_y)
            
            if not line_points:
                return None
            
            # Collect pixels along the line
            profile_pixels = []
            
            for x, y in line_points:
                # Check bounds
                if 0 <= y < height and 0 <= x < width:
                    profile_pixels.append(pixel_array[y, x])
            
            if not profile_pixels:
                return None
            
            return np.array(profile_pixels)
            
        except Exception as e:
            print(f"Error extracting profile pixels: {e}")
            return None
    
    def _get_line_points(self, x0: int, y0: int, x1: int, y1: int) -> List[Tuple[int, int]]:
        """Get points along a line using Bresenham's algorithm."""
        points = []
        is_steep = abs(y1 - y0) > abs(x1 - x0)
        
        if is_steep:
            x0, y0 = y0, x0
            x1, y1 = y1, x1
        
        rev = False
        if x0 > x1:
            x0, x1 = x1, x0
            y0, y1 = y1, y0
            rev = True
        
        delta_x = x1 - x0
        delta_y = abs(y1 - y0)
        error = int(delta_x / 2)
        y = y0
        y_step = None
        
        if y0 < y1:
            y_step = 1
        else:
            y_step = -1
        
        for x in range(x0, x1 + 1):
            if is_steep:
                points.append((y, x))
            else:
                points.append((x, y))
            
            error -= delta_y
            if error < 0:
                y += y_step
                error += delta_x
        
        if rev:
            points.reverse()
        
        return points
    
    def create_point_measurement(self, series: ImageSeries, slice_index: int,
                                 x: int, y: int, name: str = 'Point Measurement',
                                 slope: float = 1.0, intercept: float = 0.0) -> Optional[Measurement]:
        """
        Create a measurement for a single pixel.
        
        Args:
            series: ImageSeries containing the slice
            slice_index: Index of the slice to measure
            x: X coordinate of pixel
            y: Y coordinate of pixel
            name: Name for this measurement
            slope: Rescale slope for HU conversion
            intercept: Rescale intercept for HU conversion
            
        Returns:
            Measurement object if successful, None otherwise
        """
        slice_obj = series.get_slice(slice_index)
        if slice_obj is None or slice_obj.pixel_array is None:
            return None
        
        pixel_array = slice_obj.pixel_array
        
        # Check bounds
        if 0 <= y < pixel_array.shape[0] and 0 <= x < pixel_array.shape[1]:
            pixel_value = float(pixel_array[y, x])
            hu_value = pixel_value * slope + intercept
        else:
            return None
        
        # Create measurement
        measurement = Measurement(
            name=name,
            position=(x, y),
            slice_index=slice_index,
            z_position=slice_obj.z_position,
            value=pixel_value,
            metadata={'slope': slope, 'intercept': intercept},
            statistics={
                'raw_mean': pixel_value,
                'raw_std': 0.0,
                'raw_min': pixel_value,
                'raw_max': pixel_value,
                'raw_sum': pixel_value,
                'raw_median': pixel_value,
                'hu_mean': hu_value,
                'hu_std': 0.0,
                'hu_min': hu_value,
                'hu_max': hu_value,
                'hu_sum': hu_value,
                'pixel_count': 1,
                'slope': slope,
                'intercept': intercept
            },
            study_uid=series.study_uid,
            series_uid=series.series_uid,
            roi_size=1,
            roi_form='point',
            mm_per_pixel=self._get_mm_per_pixel(slice_obj)
        )
        
        self._measurement_collection.add_measurement(measurement)
        return measurement
    
    def remove_measurement(self, measurement_id: str) -> bool:
        """Remove a measurement by ID."""
        return self._measurement_collection.remove_measurement(measurement_id)
    
    def remove_measurement_by_index(self, index: int) -> bool:
        """Remove a measurement by index."""
        return self._measurement_collection.remove_measurement_by_index(index)
    
    def clear_all_measurements(self):
        """Clear all measurements."""
        self._measurement_collection.clear()
    
    def get_measurements_for_series(self, series_uid: str) -> List[Measurement]:
        """Get all measurements for a specific series."""
        return self._measurement_collection.get_measurements_by_series(series_uid)
    
    def get_measurements_for_study(self, study_uid: str) -> List[Measurement]:
        """Get all measurements for a specific study."""
        return self._measurement_collection.get_measurements_by_study(study_uid)
    
    def get_measurements_for_slice(self, series_uid: str, slice_index: int) -> List[Measurement]:
        """Get all measurements for a specific slice in a series."""
        return self._measurement_collection.get_measurements_by_slice(series_uid, slice_index)
    
    def get_measurement_by_id(self, measurement_id: str) -> Optional[Measurement]:
        """Get a specific measurement by its ID."""
        return self._measurement_collection.get_measurement_by_id(measurement_id)
    
    def update_measurement_name(self, measurement_id: str, new_name: str) -> bool:
        """Update the name of a measurement."""
        measurement = self._measurement_collection.get_measurement_by_id(measurement_id)
        if measurement:
            measurement.name = new_name
            return True
        return False
    
    def update_measurement_notes(self, measurement_id: str, new_notes: str) -> bool:
        """Update the notes of a measurement."""
        measurement = self._measurement_collection.get_measurement_by_id(measurement_id)
        if measurement:
            measurement.notes = new_notes
            return True
        return False
    
    def import_measurements_from_json(self, json_data: Union[str, List[Dict[str, Any]]]) -> int:
        """
        Import measurements from JSON data.
        
        Args:
            json_data: JSON string or list of measurement dictionaries
            
        Returns:
            Number of measurements imported
        """
        try:
            if isinstance(json_data, str):
                import json
                measurements_data = json.loads(json_data)
            else:
                measurements_data = json_data
            
            if not isinstance(measurements_data, list):
                measurements_data = [measurements_data]
            
            count = 0
            for measurement_data in measurements_data:
                measurement = Measurement.from_dict(measurement_data)
                self._measurement_collection.add_measurement(measurement)
                count += 1
            
            return count
            
        except Exception as e:
            print(f"Error importing measurements: {e}")
            return 0
    
    def get_measurement_statistics_summary(self, series_uid: Optional[str] = None) -> Dict[str, Any]:
        """
        Get summary statistics for all measurements, optionally filtered by series.
        
        Args:
            series_uid: Optional series UID to filter by
            
        Returns:
            Dictionary with summary statistics
        """
        measurements = self._measurement_collection.measurements
        if series_uid:
            measurements = [m for m in measurements if m.series_uid == series_uid]
        
        if not measurements:
            return {
                'count': 0,
                'mean_hu': 0.0, 'std_hu': 0.0, 'min_hu': 0.0, 'max_hu': 0.0,
                'mean_raw': 0.0, 'std_raw': 0.0, 'min_raw': 0.0, 'max_raw': 0.0
            }
        
        # Collect all HU and raw values
        hu_values = [m.hu_mean for m in measurements]
        raw_values = [m.raw_mean for m in measurements]
        
        return {
            'count': len(measurements),
            'mean_hu': float(np.mean(hu_values)) if hu_values else 0.0,
            'std_hu': float(np.std(hu_values)) if hu_values else 0.0,
            'min_hu': float(np.min(hu_values)) if hu_values else 0.0,
            'max_hu': float(np.max(hu_values)) if hu_values else 0.0,
            'mean_raw': float(np.mean(raw_values)) if raw_values else 0.0,
            'std_raw': float(np.std(raw_values)) if raw_values else 0.0,
            'min_raw': float(np.min(raw_values)) if raw_values else 0.0,
            'max_raw': float(np.max(raw_values)) if raw_values else 0.0
        }
    
    def find_duplicate_measurements(self, tolerance: float = 0.1) -> List[List[Measurement]]:
        """
        Find measurements that are very close to each other (potential duplicates).
        
        Args:
            tolerance: Maximum distance (in pixels) to consider as duplicate
            
        Returns:
            List of lists, where each inner list contains measurements that are duplicates
        """
        measurements = self._measurement_collection.measurements
        duplicates = []
        used_indices = set()
        
        for i, m1 in enumerate(measurements):
            if i in used_indices:
                continue
            
            group = [m1]
            for j, m2 in enumerate(measurements[i+1:], i+1):
                if j in used_indices:
                    continue
                
                # Check if measurements are on same series and slice
                if (m1.series_uid == m2.series_uid and 
                    m1.slice_index == m2.slice_index):
                    
                    # Calculate distance between positions
                    dx = m1.x - m2.x
                    dy = m1.y - m2.y
                    distance = np.sqrt(dx*dx + dy*dy)
                    
                    if distance <= tolerance:
                        group.append(m2)
                        used_indices.add(j)
            
            if len(group) > 1:
                duplicates.append(group)
                used_indices.add(i)
        
        return duplicates
    
    # Measurement mode state properties
    @property
    def measurement_mode_enabled(self) -> bool:
        """Check if measurement mode is enabled."""
        return self._measurement_mode_enabled
    
    @measurement_mode_enabled.setter
    def measurement_mode_enabled(self, enabled: bool):
        """Enable or disable measurement mode."""
        self._measurement_mode_enabled = enabled
    
    @property
    def cursor_size(self) -> int:
        """Get the current cursor size."""
        return self._cursor_size
    
    @cursor_size.setter
    def cursor_size(self, size: int):
        """Set the cursor size."""
        self._cursor_size = max(1, min(size, 20))  # Clamp between 1 and 20
    
    @property
    def roi_form(self) -> str:
        """Get the current ROI form."""
        return self._roi_form
    
    @roi_form.setter
    def roi_form(self, form: str):
        """Set the ROI form."""
        if form in ['square', 'circle', 'cross', 'point']:
            self._roi_form = form
    
    @property
    def cursor_position(self) -> Tuple[int, int]:
        """Get the current cursor position."""
        return self._cursor_position
    
    @cursor_position.setter
    def cursor_position(self, position: Tuple[int, int]):
        """Set the cursor position."""
        self._cursor_position = position
        # Add to history for coordination
        self._add_to_cursor_history(position)
    
    @property
    def current_slice_index(self) -> int:
        """Get the current slice index for measurements."""
        return self._current_slice_index
    
    @current_slice_index.setter
    def current_slice_index(self, index: int):
        """Set the current slice index for measurements."""
        self._current_slice_index = index
    
    def _add_to_cursor_history(self, position: Tuple[int, int]):
        """Add a cursor position to history."""
        self._cursor_position_history.append(position)
        # Limit history size
        if len(self._cursor_position_history) > self._max_history_size:
            self._cursor_position_history = self._cursor_position_history[-self._max_history_size:]
    
    def increase_cursor_size(self, delta: int = 1):
        """Increase cursor size (for mouse wheel support)."""
        self.cursor_size = self._cursor_size + delta
        return self._cursor_size
    
    def decrease_cursor_size(self, delta: int = 1):
        """Decrease cursor size (for mouse wheel support)."""
        self.cursor_size = self._cursor_size - delta
        return self._cursor_size
    
    def cycle_roi_form(self) -> str:
        """Cycle through available ROI forms."""
        forms = ['square', 'circle', 'cross']
        current_index = forms.index(self._roi_form)
        next_index = (current_index + 1) % len(forms)
        self.roi_form = forms[next_index]
        return self._roi_form
    
    def set_measurement_mode_parameters(self, enabled: bool, cursor_size: int, 
                                        roi_form: str = 'square', 
                                        position: Optional[Tuple[int, int]] = None):
        """
        Set multiple measurement mode parameters at once.
        
        Args:
            enabled: Whether measurement mode is enabled
            cursor_size: Cursor size for measurements
            roi_form: ROI form ('square', 'circle', 'cross')
            position: Current cursor position (x, y)
        """
        self.measurement_mode_enabled = enabled
        self.cursor_size = cursor_size
        self.roi_form = roi_form
        if position:
            self.cursor_position = position
    
    def get_measurement_mode_state(self) -> Dict[str, Any]:
        """Get the current measurement mode state as a dictionary."""
        return {
            'enabled': self.measurement_mode_enabled,
            'cursor_size': self.cursor_size,
            'roi_form': self.roi_form,
            'cursor_position': self.cursor_position,
            'slice_index': self.current_slice_index
        }
    
    def capture_measurement_at_cursor(self, series: ImageSeries, 
                                      slope: float = 1.0, 
                                      intercept: float = 0.0,
                                      name: str = 'ROI Measurement') -> Optional[Measurement]:
        """
        Capture a measurement at the current cursor position.
        
        This is a convenience method that uses the current cursor position,
        size, and ROI form to create a measurement.
        
        Args:
            series: ImageSeries to capture measurement from
            slope: Rescale slope for HU conversion
            intercept: Rescale intercept for HU conversion
            name: Name for this measurement
            
        Returns:
            Measurement object if successful, None otherwise
        """
        x, y = self.cursor_position
        return self.create_roi_measurement(
            series=series,
            slice_index=self.current_slice_index,
            x=x, y=y,
            size=self.cursor_size,
            roi_form=self.roi_form,
            name=name,
            slope=slope,
            intercept=intercept
        )
    
    def coordinate_cursor_position(self, x: int, y: int, slice_index: int,
                                   series_uid: Optional[str] = None) -> bool:
        """
        Coordinate cursor position across multiple viewers.
        
        Args:
            x: X coordinate
            y: Y coordinate  
            slice_index: Slice index
            series_uid: Optional series UID for multi-series coordination
            
        Returns:
            True if coordination was successful
        """
        try:
            self.cursor_position = (x, y)
            self.current_slice_index = slice_index
            # Store series UID if provided for multi-series coordination
            if series_uid:
                # In a full implementation, this would be used to coordinate
                # cursor positions across different series
                pass
            return True
        except Exception as e:
            print(f"Error coordinating cursor position: {e}")
            return False
    
    def get_cursor_statistics(self, series: ImageSeries) -> Optional[Dict[str, Any]]:
        """
        Get statistics for the current cursor position and settings.
        
        Args:
            series: ImageSeries to get statistics from
            
        Returns:
            Dictionary with cursor statistics, or None if failed
        """
        if not series:
            return None
            
        slice_obj = series.get_slice(self.current_slice_index)
        if slice_obj is None or slice_obj.pixel_array is None:
            return None
        
        pixel_array = slice_obj.pixel_array
        x, y = self.cursor_position
        
        # Check bounds
        if 0 <= y < pixel_array.shape[0] and 0 <= x < pixel_array.shape[1]:
            pixel_value = float(pixel_array[y, x])
            
            # Get slope and intercept from metadata or defaults
            slope = slice_obj.metadata.get('RescaleSlope', 1.0)
            intercept = slice_obj.metadata.get('RescaleIntercept', 0.0)
            
            hu_value = pixel_value * slope + intercept
            
            return {
                'x': x, 'y': y, 'slice_index': self.current_slice_index,
                'z_position': slice_obj.z_position,
                'raw_value': pixel_value,
                'hu_value': hu_value,
                'cursor_size': self.cursor_size,
                'roi_form': self.roi_form,
                'slope': slope,
                'intercept': intercept,
                'mm_per_pixel': self._get_mm_per_pixel(slice_obj)
            }
        
        return None