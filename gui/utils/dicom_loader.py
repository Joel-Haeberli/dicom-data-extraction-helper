#!/usr/bin/env python3
"""
DICOM Loading Utilities for GUI Application

Reuses functions from dicom_header_extractor.py for consistent
DICOM file handling.
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import pydicom
    from pydicom.dataset import Dataset
    HAS_PYDICOM = True
except ImportError:
    HAS_PYDICOM = False

# Import from existing project utilities
try:
    from dicom_header_extractor import (
        find_dicom_files,
        is_dicom_file,
        format_value,
        get_tag_value,
        TAG_CATEGORIES,
    )
except ImportError:
    # Fallback - define minimal TAG_CATEGORIES if import fails
    TAG_CATEGORIES = {}
    def find_dicom_files(root_path):
        """Fallback implementation."""
        return []
    def is_dicom_file(file_path):
        """Fallback implementation."""
        return False
    def format_value(value):
        """Fallback implementation."""
        return str(value) if value is not None else ""
    def get_tag_value(ds, tag_id):
        """Fallback implementation."""
        return None


@dataclass
class DICOMFile:
    """Represents a loaded DICOM file with metadata."""
    filepath: Path
    dataset: Optional[Dataset] = None
    is_image: bool = False
    is_overlay: bool = False
    image_coordinates: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class DICOMLoader:
    """Loads and manages DICOM files from a directory."""
    
    def __init__(self):
        self.dicom_files: List[DICOMFile] = []
        self.current_directory: Optional[Path] = None
        self._series_cache: Optional[List] = None  # Cache for converted series
    
    def get_series_list(self):
        """
        Convert loaded DICOM files to ImageSeries objects.
        
        This provides a bridge between the old DICOMFile-based architecture
        and the new ImageSeries-based architecture.
        
        Returns:
            List of ImageSeries objects, or empty list if no compatible files
        """
        try:
            from models.image_series import ImageSeries, ImageSlice
            from models.series_loader import SeriesLoader
            
            # Use SeriesLoader to convert our files to series
            loader = SeriesLoader()
            
            # Group files by Series UID (similar to SeriesLoader logic)
            series_files = {}
            for dicom_file in self.dicom_files:
                if dicom_file.dataset and hasattr(dicom_file.dataset, 'SeriesInstanceUID'):
                    series_uid = str(dicom_file.dataset.SeriesInstanceUID)
                    if series_uid not in series_files:
                        series_files[series_uid] = []
                    series_files[series_uid].append(dicom_file.filepath)
            
            # Load each series
            series_list = []
            for series_uid, file_paths in series_files.items():
                series = loader.load_series(file_paths)
                if series:
                    series_list.append(series)
            
            self._series_cache = series_list
            return series_list
            
        except ImportError:
            # New models not available, return empty list
            return []
        except Exception as e:
            print(f"Warning: Could not convert to series: {e}")
            return []
    
    def clear_series_cache(self):
        """Clear the cached series list."""
        self._series_cache = None
    
    def load_directory(self, path: Path) -> List[DICOMFile]:
        """
        Load all DICOM files from the specified directory.
        
        Args:
            path: Path to directory containing DICOM files
            
        Returns:
            List of DICOMFile objects
        """
        self.current_directory = path
        self.dicom_files = []
        
        # Find all DICOM files
        dicom_paths = find_dicom_files(path)
        
        for filepath in dicom_paths:
            dicom_file = self._load_dicom_file(filepath)
            if dicom_file:
                self.dicom_files.append(dicom_file)
        
        return self.dicom_files
    
    def _load_dicom_file(self, filepath: Path) -> Optional[DICOMFile]:
        """
        Load a single DICOM file.
        
        Uses stop_before_pixels=True for initial type detection,
        then loads full dataset for image files and extracts all metadata.
        """
        try:
            # First pass: load metadata only (faster) for type detection
            ds_metadata = pydicom.dcmread(filepath, stop_before_pixels=True)
            
            is_image = self._is_image_file(ds_metadata)
            is_overlay = self._is_overlay_file(ds_metadata)
            coordinates = self._get_image_coordinates(ds_metadata) if is_image else {}
            
            # For image files or overlays, load full dataset for complete metadata
            if is_image or is_overlay:
                ds = pydicom.dcmread(filepath)
                metadata = self.extract_metadata(ds)
            else:
                ds = ds_metadata
                metadata = self.extract_metadata(ds)
            
            return DICOMFile(
                filepath=filepath,
                dataset=ds,
                is_image=is_image,
                is_overlay=is_overlay,
                image_coordinates=coordinates,
                metadata=metadata,
            )
        except Exception as e:
            print(f"Warning: Could not load {filepath}: {e}", file=sys.stderr)
            return None
    
    def get_first_image(self) -> Optional[DICOMFile]:
        """
        Get the first DICOM file that contains image data.
        
        Returns:
            First DICOMFile with is_image=True, or None if none found
        """
        for dicom_file in self.dicom_files:
            if dicom_file.is_image:
                return dicom_file
        return None
    
    def get_overlay_for_image(self, image: DICOMFile) -> Optional[DICOMFile]:
        """
        Find an overlay that matches the given image.
        
        Uses multiple matching strategies:
        1. ReferencedImageSequence in overlay (most reliable for Presentation State)
        2. ReferencedImageSequence in image (overlay refers to image)
        3. Same SeriesInstanceUID and matching ImagePositionPatient
        4. Same StudyInstanceUID
        
        Args:
            image: The DICOMFile to find overlay for
            
        Returns:
            Matching DICOMFile with is_overlay=True, or None
        """
        if not image.dataset:
            return None
        
        image_sop_uid = str(getattr(image.dataset, 'SOPInstanceUID', ''))
        image_series_uid = str(getattr(image.dataset, 'SeriesInstanceUID', ''))
        image_study_uid = str(getattr(image.dataset, 'StudyInstanceUID', ''))
        image_position = getattr(image.dataset, 'ImagePositionPatient', None)
        
        # Strategy 1: Check all overlays' ReferencedImageSequence (including nested)
        # This is the most reliable for Presentation State files
        for dicom_file in self.dicom_files:
            if not dicom_file.is_overlay or not dicom_file.dataset:
                continue
            
            # Check directly on dataset
            if hasattr(dicom_file.dataset, 'ReferencedImageSequence'):
                for ref in dicom_file.dataset.ReferencedImageSequence:
                    if hasattr(ref, 'ReferencedSOPInstanceUID'):
                        ref_sop_uid = str(ref.ReferencedSOPInstanceUID)
                        if ref_sop_uid == image_sop_uid:
                            return dicom_file
            
            # Check nested in ReferencedSeriesSequence
            if hasattr(dicom_file.dataset, 'ReferencedSeriesSequence'):
                for series_ref in dicom_file.dataset.ReferencedSeriesSequence:
                    if hasattr(series_ref, 'ReferencedImageSequence'):
                        for image_ref in series_ref.ReferencedImageSequence:
                            if hasattr(image_ref, 'ReferencedSOPInstanceUID'):
                                ref_sop_uid = str(image_ref.ReferencedSOPInstanceUID)
                                if ref_sop_uid == image_sop_uid:
                                    return dicom_file
        
        # Strategy 2: Check if image has ReferencedImageSequence pointing to overlay
        # (e.g., image has overlay embedded as reference)
        if hasattr(image.dataset, 'ReferencedImageSequence'):
            for ref in image.dataset.ReferencedImageSequence:
                if hasattr(ref, 'ReferencedSOPInstanceUID'):
                    ref_sop_uid = str(ref.ReferencedSOPInstanceUID)
                    for dicom_file in self.dicom_files:
                        if dicom_file.is_overlay and dicom_file.dataset:
                            if str(getattr(dicom_file.dataset, 'SOPInstanceUID', '')) == ref_sop_uid:
                                return dicom_file
        
        # Only return overlay if there's an explicit reference match
        # Don't guess based on Series or Study UIDs
        return None
    
    def extract_metadata(self, ds: Dataset) -> Dict[str, Dict[str, Any]]:
        """
        Extract all defined tags from a DICOM dataset.
        
        Uses TAG_CATEGORIES from dicom_header_extractor.py for
        consistent tag organization, plus extracts all other tags
        into an "Additional Metadata" category.
        
        Args:
            ds: pydicom Dataset
            
        Returns:
            Nested dict: {category: {tag_name: value}}
        """
        result: Dict[str, Dict[str, Any]] = {}
        
        # Extract tags from TAG_CATEGORIES
        for category, tags in TAG_CATEGORIES.items():
            result[category] = {}
            for tag_name, tag_id in tags:
                try:
                    value = get_tag_value(ds, tag_id)
                    result[category][tag_name] = value
                except Exception:
                    result[category][tag_name] = None
        
        # Extract all other tags not in TAG_CATEGORIES
        result["Additional Metadata"] = {}
        try:
            # Build set of tag IDs already extracted
            extracted_tag_ids = set()
            for category, tags in TAG_CATEGORIES.items():
                for tag_name, tag_id in tags:
                    extracted_tag_ids.add(tag_id)
            
            # Add remaining tags
            for elem in ds:
                tag_id = elem.tag.group * 0x10000 + elem.tag.element
                if tag_id not in extracted_tag_ids:
                    try:
                        value = get_tag_value(ds, tag_id)
                        # Use keyword if available, otherwise use tag in (gggg,eeee) format
                        keyword = elem.keyword if elem.keyword else f"({elem.tag.group:04X},{elem.tag.element:04X})"
                        result["Additional Metadata"][keyword] = value
                    except Exception:
                        keyword = elem.keyword if elem.keyword else f"({elem.tag.group:04X},{elem.tag.element:04X})"
                        result["Additional Metadata"][keyword] = None
        except Exception:
            pass  # If anything goes wrong, just skip additional metadata
        
        return result
    
    def _is_image_file(self, ds: Dataset) -> bool:
        """
        Check if a DICOM dataset contains image data.
        
        Checks multiple indicators:
        - Standard image tags (Rows, Columns)
        - PixelData tag or pixel_array attribute
        - Known image SOP classes
        
        Args:
            ds: pydicom Dataset
            
        Returns:
            True if contains image pixel data
        """
        # Check for required image tags
        has_rows = (0x0028, 0x0010) in ds  # Rows
        has_cols = (0x0028, 0x0011) in ds  # Columns
        
        # Check for pixel data - multiple ways
        has_pixel_data = False
        
        # Method 1: Check for PixelData tag (explicit)
        if 'PixelData' in ds or (0x7FE0, 0x0010) in ds:
            has_pixel_data = True
        
        # Method 2: Check if pixel_array attribute exists (pydicom may have processed it)
        elif hasattr(ds, 'pixel_array'):
            has_pixel_data = True
        
        # Method 3: Check SOP Class UID for known image types
        sop_class = str(getattr(ds, 'SOPClassUID', ''))
        # Also check the SOP Class as a pydicom UID object (convert to string)
        if hasattr(ds, 'SOPClassUID') and hasattr(ds.SOPClassUID, 'name'):
            sop_class = str(ds.SOPClassUID)
        
        image_sop_classes = [
            '1.2.840.10008.5.1.4.1.1.2',      # CT Image Storage
            '1.2.840.10008.5.1.4.1.1.4',      # MR Image Storage
            '1.2.840.10008.5.1.4.1.1.6',      # US Image Storage
            '1.2.840.10008.5.1.4.1.1.7',      # Secondary Capture
            '1.2.840.10008.5.1.4.1.1.1',      # CR Image Storage
            '1.2.840.10008.5.1.4.1.1.1.1',    # XI Image (X-Ray)
            '1.2.840.10008.5.1.4.1.1.1.2',    # XI Image (X-Ray)
            '1.2.840.10008.5.1.4.1.1.3',      # NM Image Storage
            '1.2.840.10008.5.1.4.1.1.5',      # PET Image Storage
            '1.2.840.10008.5.1.4.1.1.8',      # PT Image Storage
            '1.2.840.10008.5.1.4.1.1.9',      # RT Image Storage
            '1.2.840.10008.5.1.4.1.1.10',     # Mammography Image Storage
            '1.2.840.10008.5.1.4.1.1.18',     # IVUS Image Storage
            '1.2.840.10008.5.1.4.1.1.19',     # Ophthalmic Photography Image Storage
        ]
        if sop_class in image_sop_classes:
            has_pixel_data = True
        
        # Also check common SOP class descriptions
        sop_class_desc = sop_class.split('.')[-1] if '.' in sop_class else sop_class
        if 'Image Storage' in sop_class_desc or sop_class_desc in ['CT', 'MR', 'US', 'CR', 'DR']:
            has_pixel_data = True
        
        # Method 4: Check Modality
        modality = getattr(ds, 'Modality', '')
        image_modalities = ['CT', 'MR', 'US', 'CR', 'DR', 'XA', 'RF', 'NM', 'PT', 'PET', 'RTIMAGE', 'OT', 'MAMMO']
        if str(modality).upper() in image_modalities:
            has_pixel_data = True
        
        return has_rows and has_cols and has_pixel_data
    
    def _is_overlay_file(self, ds: Dataset) -> bool:
        """
        Check if a DICOM dataset contains overlay data.
        
        Checks for:
        - Traditional OverlayData tags (60xx, 3000)
        - Presentation State with overlay groups
        - Graphics overlay sequences
        
        Args:
            ds: pydicom Dataset
            
        Returns:
            True if contains overlay data
        """
        # Check for traditional overlay data (groups 6000-60FF, element 3000)
        for group in range(0x6000, 0x60FF, 2):
            if (group, 0x3000) in ds:
                return True
        
        # Check for OverlayData in standard locations
        for elem in range(0x3000, 0x3100, 2):
            if (0x6000, elem) in ds:
                return True
        
        # Check for Graphic Annotation Sequence (Presentation State)
        if hasattr(ds, 'GraphicAnnotationSequence'):
            return True
        
        # Check for overlay-related SOP classes
        sop_class = getattr(ds, 'SOPClassUID', '')
        overlay_sop_classes = [
            '1.2.840.10008.5.1.4.1.1.11.1',  # Graphic Annotation
            '1.2.840.10008.5.1.4.1.1.11',    # Presentation State
        ]
        if str(sop_class) in overlay_sop_classes:
            return True
        
        return False
    
    def _get_image_coordinates(self, ds: Dataset) -> Dict[str, float]:
        """
        Extract x, y, z coordinates from ImagePositionPatient tag.
        
        Args:
            ds: pydicom Dataset
            
        Returns:
            Dict with keys 'x', 'y', 'z' and float values
        """
        coords = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        
        position = getattr(ds, 'ImagePositionPatient', None)
        if position:
            try:
                coords['x'] = float(position[0])
                coords['y'] = float(position[1])
                coords['z'] = float(position[2])
            except (IndexError, ValueError, TypeError):
                pass
        
        return coords
    
    def clear(self):
        """Clear all loaded DICOM files."""
        self.dicom_files = []
        self.current_directory = None
