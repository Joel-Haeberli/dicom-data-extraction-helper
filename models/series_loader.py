#!/usr/bin/env python3
"""
Series Loader for DICOM Data Extraction Helper.

This module provides functionality to load DICOM files and organize them
into ImageSeries objects using the core model.
"""

import sys
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from collections import defaultdict

try:
    import pydicom
    from pydicom.dataset import Dataset
    import numpy as np
    HAS_PYDICOM = True
except ImportError:
    HAS_PYDICOM = False
    Dataset = Any
    np = Any

from .image_series import ImageSlice, ImageSeries


class SeriesLoader:
    """
    Loads DICOM files and organizes them into ImageSeries objects.
    
    This class handles:
    - Finding DICOM files in directories
    - Grouping files by Series UID
    - Creating ImageSeries objects with proper slice ordering
    - Extracting metadata and pixel data
    """
    
    def __init__(self):
        """Initialize the series loader."""
        self._tag_categories = None
        self._try_load_tag_categories()
    
    def _try_load_tag_categories(self):
        """Try to load TAG_CATEGORIES from dicom_header_extractor."""
        try:
            from dicom_header_extractor import TAG_CATEGORIES
            self._tag_categories = TAG_CATEGORIES
        except ImportError:
            # Fallback - define minimal TAG_CATEGORIES
            self._tag_categories = {}
    
    def find_dicom_files(self, path: Path) -> List[Path]:
        """Find all DICOM files in a directory recursively."""
        try:
            from dicom_header_extractor import find_dicom_files
            return find_dicom_files(path)
        except ImportError:
            # Fallback implementation
            return self._find_dicom_files_fallback(path)
    
    def _find_dicom_files_fallback(self, path: Path) -> List[Path]:
        """Fallback implementation for finding DICOM files."""
        dicom_files = []
        
        if not path.exists():
            return dicom_files
        
        for file_path in path.rglob('*'):
            if file_path.is_file() and self._is_dicom_file_fallback(file_path):
                dicom_files.append(file_path)
        
        return dicom_files
    
    def _is_dicom_file_fallback(self, file_path: Path) -> bool:
        """Fallback implementation to check if a file is DICOM."""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(128)
                # Check for DICOM magic word "DICM"
                return b'DICM' in header
        except (IOError, OSError):
            return False
    
    def find_series_in_directory(self, path: Path) -> Dict[str, List[Path]]:
        """
        Find all DICOM files and group them by Series UID.
        
        Args:
            path: Path to directory containing DICOM files
            
        Returns:
            Dictionary mapping Series UID to list of file paths
        """
        dicom_files = self.find_dicom_files(path)
        
        # Group files by Series Instance UID
        series_files = defaultdict(list)
        
        for filepath in dicom_files:
            series_uid = self._get_series_uid(filepath)
            if series_uid:
                series_files[series_uid].append(filepath)
            else:
                # If we can't determine series UID, put in a special group
                series_files['UNKNOWN'].append(filepath)
        
        return dict(series_files)
    
    def _get_series_uid(self, filepath: Path) -> Optional[str]:
        """Get Series Instance UID from a DICOM file."""
        try:
            # Try to read with minimal data (faster)
            ds = pydicom.dcmread(filepath, stop_before_pixels=True)
            return str(getattr(ds, 'SeriesInstanceUID', None))
        except Exception:
            return None
    
    def _get_study_uid(self, filepath: Path) -> Optional[str]:
        """Get Study Instance UID from a DICOM file."""
        try:
            ds = pydicom.dcmread(filepath, stop_before_pixels=True)
            return str(getattr(ds, 'StudyInstanceUID', None))
        except Exception:
            return None
    
    def _get_patient_id(self, filepath: Path) -> Optional[str]:
        """Get Patient ID from a DICOM file."""
        try:
            ds = pydicom.dcmread(filepath, stop_before_pixels=True)
            return str(getattr(ds, 'PatientID', None))
        except Exception:
            return None
    
    def _get_patient_name(self, filepath: Path) -> Optional[str]:
        """Get Patient Name from a DICOM file."""
        try:
            ds = pydicom.dcmread(filepath, stop_before_pixels=True)
            return str(getattr(ds, 'PatientName', None))
        except Exception:
            return None
    
    def _get_series_description(self, filepath: Path) -> Optional[str]:
        """Get Series Description from a DICOM file."""
        try:
            ds = pydicom.dcmread(filepath, stop_before_pixels=True)
            return str(getattr(ds, 'SeriesDescription', None))
        except Exception:
            return None
    
    def _get_modality(self, filepath: Path) -> Optional[str]:
        """Get Modality from a DICOM file."""
        try:
            ds = pydicom.dcmread(filepath, stop_before_pixels=True)
            return str(getattr(ds, 'Modality', None))
        except Exception:
            return None
    
    def _get_study_date(self, filepath: Path) -> Optional[str]:
        """Get Study Date from a DICOM file."""
        try:
            ds = pydicom.dcmread(filepath, stop_before_pixels=True)
            return str(getattr(ds, 'StudyDate', None))
        except Exception:
            return None
    
    def _get_study_time(self, filepath: Path) -> Optional[str]:
        """Get Study Time from a DICOM file."""
        try:
            ds = pydicom.dcmread(filepath, stop_before_pixels=True)
            return str(getattr(ds, 'StudyTime', None))
        except Exception:
            return None
    
    def load_series(self, dicom_files: List[Path]) -> Optional[ImageSeries]:
        """
        Load a series from a list of DICOM file paths.
        
        Args:
            dicom_files: List of paths to DICOM files in the series
            
        Returns:
            ImageSeries object if successful, None otherwise
        """
        if not dicom_files:
            return None
        
        # Get series metadata from the first file
        first_file = dicom_files[0]
        series_uid = self._get_series_uid(first_file)
        study_uid = self._get_study_uid(first_file)
        patient_id = self._get_patient_id(first_file)
        
        if not series_uid:
            return None
        
        series_description = self._get_series_description(first_file) or ""
        modality = self._get_modality(first_file) or ""
        patient_name = self._get_patient_name(first_file) or ""
        study_date = self._get_study_date(first_file) or ""
        study_time = self._get_study_time(first_file) or ""
        
        # Create the series object
        series = ImageSeries(
            series_uid=series_uid,
            study_uid=study_uid,
            patient_id=patient_id,
            series_description=series_description,
            modality=modality,
            patient_name=patient_name,
            study_date=study_date,
            study_time=study_time,
        )
        
        # Load each file as a slice
        slices = []
        for filepath in dicom_files:
            slice_obj = self._load_slice(filepath)
            if slice_obj:
                slices.append(slice_obj)
        
        # Sort slices by z_position before adding to series
        slices.sort(key=lambda s: s.z_position)
        
        # Assign slice indices
        for i, slice_obj in enumerate(slices):
            slice_obj.slice_index = i
        
        # Add slices to series
        for slice_obj in slices:
            series.add_slice(slice_obj)
        
        return series if series.num_slices > 0 else None
    
    def _load_slice(self, filepath: Path) -> Optional[ImageSlice]:
        """Load a single DICOM file as an ImageSlice."""
        try:
            # First try to read metadata only
            ds_metadata = pydicom.dcmread(filepath, stop_before_pixels=True)
            
            # Check if this file has image data
            if not self._is_image_file(ds_metadata):
                return None
            
            # Read full dataset with pixel data
            ds = pydicom.dcmread(filepath)
            
            # Extract pixel array
            pixel_array = self._extract_pixel_array(ds)
            if pixel_array is None:
                return None
            
            # Get Z position
            z_position = self._get_z_position(ds)
            
            # Create slice
            slice_obj = ImageSlice(
                filepath=filepath,
                dataset=ds,
                pixel_array=pixel_array,
                slice_index=0,  # Will be set later
                z_position=z_position,
                metadata=self._extract_slice_metadata(ds),
            )
            
            return slice_obj
            
        except Exception as e:
            print(f"Warning: Could not load slice {filepath}: {e}", file=sys.stderr)
            return None
    
    def _is_image_file(self, ds: Dataset) -> bool:
        """Check if a DICOM dataset contains image data."""
        # Check for required image tags
        has_rows = (0x0028, 0x0010) in ds  # Rows
        has_cols = (0x0028, 0x0011) in ds  # Columns
        
        # Check for pixel data
        has_pixel_data = False
        
        # Method 1: Check for PixelData tag
        if 'PixelData' in ds or (0x7FE0, 0x0010) in ds:
            has_pixel_data = True
        
        # Method 2: Check if pixel_array attribute exists
        elif hasattr(ds, 'pixel_array'):
            has_pixel_data = True
        
        # Method 3: Check Modality
        modality = getattr(ds, 'Modality', '')
        image_modalities = ['CT', 'MR', 'US', 'CR', 'DR', 'XA', 'RF', 'NM', 'PT', 'PET', 'RTIMAGE', 'OT', 'MAMMO']
        if str(modality).upper() in image_modalities:
            has_pixel_data = True
        
        return has_rows and has_cols and has_pixel_data
    
    def _extract_pixel_array(self, ds: Dataset) -> Optional[np.ndarray]:
        """Extract pixel array from a DICOM dataset."""
        try:
            if hasattr(ds, 'pixel_array') and ds.pixel_array is not None:
                pixel_array = ds.pixel_array
                # Ensure it's a numpy array
                if not isinstance(pixel_array, np.ndarray):
                    pixel_array = np.array(pixel_array)
                return pixel_array
            
            # Try to access PixelData directly
            if hasattr(ds, 'PixelData') and ds.PixelData:
                pixel_data = ds.PixelData
                # Convert to numpy array
                if isinstance(pixel_data, bytes):
                    # Need to decode based on bits allocated, etc.
                    # For now, return None as this requires more complex handling
                    return None
                return np.array(pixel_data)
            
            return None
            
        except Exception:
            return None
    
    def _get_z_position(self, ds: Dataset) -> float:
        """Extract Z coordinate from ImagePositionPatient tag."""
        position = getattr(ds, 'ImagePositionPatient', None)
        if position:
            try:
                return float(position[2])
            except (IndexError, ValueError, TypeError):
                pass
        return 0.0
    
    def _extract_slice_metadata(self, ds: Dataset) -> Dict[str, Any]:
        """Extract additional metadata from a DICOM dataset."""
        metadata = {}
        
        # Extract common tags
        common_tags = [
            'SOPInstanceUID',
            'SOPClassUID',
            'InstanceNumber',
            'ImagePositionPatient',
            'ImageOrientationPatient',
            'PixelSpacing',
            'SliceThickness',
            'Rows',
            'Columns',
            'BitsAllocated',
            'BitsStored',
            'HighBit',
            'PixelRepresentation',
            'WindowCenter',
            'WindowWidth',
            'RescaleIntercept',
            'RescaleSlope',
            'PhotometricInterpretation',
            'SamplesPerPixel',
        ]
        
        for tag in common_tags:
            if hasattr(ds, tag):
                value = getattr(ds, tag)
                try:
                    # Convert pydicom types to standard Python types
                    if hasattr(value, 'original_string'):
                        metadata[tag] = str(value)
                    elif isinstance(value, (list, tuple)):
                        metadata[tag] = [str(v) for v in value]
                    else:
                        metadata[tag] = str(value)
                except Exception:
                    metadata[tag] = str(value)
        
        return metadata
    
    def load_series_from_directory(self, path: Path) -> List[ImageSeries]:
        """
        Load all series from a directory.
        
        Args:
            path: Path to directory containing DICOM files
            
        Returns:
            List of ImageSeries objects found in the directory
        """
        # Find all DICOM files and group by series
        series_files = self.find_series_in_directory(path)
        
        series_list = []
        for series_uid, file_list in series_files.items():
            if series_uid != 'UNKNOWN':  # Skip files we couldn't categorize
                series = self.load_series(file_list)
                if series:
                    series_list.append(series)
        
        return series_list
    
    def load_multiple_directories(self, paths: List[Path]) -> List[ImageSeries]:
        """
        Load series from multiple directories.
        
        Args:
            paths: List of directory paths
            
        Returns:
            List of ImageSeries objects from all directories
        """
        all_series = []
        for path in paths:
            series_list = self.load_series_from_directory(path)
            all_series.extend(series_list)
        return all_series