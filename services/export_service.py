#!/usr/bin/env python3
"""
Export Service for DICOM Data Extraction Helper.

This service provides export functionality for ImageSeries data and analysis results,
separate from the UI components. It handles various export formats and file operations.
"""

import csv
import json
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
import numpy as np

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


class ExportService:
    """
    Service for exporting ImageSeries data and analysis results to various formats.
    
    This service provides:
    - CSV export for measurements and statistics
    - JSON export for series metadata and measurements
    - Pixel data export in various formats
    - Image slice export
    - Batch export operations
    """
    
    def __init__(self):
        """Initialize the export service."""
        pass
    
    def export_measurements_to_csv(self, measurements: List[Measurement], 
                                  file_path: Union[str, Path], 
                                  delimiter: str = ',') -> bool:
        """
        Export measurements to a CSV file.
        
        Args:
            measurements: List of Measurement objects to export
            file_path: Destination file path
            delimiter: CSV delimiter character
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, delimiter=delimiter)
                
                # Write header
                fieldnames = self._get_measurement_fieldnames()
                writer.writeheader(fieldnames)
                
                # Write data rows
                for measurement in measurements:
                    row_data = self._measurement_to_csv_row(measurement)
                    writer.writerow(row_data)
            
            return True
            
        except Exception as e:
            print(f"Error exporting measurements to CSV: {e}")
            return False
    
    def _get_measurement_fieldnames(self) -> List[str]:
        """Get field names for CSV export."""
        return [
            'measurement_id', 'name', 'series_uid', 'study_uid', 'slice_index',
            'z_position', 'x', 'y', 'value', 'roi_size', 'roi_form',
            'raw_mean', 'raw_std', 'raw_min', 'raw_max',
            'hu_mean', 'hu_std', 'hu_min', 'hu_max',
            'window_center', 'window_width', 'mm_per_pixel',
            'notes', 'created_at'
        ]
    
    def _measurement_to_csv_row(self, measurement: Measurement) -> Dict[str, Any]:
        """Convert a Measurement to a CSV row dictionary."""
        return {
            'measurement_id': measurement.measurement_id,
            'name': measurement.name,
            'series_uid': measurement.series_uid,
            'study_uid': measurement.study_uid,
            'slice_index': measurement.slice_index,
            'z_position': measurement.z_position,
            'x': measurement.x,
            'y': measurement.y,
            'value': measurement.value,
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
            'window_center': measurement.window_center or '',
            'window_width': measurement.window_width or '',
            'mm_per_pixel': measurement.mm_per_pixel,
            'notes': measurement.notes,
            'created_at': measurement.created_at
        }
    
    def export_measurement_collection_to_csv(self, collection: MeasurementCollection,
                                            file_path: Union[str, Path]) -> bool:
        """
        Export a MeasurementCollection to CSV.
        
        Args:
            collection: MeasurementCollection to export
            file_path: Destination file path
            
        Returns:
            True if export successful, False otherwise
        """
        return self.export_measurements_to_csv(collection.measurements, file_path)
    
    def export_measurements_to_json(self, measurements: List[Measurement],
                                  file_path: Union[str, Path]) -> bool:
        """
        Export measurements to a JSON file.
        
        Args:
            measurements: List of Measurement objects to export
            file_path: Destination file path
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = [measurement.to_dict() for measurement in measurements]
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"Error exporting measurements to JSON: {e}")
            return False
    
    def export_measurement_collection_to_json(self, collection: MeasurementCollection,
                                              file_path: Union[str, Path]) -> bool:
        """
        Export a MeasurementCollection to JSON.
        
        Args:
            collection: MeasurementCollection to export
            file_path: Destination file path
            
        Returns:
            True if export successful, False otherwise
        """
        return self.export_measurements_to_json(collection.measurements, file_path)
    
    def export_series_metadata_to_json(self, series: ImageSeries,
                                     file_path: Union[str, Path]) -> bool:
        """
        Export series metadata to a JSON file.
        
        Args:
            series: ImageSeries to export metadata from
            file_path: Destination file path
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            metadata = series.to_dict()
            
            # Add slice metadata
            metadata['slices'] = []
            for i, slice_obj in enumerate(series.sorted_slices):
                slice_metadata = {
                    'slice_index': i,
                    'z_position': slice_obj.z_position,
                    'shape': slice_obj.shape,
                    'filepath': str(slice_obj.filepath),
                    'has_pixel_data': slice_obj.has_pixel_data,
                    'metadata': slice_obj.metadata
                }
                metadata['slices'].append(slice_metadata)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"Error exporting series metadata to JSON: {e}")
            return False
    
    def export_slice_pixel_data_to_csv(self, series: ImageSeries, slice_index: int,
                                     file_path: Union[str, Path], 
                                     limit_size: Optional[int] = None) -> bool:
        """
        Export pixel data from a specific slice to CSV.
        
        Args:
            series: ImageSeries containing the slice
            slice_index: Index of the slice to export
            file_path: Destination file path
            limit_size: Maximum number of pixels to export (for large slices)
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            slice_obj = series.get_slice(slice_index)
            if slice_obj is None or slice_obj.pixel_array is None:
                print(f"No pixel data available for slice {slice_index}")
                return False
            
            pixel_array = slice_obj.pixel_array
            rows, cols = pixel_array.shape
            
            # If limit_size is specified, only export a subset
            if limit_size is not None and pixel_array.size > limit_size:
                # Calculate a square region around the center
                target_area = int(np.sqrt(limit_size))
                start_row = max(0, (rows - target_area) // 2)
                start_col = max(0, (cols - target_area) // 2)
                end_row = min(rows, start_row + target_area)
                end_col = min(cols, start_col + target_area)
                pixel_array = pixel_array[start_row:end_row, start_col:end_col]
            
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write header
                header = ['row', 'col'] + [f'pixel_{i}' for i in range(pixel_array.shape[1])]
                writer.writerow(header)
                
                # Write pixel data
                for row_idx in range(pixel_array.shape[0]):
                    row_data = [row_idx] + [int(pixel_array[row_idx, col_idx]) 
                                            for col_idx in range(pixel_array.shape[1])]
                    writer.writerow(row_data)
            
            return True
            
        except Exception as e:
            print(f"Error exporting slice pixel data to CSV: {e}")
            return False
    
    def export_series_statistics_to_csv(self, series: ImageSeries,
                                       file_path: Union[str, Path]) -> bool:
        """
        Export per-slice statistics to CSV.
        
        Args:
            series: ImageSeries to export statistics from
            file_path: Destination file path
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write header
                writer.writerow([
                    'slice_index', 'z_position', 'mean', 'std', 'min', 'max', 'sum', 'num_pixels'
                ])
                
                # Calculate and write statistics for each slice
                for i, slice_obj in enumerate(series.sorted_slices):
                    if slice_obj.pixel_array is not None:
                        pixel_array = slice_obj.pixel_array
                        writer.writerow([
                            i,
                            slice_obj.z_position,
                            float(np.mean(pixel_array)),
                            float(np.std(pixel_array)),
                            float(np.min(pixel_array)),
                            float(np.max(pixel_array)),
                            float(np.sum(pixel_array)),
                            int(pixel_array.size)
                        ])
            
            return True
            
        except Exception as e:
            print(f"Error exporting series statistics to CSV: {e}")
            return False
    
    def export_series_overview_to_json(self, series_list: List[ImageSeries],
                                      file_path: Union[str, Path]) -> bool:
        """
        Export an overview of multiple series to JSON.
        
        Args:
            series_list: List of ImageSeries to include in overview
            file_path: Destination file path
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            overview = {
                'num_series': len(series_list),
                'total_slices': sum(series.num_slices for series in series_list),
                'series': []
            }
            
            for series in series_list:
                series_overview = {
                    'series_uid': series.series_uid,
                    'study_uid': series.study_uid,
                    'patient_id': series.patient_id,
                    'patient_name': series.patient_name,
                    'series_description': series.series_description,
                    'modality': series.modality,
                    'num_slices': series.num_slices,
                    'shape': series.shape,
                    'slice_shape': series.slice_shape,
                    'study_date': series.study_date,
                    'study_time': series.study_time,
                    'z_positions': series.z_positions,
                    'z_range': (min(series.z_positions) if series.z_positions else 0,
                               max(series.z_positions) if series.z_positions else 0)
                }
                overview['series'].append(series_overview)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(overview, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"Error exporting series overview to JSON: {e}")
            return False
    
    def export_hu_profile_to_csv(self, series: ImageSeries, slice_index: int,
                               row: int, col_start: int, col_end: int,
                               file_path: Union[str, Path],
                               slope: float = 1.0, intercept: float = 0.0) -> bool:
        """
        Export a HU profile along a row to CSV.
        
        Args:
            series: ImageSeries containing the slice
            slice_index: Index of the slice to extract profile from
            row: Row index for the profile
            col_start: Starting column
            col_end: Ending column
            file_path: Destination file path
            slope: Rescale slope for HU conversion
            intercept: Rescale intercept for HU conversion
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            slice_obj = series.get_slice(slice_index)
            if slice_obj is None or slice_obj.pixel_array is None:
                return False
            
            pixel_array = slice_obj.pixel_array
            
            # Extract profile
            profile = pixel_array[row, col_start:col_end]
            
            # Apply HU conversion
            hu_profile = profile * slope + intercept
            
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['col', 'raw_value', 'hu_value'])
                
                for i, (raw_val, hu_val) in enumerate(zip(profile, hu_profile)):
                    writer.writerow([col_start + i, float(raw_val), float(hu_val)])
            
            return True
            
        except Exception as e:
            print(f"Error exporting HU profile to CSV: {e}")
            return False
    
    def export_to_numpy_format(self, series: ImageSeries, 
                             file_path: Union[str, Path]) -> bool:
        """
        Export series volume data to numpy .npy format.
        
        Args:
            series: ImageSeries to export
            file_path: Destination file path
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            volume = series.volume
            if volume.size == 0:
                return False
            
            np.save(file_path, volume)
            return True
            
        except Exception as e:
            print(f"Error exporting to numpy format: {e}")
            return False
    
    def export_single_slice_to_numpy(self, series: ImageSeries, slice_index: int,
                                    file_path: Union[str, Path]) -> bool:
        """
        Export a single slice to numpy .npy format.
        
        Args:
            series: ImageSeries containing the slice
            slice_index: Index of the slice to export
            file_path: Destination file path
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            slice_obj = series.get_slice(slice_index)
            if slice_obj is None or slice_obj.pixel_array is None:
                return False
            
            np.save(file_path, slice_obj.pixel_array)
            return True
            
        except Exception as e:
            print(f"Error exporting single slice to numpy format: {e}")
            return False
    
    def create_export_directory(self, base_path: Union[str, Path]) -> Path:
        """
        Create a timestamped export directory.
        
        Args:
            base_path: Base directory to create export directory within
            
        Returns:
            Path to the created export directory
        """
        from datetime import datetime
        
        base_path = Path(base_path)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        export_dir = base_path / f'export_{timestamp}'
        export_dir.mkdir(parents=True, exist_ok=True)
        
        return export_dir
    
    def export_full_study(self, series_list: List[ImageSeries],
                        export_dir: Union[str, Path],
                        include_pixel_data: bool = False) -> Dict[str, Any]:
        """
        Export a complete study (multiple series) to a directory.
        
        Args:
            series_list: List of ImageSeries to export
            export_dir: Destination directory
            include_pixel_data: Whether to include actual pixel data (can be large)
            
        Returns:
            Dictionary with export results and file paths
        """
        export_dir = Path(export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)
        
        results = {
            'export_dir': str(export_dir),
            'series_exencias': [],
            'files_created': [],
            'success': True,
            'errors': []
        }
        
        try:
            # Export overview
            overview_path = export_dir / 'series_overview.json'
            if self.export_series_overview_to_json(series_list, overview_path):
                results['files_created'].append(str(overview_path))
            
            # Export each series
            for i, series in enumerate(series_list):
                series_dir = export_dir / f'series_{i}_{series.series_uid}'
                series_dir.mkdir(exist_ok=True)
                
                # Export metadata
                metadata_path = series_dir / 'metadata.json'
                if self.export_series_metadata_to_json(series, metadata_path):
                    results['files_created'].append(str(metadata_path))
                
                # Export statistics
                stats_path = series_dir / 'statistics.csv'
                if self.export_series_statistics_to_csv(series, stats_path):
                    results['files_created'].append(str(stats_path))
                
                # Export volume data if requested
                if include_pixel_data and series.num_slices > 0:
                    volume_path = series_dir / 'volume.npy'
                    if self.export_to_numpy_format(series, volume_path):
                        results['files_created'].append(str(volume_path))
                
                series_result = {
                    'series_uid': series.series_uid,
                    'series_description': series.series_description,
                    'num_slices': series.num_slices,
                    'export_dir': str(series_dir),
                    'files': []
                }
                results['series_exencias'].append(series_result)
            
            return results
            
        except Exception as e:
            results['success'] = False
            results['errors'].append(str(e))
            return results