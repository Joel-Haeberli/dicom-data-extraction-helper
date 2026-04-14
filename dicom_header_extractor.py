#!/usr/bin/env python3
"""
DICOM Header Extraction Tool

Extracts and displays DICOM metadata from directory exports (e.g., PACS).
Organizes output by DICOM hierarchy: Patient -> Study -> Series -> Image.

Usage:
    python dicom_header_extractor.py /path/to/dicom/directory
    python dicom_header_extractor.py /path/to/dicom/directory --csv output.csv
    python dicom_header_extractor.py /path/to/dicom/directory --output report.txt
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any, Optional

try:
    import pydicom
    from pydicom.dataset import Dataset
    HAS_PYDICOM = True
except ImportError:
    HAS_PYDICOM = False
    print("Error: pydicom library is required. Install with: pip install pydicom")
    sys.exit(1)


# =============================================================================
# TAG REGISTRY - All tags from DICOM.md organized by category
# =============================================================================

# Tag format: (display_name, tag_id_int, tag_group_hex, tag_element_hex)
# tag_id_int = (group << 16) | element

TAG_CATEGORIES: dict[str, list[tuple[str, int]]] = {
    "Patient": [
        ("Patient's Name", 0x00100010),
        ("Patient ID", 0x00100020),
        ("Issuer of Patient ID", 0x00100021),
        ("Type of Patient ID", 0x00100022),
        ("Patient's Birth Date", 0x00100030),
        ("Patient's Birth Time", 0x00100032),
        ("Patient's Sex", 0x00100040),
        ("Patient's Insurance Plan Code Sequence", 0x00100050),
        ("Other Patient IDs", 0x00101000),
        ("Other Patient Names", 0x00101001),
        ("Other Patient IDs Sequence", 0x00101002),
        ("Patient's Birth Name", 0x00101005),
        ("Patient's Age", 0x00101010),
        ("Patient's Size", 0x00101020),
        ("Patient's Weight", 0x00101030),
        ("Patient's Address", 0x00101040),
        ("Insurance Plan Identification", 0x00101050),
        ("Patient's Mother's Birth Name", 0x00101060),
        ("Military Rank", 0x00101080),
        ("Branch of Service", 0x00101081),
        ("Medical Record Locator", 0x00101090),
        ("Medical Alerts", 0x00102000),
        ("Allergies", 0x00102110),
        ("Country of Residence", 0x00102150),
        ("Region of Residence", 0x00102152),
        ("Patient's Telephone Numbers", 0x00102154),
        ("Ethnic Group", 0x00102160),
        ("Occupation", 0x00102180),
        ("Smoking Status", 0x001021A0),
        ("Additional Patient History", 0x001021B0),
        ("Pregnancy Status", 0x001021C0),
        ("Last Menstrual Date", 0x001021D0),
        ("Patient's Religious Preference", 0x001021F0),
        ("Patient Species Description", 0x00102201),
        ("Patient Species Code Sequence", 0x00102202),
        ("Patient's Sex Neutered", 0x00102203),
        ("Anatomical Orientation Type", 0x00102210),
        ("Patient Breed Description", 0x00102292),
        ("Patient Breed Code Sequence", 0x00102293),
        ("Breed Registration Sequence", 0x00102294),
        ("Breed Registration Number", 0x00102295),
        ("Breed Registry Code Sequence", 0x00102296),
        ("Responsible Person", 0x00102297),
        ("Responsible Person Role", 0x00102298),
        ("Responsible Organization", 0x00102299),
    ],
    "Study": [
        ("Study Instance UID", 0x0020000D),
        ("Study Date", 0x00080020),
        ("Study Time", 0x00080030),
        ("Accession Number", 0x00080050),
        ("Study ID", 0x00200010),
        ("Study Description", 0x00081030),
        ("Referring Physician's Name", 0x00080090),
        ("Referring Physician's Address", 0x00080092),
        ("Referring Physician's Telephone Numbers", 0x00080094),
        ("Referring Physician Identification Sequence", 0x00080096),
        ("Physician(s) of Record", 0x00081048),
        ("Physician(s) of Record Identification Sequence", 0x00081049),
        ("Name of Physician(s) Reading Study", 0x00081060),
        ("Physician(s) Reading Study Identification Sequence", 0x00081062),
        ("Institution Name", 0x00080080),
        ("Institution Address", 0x00080081),
        ("Institution Department Name", 0x00081040),
    ],
    "Series": [
        ("Series Instance UID", 0x0020000E),
        ("Series Number", 0x00200011),
        ("Series Date", 0x00080021),
        ("Series Time", 0x00080031),
        ("Series Description", 0x0008103E),
        ("Modality", 0x00080060),
        ("Body Part Examined", 0x00180015),
        ("Performing Physician's Name", 0x00081050),
        ("Performing Physician Identification Sequence", 0x00081052),
        ("Operators' Name", 0x00081070),
        ("Operator Identification Sequence", 0x00081072),
        ("Manufacturer", 0x00080070),
    ],
    "Image": [
        ("SOP Class UID", 0x00080016),
        ("SOP Instance UID", 0x00080018),
        ("Instance Number", 0x00200013),
        ("Image Type", 0x00080008),
        ("Rows", 0x00280010),
        ("Columns", 0x00280011),
        ("Samples per Pixel", 0x00280002),
        ("Photometric Interpretation", 0x00280004),
        ("Planar Configuration", 0x00280006),
        ("Number of Frames", 0x00280008),
        ("Frame Increment Pointer", 0x00280009),
        ("Pixel Spacing", 0x00280030),
        ("Image Orientation (Patient)", 0x00200037),
        ("Image Position (Patient)", 0x00200032),
        ("Slice Thickness", 0x00180050),
        ("Spacing Between Slices", 0x00180088),
        ("Bits Allocated", 0x00280100),
        ("Bits Stored", 0x00280101),
        ("High Bit", 0x00280102),
        ("Pixel Representation", 0x00280103),
        ("Smallest Image Pixel Value", 0x00280106),
        ("Largest Image Pixel Value", 0x00280107),
        ("Window Center", 0x00281050),
        ("Window Width", 0x00281051),
        ("Rescale Intercept", 0x00281052),
        ("Rescale Slope", 0x00281053),
    ],
    "Physicians": [
        ("Referring Physician's Name", 0x00080090),
        ("Referring Physician's Address", 0x00080092),
        ("Referring Physician's Telephone Numbers", 0x00080094),
        ("Referring Physician Identification Sequence", 0x00080096),
        ("Physician(s) of Record", 0x00081048),
        ("Physician(s) of Record Identification Sequence", 0x00081049),
        ("Performing Physician's Name", 0x00081050),
        ("Performing Physician Identification Sequence", 0x00081052),
        ("Name of Physician(s) Reading Study", 0x00081060),
        ("Physician(s) Reading Study Identification Sequence", 0x00081062),
        ("Operators' Name", 0x00081070),
        ("Operator Identification Sequence", 0x00081072),
        ("Requesting Physician", 0x00321032),
        ("Concept Name Code Sequence", 0x0040A075),
    ],
}

# Also add a few more important tags that might be missing
TAG_CATEGORIES["Image"].extend([
    ("Image Comments", 0x00204000),
    ("Acquisition Date", 0x00080022),
    ("Acquisition Time", 0x00080032),
    ("Content Date", 0x00080023),
    ("Content Time", 0x00080033),
    ("Image Laterality", 0x00200062),
])

# Deduplicate tags that appear in multiple categories
# (e.g., Referring Physician appears in both Study and Physicians)
# We'll keep them in their primary category but they'll be accessible


def get_tag_name_from_id(tag_id: int) -> Optional[str]:
    """Find tag name from integer ID."""
    for category, tags in TAG_CATEGORIES.items():
        for tag_name, tid in tags:
            if tid == tag_id:
                return f"{category}: {tag_name}"
    return None


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class DicomEntity:
    """Represents a DICOM entity in the hierarchy."""
    level: str  # 'patient', 'study', 'series', 'image'
    uid: str
    path: Optional[Path] = None
    metadata: dict[str, dict[str, Any]] = field(default_factory=dict)
    children: list["DicomEntity"] = field(default_factory=list)
    parent: Optional["DicomEntity"] = None
    dicom_file: Optional[Path] = None  # For image level

    def __repr__(self) -> str:
        return f"DicomEntity({self.level}, {self.uid}, children={len(self.children)})"


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def is_dicom_file(file_path: Path) -> bool:
    """Check if a file is a DICOM file by reading the prefix."""
    try:
        with open(file_path, 'rb') as f:
            f.seek(128)  # Skip preamble
            prefix = f.read(4)
            return prefix == b'DICM'
    except (IOError, OSError):
        return False


def find_dicom_files(root_path: Path) -> list[Path]:
    """Recursively find all DICOM files in a directory tree.
    
    Excludes DICOMDIR (media directory file) which is a DICOM file but metadata.
    """
    dicom_files: list[Path] = []
    for path in root_path.rglob('*'):
        if path.is_file() and path.name != "DICOMDIR" and is_dicom_file(path):
            dicom_files.append(path)
    return sorted(dicom_files)


def format_value(value: Any) -> str:
    """Format a DICOM value for output.
    
    Handles:
    - Multi-value tags (lists, tuples) -> joined with semicolon
    - pydicom types (PersonName, Date, Time, etc.)
    - None/missing -> empty string
    - Bytes -> decoded string
    """
    if value is None:
        return ""
    
    # Handle pydicom VR types that have original_string
    if hasattr(value, "original_string"):
        return str(value)
    
    # Handle bytes
    if isinstance(value, bytes):
        try:
            return value.decode('utf-8')
        except UnicodeDecodeError:
            return value.decode('latin-1')
    
    # Handle pydicom PersonName - it's iterable but we want str() representation
    # Check for pydicom PersonName specifically
    try:
        # pydicom.valuerep.PersonName exists
        from pydicom.valuerep import PersonName
        if isinstance(value, PersonName):
            return str(value)
    except ImportError:
        pass
    
    # Handle pydicom MultiValue (list-like objects that aren't strings or bytes)
    if hasattr(value, "__iter__") and not isinstance(value, (str, bytes, bytearray)):
        try:
            # Check if it's a string-like iterable (PersonName iterates over chars)
            # If the first element is a single character, treat as string
            # But better: just use str() for PersonName-like objects
            return ";".join(str(v) for v in value)
        except TypeError:
            return str(value)
    
    return str(value)


def get_tag_value(ds: Dataset, tag_id: int) -> Any:
    """Get value from dataset for a given tag ID, handling keyword vs numeric access."""
    try:
        # Try to get by keyword if pydicom has it
        tag = pydicom.tag.Tag(tag_id)
        if tag in ds:
            element = ds[tag]
            # For PersonName and other VR types without .value, return the element itself
            # pydicom elements are usually accessed via element.value, but some types
            # like PersonName return the string directly
            if hasattr(element, 'value'):
                return element.value
            else:
                # It's a type like PersonName that IS the value
                return element
        return None
    except Exception:
        return None


# =============================================================================
# DICOM PARSING
# =============================================================================

def parse_dicom_file(file_path: Path) -> Optional[Dataset]:
    """Parse a DICOM file and return the dataset (without pixel data)."""
    try:
        # Use stop_before_pixels=True to avoid loading large pixel arrays
        ds = pydicom.dcmread(file_path, stop_before_pixels=True)
        return ds
    except Exception as e:
        print(f"Warning: Could not parse {file_path}: {e}", file=sys.stderr)
        return None


def extract_tags_from_dataset(ds: Dataset) -> dict[str, dict[str, Any]]:
    """Extract all defined tags from a DICOM dataset."""
    result: dict[str, dict[str, Any]] = {}
    
    for category, tags in TAG_CATEGORIES.items():
        result[category] = {}
        for tag_name, tag_id in tags:
            try:
                value = get_tag_value(ds, tag_id)
                result[category][tag_name] = value
            except Exception:
                result[category][tag_name] = None
    
    return result


# =============================================================================
# HIERARCHY BUILDING
# =============================================================================

def extract_uid_from_path(path: Path, level: str) -> Optional[str]:
    """Extract UID from directory path based on hierarchy level.
    
    Directory structure: .../DICOM/{patient}/{request}/{study}/{series}/{image}
    """
    parts = list(path.parts)
    # Find index of 'DICOM' in path
    try:
        dicom_idx = parts.index('DICOM')
    except ValueError:
        return None
    
    # patient is at dicom_idx + 1
    # request is at dicom_idx + 2
    # study is at dicom_idx + 3
    # series is at dicom_idx + 4
    # image filename is the file itself
    
    offsets = {
        'patient': 1,
        'request': 2,
        'study': 3,
        'series': 4,
    }
    
    if level in offsets:
        idx = dicom_idx + offsets[level]
        if idx < len(parts):
            return parts[idx]
    return None


def build_hierarchy(dicom_files: list[Path], root: Path) -> Optional[DicomEntity]:
    """Build DICOM hierarchy from file paths and content.
    
    Each DICOM file is parsed and its metadata is extracted. The metadata is stored
    at the image level (most specific). The hierarchy entities (patient, study, series)
    serve as organizational containers.
    """
    if not dicom_files:
        return None
    
    # Create root entity
    root_entity = DicomEntity(
        level="root",
        uid="root",
        path=root,
    )
    
    # Group files by patient, study, series using path structure
    patients: dict[str, DicomEntity] = {}
    studies: dict[tuple[str, str], DicomEntity] = {}
    series_dict: dict[tuple[str, str, str], DicomEntity] = {}
    
    for file_path in dicom_files:
        # Extract UIDs from directory path
        # Expected: .../DICOM/{patient}/{request}/{study}/{series}/{image}
        patient_uid = extract_uid_from_path(file_path, 'patient')
        study_uid = extract_uid_from_path(file_path, 'study')
        series_uid = extract_uid_from_path(file_path, 'series')
        
        if not all([patient_uid, study_uid, series_uid]):
            # Try to get from DICOM file itself
            ds = parse_dicom_file(file_path)
            if ds:
                patient_id_val = get_tag_value(ds, 0x00100020)  # Patient ID
                study_uid_val = get_tag_value(ds, 0x0020000D)  # Study Instance UID
                series_uid_val = get_tag_value(ds, 0x0020000E)  # Series Instance UID
                
                if patient_id_val:
                    patient_uid = str(patient_id_val)
                if study_uid_val:
                    study_uid = str(study_uid_val)[:8]  # Short form for dir name
                if series_uid_val:
                    series_uid = str(series_uid_val)[:8]
            else:
                # Can't determine hierarchy from path or file - skip
                continue
        
        # Get or create patient entity
        if patient_uid not in patients:
            patient_entity = DicomEntity(
                level="patient",
                uid=patient_uid,
                path=file_path.parents[4] if len(file_path.parts) > 4 else None,
            )
            patients[patient_uid] = patient_entity
            root_entity.children.append(patient_entity)
            patient_entity.parent = root_entity
        else:
            patient_entity = patients[patient_uid]
        
        # Get or create study entity
        study_key = (patient_uid, study_uid)
        if study_key not in studies:
            study_entity = DicomEntity(
                level="study",
                uid=study_uid,
                path=file_path.parents[3] if len(file_path.parts) > 3 else None,
            )
            studies[study_key] = study_entity
            patient_entity.children.append(study_entity)
            study_entity.parent = patient_entity
        else:
            study_entity = studies[study_key]
        
        # Get or create series entity
        series_key = (patient_uid, study_uid, series_uid)
        if series_key not in series_dict:
            series_entity = DicomEntity(
                level="series",
                uid=series_uid,
                path=file_path.parents[2] if len(file_path.parts) > 2 else None,
            )
            series_dict[series_key] = series_entity
            study_entity.children.append(series_entity)
            series_entity.parent = study_entity
        else:
            series_entity = series_dict[series_key]
        
        # Create image entity and parse DICOM file
        ds = parse_dicom_file(file_path)
        if ds:
            metadata = extract_tags_from_dataset(ds)
            instance_uid = get_tag_value(ds, 0x00080018) or file_path.stem
        else:
            metadata = {}
            instance_uid = file_path.stem
        
        image_entity = DicomEntity(
            level="image",
            uid=instance_uid,
            path=file_path,
            dicom_file=file_path,
            metadata=metadata,
        )
        series_entity.children.append(image_entity)
        image_entity.parent = series_entity
        
        # Also store aggregated metadata at study/series level from first image
        # This ensures study and series level metadata is accessible
        if not study_entity.metadata:
            # First image in this study - copy metadata to study level
            # But only for study-level tags
            study_entity.metadata = {cat: {} for cat in TAG_CATEGORIES.keys()}
            for cat in ["Study", "Physicians"]:
                study_entity.metadata[cat] = metadata.get(cat, {}).copy()
        
        if not series_entity.metadata:
            # First image in this series - copy metadata to series level
            series_entity.metadata = {cat: {} for cat in TAG_CATEGORIES.keys()}
            for cat in ["Series"]:
                series_entity.metadata[cat] = metadata.get(cat, {}).copy()
    
    return root_entity


# =============================================================================
# OUTPUT FORMATTERS
# =============================================================================

def timestamp() -> str:
    """Get current timestamp string."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_text_level_header(level_name: str) -> list[str]:
    """Create level header."""
    return [
        "",
        "-" * 80,
        f"--- {level_name.upper()} LEVEL ---",
        "-" * 80,
        "",
    ]


def format_text_entity(entity: DicomEntity, level: str, indent: int = 0) -> list[str]:
    """Format a single entity for text output."""
    lines = []
    prefix = "  " * indent
    
    # Get metadata for this level
    category_metadata = entity.metadata.get(level, {})
    
    # Header with UID
    lines.append(f"{prefix}[{level.capitalize()} {len(lines) + 1}: {entity.uid}]")
    
    # Add all tags for this category
    if level in TAG_CATEGORIES:
        for tag_name, _ in TAG_CATEGORIES[level]:
            value = category_metadata.get(tag_name)
            if value is not None:
                formatted_value = format_value(value)
                if formatted_value:
                    lines.append(f"{prefix}  {tag_name}: {formatted_value}")
    
    return lines


def format_as_text(hierarchy: DicomEntity, category_filter: Optional[str] = None) -> str:
    """Format hierarchy as human-readable text."""
    lines = []
    
    # Header
    lines.append("=" * 80)
    lines.append("DICOM HEADER EXTRACTION REPORT")
    lines.append("=" * 80)
    lines.append(f"Generated: {timestamp()}")
    lines.append(f"Source: {hierarchy.path or 'unknown'}")
    lines.append("=" * 80)
    lines.append("")
    
    # Process each patient
    for patient in hierarchy.children:
        # Patient level
        lines.extend(format_text_level_header("Patient"))
        lines.append(f"[Patient: {patient.uid}]")
        
        # Patient metadata - get from first image's patient data
        # Since patient entities don't have metadata directly, get from any image
        patient_data = {}
        if patient.children and patient.children[0].children and patient.children[0].children[0].children:
            patient_data = patient.children[0].children[0].children[0].metadata.get("Patient", {})
        
        if category_filter == "Patient" or category_filter is None:
            for tag_name, _ in TAG_CATEGORIES.get("Patient", []):
                val = patient_data.get(tag_name)
                if val is not None:
                    lines.append(f"  {tag_name}: {format_value(val)}")
        else:
            lines.append(f"  (filtered by category: {category_filter})")
        lines.append("")
        
        # Study level
        for study in patient.children:
            lines.extend(format_text_level_header("Study"))
            lines.append(f"[Study: {study.uid}]")
            
            # Study metadata is stored in study.metadata or from first image
            study_data = study.metadata.get("Study", {})
            if not study_data and study.children:
                study_data = study.children[0].children[0].metadata.get("Study", {})
            
            if category_filter == "Study" or category_filter is None:
                for tag_name, _ in TAG_CATEGORIES.get("Study", []):
                    val = study_data.get(tag_name)
                    if val is not None:
                        lines.append(f"  {tag_name}: {format_value(val)}")
            lines.append("")
            
            # Physicians at study level
            if category_filter == "Physicians" or category_filter is None:
                phys_data = study.metadata.get("Physicians", {})
                if not phys_data and study.children:
                    phys_data = study.children[0].children[0].metadata.get("Physicians", {})
                has_phys = any(v is not None for v in phys_data.values())
                if has_phys:
                    lines.append("  Physicians:")
                    for tag_name, _ in TAG_CATEGORIES.get("Physicians", []):
                        val = phys_data.get(tag_name)
                        if val is not None:
                            lines.append(f"    {tag_name}: {format_value(val)}")
            lines.append("")
            
            # Series level
            for series in study.children:
                lines.extend(format_text_level_header("Series"))
                lines.append(f"[Series: {series.uid}] - {len(series.children)} images")
                
                # Series metadata
                series_data = series.metadata.get("Series", {})
                if not series_data and series.children:
                    series_data = series.children[0].metadata.get("Series", {})
                
                if category_filter == "Series" or category_filter is None:
                    for tag_name, _ in TAG_CATEGORIES.get("Series", []):
                        val = series_data.get(tag_name)
                        if val is not None:
                            lines.append(f"  {tag_name}: {format_value(val)}")
                lines.append("")
                
                # Image level
                lines.extend(format_text_level_header("Image"))
                lines.append(f"[Series: {series.uid}] - {len(series.children)} images")
                lines.append("")
                
                for idx, image in enumerate(series.children[:10]):  # Show first 10, then summary
                    if category_filter == "Image" or category_filter is None:
                        lines.append(f"  Image {idx + 1}: {image.uid}")
                        img_meta = image.metadata.get("Image", {})
                        # Show a subset of important image tags to keep output manageable
                        important_image_tags = [
                            ("SOP Instance UID", 0x00080018),
                            ("SOP Class UID", 0x00080016),
                            ("Instance Number", 0x00200013),
                            ("Rows", 0x00280010),
                            ("Columns", 0x00280011),
                            ("Pixel Spacing", 0x00280030),
                            ("Slice Thickness", 0x00180050),
                            ("Image Position (Patient)", 0x00200032),
                            ("Window Center", 0x00281050),
                            ("Window Width", 0x00281051),
                            ("Rescale Intercept", 0x00281052),
                            ("Rescale Slope", 0x00281053),
                        ]
                        for tag_name, tag_id in important_image_tags:
                            val = img_meta.get(tag_name)
                            if val is not None:
                                lines.append(f"    {tag_name}: {format_value(val)}")
                        lines.append("")
                
                if len(series.children) > 10:
                    lines.append(f"  ... and {len(series.children) - 10} more images")
                    lines.append("")
    
    # Summary
    lines.append("=" * 80)
    patient_count = len(hierarchy.children)
    study_count = sum(len(p.children) for p in hierarchy.children)
    series_count = sum(len(s.children) for p in hierarchy.children for s in p.children)
    image_count = sum(len(se.children) for p in hierarchy.children for s in p.children for se in s.children)
    lines.append(f"Total: {patient_count} Patient(s), {study_count} Study/Studies, "
                f"{series_count} Series, {image_count} Images")
    lines.append("=" * 80)
    
    return "\n".join(lines)


def format_as_csv(
    hierarchy: DicomEntity, 
    category_filter: Optional[str] = None,
    output_path: Optional[Path] = None
) -> str:
    """Format hierarchy data as CSV with one row per image.
    
    For tags that appear in multiple categories (e.g., "Referring Physician's Name" in both 
    Study and Physicians), adds category prefix to make column names unique:
    - Study_Referring Physician's Name
    - Physicians_Referring Physician's Name
    """
    output = StringIO()
    
    # Determine which categories to include
    if category_filter:
        categories = [category_filter]
    else:
        categories = list(TAG_CATEGORIES.keys())
    
    # Build unique column names WITH CATEGORY PREFIX for ALL tags
    # This makes CSV columns explicit about which category they belong to
    # Also map (category, tag_name) -> column_name for lookups
    column_names: list[str] = ["File Path", "SOP Instance UID"]
    tag_to_column: dict[tuple[str, str], str] = {}
    
    for category in categories:
        for tag_name, _ in TAG_CATEGORIES.get(category, []):
            # ALWAYS add category prefix to make columns explicit
            column_name = f"{category}_{tag_name}"
            
            # Only add to column_names if not already present
            if column_name not in column_names:
                column_names.append(column_name)
            
            # Map this (category, tag_name) to column_name
            tag_to_column[(category, tag_name)] = column_name
    
    # Validate: No empty column names
    for name in column_names:
        if not name.strip():
            raise ValueError(f"Empty column header detected: '{name}'")
    
    writer = csv.DictWriter(output, fieldnames=column_names, quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    
    # Walk through all images and write rows
    def recursive_collect(entity: DicomEntity):
        """Recursively collect data from hierarchy."""
        if entity.level == "image":
            # This is an image - output a row
            row: dict[str, str] = {
                "File Path": str(entity.path) if entity.path else "",
                "SOP Instance UID": entity.uid,
            }
            
            # Add all category data, using category-prefixed column names for duplicates
            for category in categories:
                for tag_name, _ in TAG_CATEGORIES.get(category, []):
                    column_name = tag_to_column.get((category, tag_name), tag_name)
                    
                    # Get value from metadata
                    val = entity.metadata.get(category, {}).get(tag_name)
                    row[column_name] = format_value(val) if val is not None else ""
            
            # Ensure all columns exist (for categories not in this file)
            for col in column_names:
                if col not in row:
                    row[col] = ""
            
            writer.writerow(row)
        
        # Recurse into children
        for child in entity.children:
            recursive_collect(child)
    
    # Start recursion from root
    for patient in hierarchy.children:
        recursive_collect(patient)
    
    return output.getvalue()


# =============================================================================
# Main CLI
# =============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Extract and display DICOM headers from a directory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python dicom_header_extractor.py /path/to/dicom/directory
  python dicom_header_extractor.py /path/to/dir --output report.txt
  python dicom_header_extractor.py /path/to/dir --csv metadata.csv
  python dicom_header_extractor.py /path/to/dir --csv patients.csv --category patient
        """,
    )
    
    parser.add_argument(
        "directory",
        type=Path,
        help="Path to directory containing DICOM files",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Output text file path (default: stdout)",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        metavar="FILENAME",
        help="Write results to CSV file with specified filename",
    )
    parser.add_argument(
        "--category", "-c",
        choices=["all", "Patient", "Study", "Series", "Image", "Physicians"],
        default="all",
        help="Filter output by category (default: all)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show additional metadata and debug info",
    )
    
    args = parser.parse_args()
    
    # Validate directory
    if not args.directory.exists():
        print(f"Error: Directory not found: {args.directory}", file=sys.stderr)
        sys.exit(1)
    
    if not args.directory.is_dir():
        print(f"Error: Path is not a directory: {args.directory}", file=sys.stderr)
        sys.exit(1)
    
    # Normalize category filter
    category_filter = None if args.category == "all" else args.category
    
    if args.verbose:
        print(f"Scanning directory: {args.directory}", file=sys.stderr)
        print(f"Category filter: {category_filter or 'all'}", file=sys.stderr)
    
    # Step 1: Find DICOM files
    if args.verbose:
        print("Finding DICOM files...", file=sys.stderr)
    
    dicom_files = find_dicom_files(args.directory)
    
    if not dicom_files:
        print("No DICOM files found!", file=sys.stderr)
        sys.exit(0)
    
    if args.verbose:
        print(f"Found {len(dicom_files)} DICOM files", file=sys.stderr)
    
    # Step 2: Build hierarchy
    if args.verbose:
        print("Building DICOM hierarchy...", file=sys.stderr)
    
    hierarchy = build_hierarchy(dicom_files, args.directory)
    if hierarchy is None:
        print("Failed to build hierarchy", file=sys.stderr)
        sys.exit(1)
    
    if args.verbose:
        print(f"Hierarchy: {len(hierarchy.children)} patients", file=sys.stderr)
    
    # Step 3: Format output
    if args.csv:
        # CSV output
        if args.verbose:
            print(f"Formatting as CSV...", file=sys.stderr)
        
        csv_data = format_as_csv(hierarchy, category_filter)
        
        try:
            args.csv.write_text(csv_data)
            print(f"CSV report written to {args.csv} ({len(csv_data)} bytes)", file=sys.stderr)
        except IOError as e:
            print(f"Error writing CSV file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Text output
        if args.verbose:
            print("Formatting as text...", file=sys.stderr)
        
        text_data = format_as_text(hierarchy, category_filter)
        
        if args.output:
            try:
                args.output.write_text(text_data)
                print(f"Text report written to {args.output}", file=sys.stderr)
            except IOError as e:
                print(f"Error writing output file: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            print(text_data)


if __name__ == "__main__":
    main()
