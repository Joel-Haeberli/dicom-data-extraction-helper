#!/usr/bin/env python3
"""
Analysis Service for DICOM Data Extraction Helper.

This service provides analysis operations on ImageSeries data, separate from the UI components.
It represents the business logic layer in the series-centric architecture.
"""

from typing import Optional, List, Dict, Any, Tuple, Union
import numpy as np
from pathlib import Path

try:
    from models.image_series import ImageSeries, ImageSlice
    HAS_MODELS = True
except ImportError:
    HAS_MODELS = False
    ImageSeries = Any
    ImageSlice = Any


class AnalysisService:
    """
    Service for performing analysis operations on ImageSeries data.
    
    This service provides:
    - Statistical analysis of series data
    - ROI analysis and measurements
    - Hounsfield Unit (HU) calculations
    - Series comparison and validation
    - Export-ready data preparation
    """
    
    def __init__(self):
        """Initialize the analysis service."""
        pass
    
    def get_series_statistics(self, series: ImageSeries) -> Dict[str, Any]:
        """
        Calculate comprehensive statistics for an entire series.
        
        Args:
            series: ImageSeries to analyze
            
        Returns:
            Dictionary with series-wide statistics
        """
        if not series or series.num_slices == 0:
            return self._empty_statistics()
        
        # Get volume data
        volume = series.volume
        if volume.size == 0:
            return self._empty_statistics()
        
        stats = {}
        
        # Basic statistics
        stats['num_slices'] = series.num_slices
        stats['shape'] = series.shape
        stats['slice_shape'] = series.slice_shape
        stats['z_positions'] = series.z_positions
        stats['z_spacing'] = self._calculate_z_spacing(series)
        
        # Volume statistics
        stats['volume_mean'] = float(np.mean(volume))
        stats['volume_std'] = float(np.std(volume))
        stats['volume_min'] = float(np.min(volume))
        stats['volume_max'] = float(np.max(volume))
        stats['volume_sum'] = float(np.sum(volume))
        stats['volume_total_voxels'] = int(volume.size)
        
        # Per-slice statistics
        stats['slice_statistics'] = []
        for i, slice_obj in enumerate(series.sorted_slices):
            if slice_obj.pixel_array is not None:
                slice_stats = self._calculate_slice_statistics(slice_obj.pixel_array)
                slice_stats['slice_index'] = i
                slice_stats['z_position'] = slice_obj.z_position
                stats['slice_statistics'].append(slice_stats)
        
        # Series metadata
        stats['series_uid'] = series.series_uid
        stats['study_uid'] = series.study_uid
        stats['patient_id'] = series.patient_id
        stats['series_description'] = series.series_description
        stats['modality'] = series.modality
        stats['patient_name'] = series.patient_name
        stats['study_date'] = series.study_date
        stats['study_time'] = series.study_time
        
        return stats
    
    def _empty_statistics(self) -> Dict[str, Any]:
        """Return empty statistics dictionary."""
        return {
            'num_slices': 0,
            'shape': (0, 0, 0),
            'slice_shape': (0, 0),
            'z_positions': [],
            'z_spacing': 0.0,
            'volume_mean': 0.0,
            'volume_std': 0.0,
            'volume_min': 0.0,
            'volume_max': 0.0,
            'volume_sum': 0.0,
            'volume_total_voxels': 0,
            'slice_statistics': [],
            'series_uid': '',
            'study_uid': '',
            'patient_id': '',
            'series_description': '',
            'modality': '',
            'patient_name': '',
            'study_date': '',
            'study_time': ''
        }
    
    def _calculate_z_spacing(self, series: ImageSeries) -> List[float]:
        """Calculate Z spacing between slices."""
        z_positions = series.z_positions
        if len(z_positions) < 2:
            return []
        
        spacings = []
        for i in range(1, len(z_positions)):
            spacing = abs(z_positions[i] - z_positions[i-1])
            spacings.append(spacing)
        
        return spacings
    
    def _calculate_slice_statistics(self, pixel_array: np.ndarray) -> Dict[str, float]:
        """Calculate statistics for a single slice."""
        return {
            'mean': float(np.mean(pixel_array)),
            'std': float(np.std(pixel_array)),
            'min': float(np.min(pixel_array)),
            'max': float(np.max(pixel_array)),
            'sum': float(np.sum(pixel_array)),
            'num_pixels': int(pixel_array.size)
        }
    
    def get_roi_statistics(self, series: ImageSeries, slice_index: int, 
                          x: int, y: int, width: int, height: int,
                          is_circle: bool = False, diameter: int = 0) -> Dict[str, Any]:
        """
        Calculate statistics for a region of interest (ROI) on a specific slice.
        
        Args:
            series: ImageSeries containing the slice
            slice_index: Index of the slice to analyze
            x: X coordinate of ROI center
            y: Y coordinate of ROI center
            width: Width of ROI
            height: Height of ROI
            is_circle: If True, use circular ROI
            diameter: Diameter of circle if is_circle=True
            
        Returns:
            Dictionary with ROI statistics
        """
        slice_obj = series.get_slice(slice_index)
        if slice_obj is None or slice_obj.pixel_array is None:
            return self._empty_roi_statistics()
        
        pixel_array = slice_obj.pixel_array
        
        # Calculate ROI bounds
        x_start = max(0, x - width // 2)
        x_end = min(pixel_array.shape[1], x + width // 2)
        y_start = max(0, y - height // 2)
        y_end = min(pixel_array.shape[0], y + height // 2)
        
        # Extract ROI
        roi = pixel_array[y_start:y_end, x_start:x_end]
        
        if is_circle and diameter > 0:
            # Create circular mask
            center_x = width / 2.0
            center_y = height / 2.0
            radius = diameter / 2.0
            radius_sq = radius * radius
            
            yy, xx = np.ogrid[:roi.shape[0], :roi.shape[1]]
            mask = (xx + 0.5 - center_x)**2 + (yy + 0.5 - center_y)**2 <= radius_sq
            
            # Apply mask
            roi = roi[mask]
        
        if roi.size == 0:
            return self._empty_roi_statistics()
        
        return {
            'slice_index': slice_index,
            'z_position': slice_obj.z_position,
            'x': x, 'y': y,
            'width': width, 'height': height,
            'is_circle': is_circle,
            'diameter': diameter,
            'pixel_count': int(roi.size),
            'mean': float(np.mean(roi)),
            'std': float(np.std(roi)),
            'min': float(np.min(roi)),
            'max': float(np.max(roi)),
            'sum': float(np.sum(roi)),
            'median': float(np.median(roi)) if roi.size > 0 else 0.0
        }
    
    def _empty_roi_statistics(self) -> Dict[str, Any]:
        """Return empty ROI statistics."""
        return {
            'slice_index': 0,
            'z_position': 0.0,
            'x': 0, 'y': 0,
            'width': 0, 'height': 0,
            'is_circle': False,
            'diameter': 0,
            'pixel_count': 0,
            'mean': 0.0, 'std': 0.0,
            'min': 0.0, 'max': 0.0,
            'sum': 0.0, 'median': 0.0
        }
    
    def apply_hu_conversion(self, series: ImageSeries, slice_index: int = 0,
                           slope: Optional[float] = None, intercept: Optional[float] = None) -> Optional[np.ndarray]:
        """
        Apply Hounsfield Unit conversion to a slice's pixel data.
        
        Args:
            series: ImageSeries containing the slice
            slice_index: Index of the slice to convert
            slope: Rescale slope (from DICOM metadata if None)
            intercept: Rescale intercept (from DICOM metadata if None)
            
        Returns:
            HU-converted numpy array, or None if conversion not possible
        """
        slice_obj = series.get_slice(slice_index)
        if slice_obj is None or slice_obj.pixel_array is None:
            return None
        
        pixel_array = slice_obj.pixel_array
        
        # Try to get slope and intercept from metadata
        if slope is None or intercept is None:
            metadata = slice_obj.metadata
            slope = metadata.get('RescaleSlope', 1.0)
            intercept = metadata.get('RescaleIntercept', 0.0)
            
            # Try to convert from string if needed
            try:
                slope = float(slope) if slope is not None else 1.0
                intercept = float(intercept) if intercept is not None else 0.0
            except (ValueError, TypeError):
                slope = 1.0
                intercept = 0.0
        
        # Apply conversion
        hu_array = pixel_array * slope + intercept
        return hu_array
    
    def calculate_series_hu_statistics(self, series: ImageSeries,
                                     slope: Optional[float] = None,
                                     intercept: Optional[float] = None) -> Dict[str, Any]:
        """
        Calculate HU statistics for all slices in a series.
        
        Args:
            series: ImageSeries to analyze
            slope: Rescale slope (from DICOM if None)
            intercept: Rescale intercept (from DICOM if None)
            
        Returns:
            Dictionary with HU statistics for each slice and series overall
        """
        if not series or series.num_slices == 0:
            return self._empty_statistics()
        
        stats = {}
        hu_values = []
        
        for i, slice_obj in enumerate(series.sorted_slices):
            if slice_obj.pixel_array is not None:
                hu_array = self.apply_hu_conversion(series, i, slope, intercept)
                if hu_array is not None:
                    hu_values.extend(hu_array.flatten())
                    
                    slice_stats = {
                        'slice_index': i,
                        'z_position': slice_obj.z_position,
                        'mean': float(np.mean(hu_array)),
                        'std': float(np.std(hu_array)),
                        'min': float(np.min(hu_array)),
                        'max': float(np.max(hu_array))
                    }
                    if 'slice_hu_statistics' not in stats:
                        stats['slice_hu_statistics'] = []
                    stats['slice_hu_statistics'].append(slice_stats)
        
        if hu_values:
            stats['overall_mean'] = float(np.mean(hu_values))
            stats['overall_std'] = float(np.std(hu_values))
            stats['overall_min'] = float(np.min(hu_values))
            stats['overall_max'] = float(np.max(hu_values))
        else:
            stats.update(self._empty_statistics())
        
        return stats
    
    def validate_series_integrity(self, series: ImageSeries) -> Dict[str, Any]:
        """
        Validate the integrity of a series (consistent shape, spacing, etc.).
        
        Args:
            series: ImageSeries to validate
            
        Returns:
            Dictionary with validation results and any issues found
        """
        validation = {
            'is_valid': True,
            'issues': [],
            'warnings': [],
            'num_slices': series.num_slices,
            'expected_shape': None,
            'actual_shapes': []
        }
        
        if series.num_slices == 0:
            validation['is_valid'] = False
            validation['issues'].append('No slices in series')
            return validation
        
        # Check consistent slice shapes
        expected_shape = series.slice_shape
        validation['expected_shape'] = expected_shape
        
        for i, slice_obj in enumerate(series.sorted_slices):
            if slice_obj.pixel_array is not None:
                shape = slice_obj.pixel_array.shape
                validation['actual_shapes'].append({
                    'slice_index': i,
                    'shape': shape,
                    'matches_expected': shape == expected_shape
                })
                
                if shape != expected_shape:
                    validation['is_valid'] = False
                    validation['issues'].append(
                        f'Slice {i} has shape {shape}, expected {expected_shape}'
                    )
            else:
                validation['is_valid'] = False
                validation['issues'].append(f'Slice {i} has no pixel data')
        
        # Check Z position ordering
        z_positions = series.z_positions
        if z_positions:
            sorted_z = sorted(z_positions)
            if z_positions != sorted_z:
                validation['warnings'].append('Slices are not ordered by Z position')
        
        # Check Z spacing consistency
        z_spacings = self._calculate_z_spacing(series)
        if len(z_spacings) > 1:
            spacing_std = float(np.std(z_spacings))
            spacing_mean = float(np.mean(z_spacings))
            if spacing_std > spacing_mean * 0.1:  # More than 10% variation
                validation['warnings'].append(
                    f'Inconsistent Z spacing (mean: {spacing_mean:.3f}, std: {spacing_std:.3f})'
                )
        
        return validation
    
    def get_series_histogram(self, series: ImageSeries, bins: int = 256,
                            slice_range: Optional[Tuple[int, int]] = None) -> Dict[str, Any]:
        """
        Calculate histogram for a series or slice range.
        
        Args:
            series: ImageSeries to analyze
            bins: Number of histogram bins
            slice_range: Tuple of (start_slice, end_slice) for partial series
            
        Returns:
            Dictionary with histogram data
        """
        if not series or series.num_slices == 0:
            return {'bins': [], 'counts': [], 'range': (0, 0), 'total': 0}
        
        # Determine slice range
        start_slice = slice_range[0] if slice_range else 0
        end_slice = slice_range[1] if slice_range else series.num_slices
        
        # Collect all pixel values
        all_values = []
        for i in range(start_slice, end_slice):
            slice_obj = series.get_slice(i)
            if slice_obj and slice_obj.pixel_array is not None:
                all_values.extend(slice_obj.pixel_array.flatten())
        
        if not all_values:
            return {'bins': [], 'counts': [], 'range': (0, 0), 'total': 0}
        
        # Calculate histogram
        values_array = np.array(all_values)
        counts, bin_edges = np.histogram(values_array, bins=bins)
        
        return {
            'bins': bin_edges.tolist(),
            'counts': counts.tolist(),
            'range': (float(np.min(values_array)), float(np.max(values_array))),
            'total': int(len(all_values)),
            'mean': float(np.mean(values_array)),
            'std': float(np.std(values_array))
        }
    
    def compare_series(self, series1: ImageSeries, series2: ImageSeries) -> Dict[str, Any]:
        """
        Compare two series and return comparison metrics.
        
        Args:
            series1: First series to compare
            series2: Second series to compare
            
        Returns:
            Dictionary with comparison results
        """
        comparison = {
            'series1_uid': series1.series_uid,
            'series2_uid': series2.series_uid,
            'matches': [],
            'differences': [],
            'statistics': {}
        }
        
        # Basic metadata comparison
        if series1.series_uid == series2.series_uid:
            comparison['matches'].append('Series UID')
        else:
            comparison['differences'].append(f'Series UID: {series1.series_uid} vs {series2.series_uid}')
        
        if series1.study_uid == series2.study_uid:
            comparison['matches'].append('Study UID')
        else:
            comparison['differences'].append(f'Study UID: {series1.study_uid} vs {series2.study_uid}')
        
        if series1.patient_id == series2.patient_id:
            comparison['matches'].append('Patient ID')
        else:
            comparison['differences'].append(f'Patient ID: {series1.patient_id} vs {series2.patient_id}')
        
        if series1.modality == series2.modality:
            comparison['matches'].append('Modality')
        else:
            comparison['differences'].append(f'Modality: {series1.modality} vs {series2.modality}')
        
        # Shape comparison
        if series1.shape == series2.shape:
            comparison['matches'].append('Shape')
        else:
            comparison['differences'].append(f'Shape: {series1.shape} vs {series2.shape}')
        
        if series1.num_slices == series2.num_slices:
            comparison['matches'].append('Slice count')
        else:
            comparison['differences'].append(f'Slice count: {series1.num_slices} vs {series2.num_slices}')
        
        # Volume statistics comparison (if both have data)
        if series1.num_slices > 0 and series2.num_slices > 0:
            stats1 = self.get_series_statistics(series1)
            stats2 = self.get_series_statistics(series2)
            
            comparison['statistics'] = {
                'series1': stats1,
                'series2': stats2
            }
        
        return comparison
    
    def create_series_report(self, series: ImageSeries) -> str:
        """
        Create a comprehensive text report for a series.
        
        Args:
            series: ImageSeries to report on
            
        Returns:
            Formatted text report
        """
        stats = self.get_series_statistics(series)
        validation = self.validate_series_integrity(series)
        
        lines = []
        lines.append("=" * 60)
        lines.append("DICOM SERIES ANALYSIS REPORT")
        lines.append("=" * 60)
        
        # Series identification
        lines.append("\nSERIES IDENTIFICATION:")
        lines.append(f"  Series UID: {stats['series_uid']}")
        lines.append(f"  Study UID: {stats['study_uid']}")
        lines.append(f"  Patient ID: {stats['patient_id']}")
        lines.append(f"  Patient Name: {stats['patient_name']}")
        lines.append(f"  Series Description: {stats['series_description']}")
        lines.append(f"  Modality: {stats['modality']}")
        lines.append(f"  Study Date: {stats['study_date']}")
        lines.append(f"  Study Time: {stats['study_time']}")
        
        # Series structure
        lines.append("\nSERIES STRUCTURE:")
        lines.append(f"  Number of Slices: {stats['num_slices']}")
        lines.append(f"  Shape (D, H, W): {stats['shape']}")
        lines.append(f"  Slice Shape (H, W): {stats['slice_shape']}")
        lines.append(f"  Total Voxels: {stats['volume_total_voxels']:,}")
        
        # Z positioning
        if stats['z_positions']:
            lines.append(f"  Z Positions: {len(stats['z_positions'])} positions")
            if len(stats['z_positions']) > 1:
                z_min = min(stats['z_positions'])
                z_max = max(stats['z_positions'])
                lines.append(f"  Z Range: {z_min:.2f} to {z_max:.2f}")
        
        # Validation results
        lines.append("\nVALIDATION:")
        lines.append(f"  Series is valid: {validation['is_valid']}")
        if validation['issues']:
            lines.append(f"  Issues found: {len(validation['issues'])}")
            for issue in validation['issues']:
                lines.append(f"    - {issue}")
        if validation['warnings']:
            lines.append(f"  Warnings: {len(validation['warnings'])}")
            for warning in validation['warnings']:
                lines.append(f"    - {warning}")
        
        # Volume statistics
        lines.append("\nVOLUME STATISTICS:")
        lines.append(f"  Mean: {stats['volume_mean']:.2f}")
        lines.append(f"  Std Dev: {stats['volume_std']:.2f}")
        lines.append(f"  Min: {stats['volume_min']:.2f}")
        lines.append(f"  Max: {stats['volume_max']:.2f}")
        lines.append(f"  Sum: {stats['volume_sum']:.0f}")
        
        # Per-slice statistics (summary)
        if stats['slice_statistics']:
            lines.append("\nPER-SLICE STATISTICS (SUMMARY):")
            slice_means = [s['mean'] for s in stats['slice_statistics']]
            lines.append(f"  Mean values: min={min(slice_means):.2f}, max={max(slice_means):.2f}, mean={np.mean(slice_means):.2f}")
        
        lines.append("\n" + "=" * 60)
        
        return "\n".join(lines)