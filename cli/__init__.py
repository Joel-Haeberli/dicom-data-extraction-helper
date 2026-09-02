"""
CLI tools for DICOM Data Extraction Helper.

This package contains command-line tools for DICOM file analysis and processing.
"""

# CLI tools now available both from root (for backward compatibility) and from cli package

try:
    # Import from local CLI modules
    from .dicom_header_extractor import (
        find_dicom_files,
        is_dicom_file,
        format_value,
        get_tag_value,
        TAG_CATEGORIES,
        extract_metadata,
        print_metadata,
        extract_all_metadata
    )
    HAS_CLI_TOOLS = True
except ImportError:
    try:
        # Fallback to root imports for backward compatibility
        from dicom_header_extractor import (
            find_dicom_files,
            is_dicom_file,
            format_value,
            get_tag_value,
            TAG_CATEGORIES,
            extract_metadata,
            print_metadata,
            extract_all_metadata
        )
        HAS_CLI_TOOLS = True
    except ImportError:
        HAS_CLI_TOOLS = False

try:
    from .profile_parser import ProfileParser
    HAS_PROFILE_PARSER = True
except ImportError:
    try:
        from profile_parser import ProfileParser
        HAS_PROFILE_PARSER = True
    except ImportError:
        HAS_PROFILE_PARSER = False

try:
    from .profile_analyzer import ProfileAnalyzer
    HAS_PROFILE_ANALYZER = True
except ImportError:
    try:
        from profile_analyzer import ProfileAnalyzer
        HAS_PROFILE_ANALYZER = True
    except ImportError:
        HAS_PROFILE_ANALYZER = False

# Re-export for easy access
__all__ = [
    'find_dicom_files', 'is_dicom_file', 'format_value', 'get_tag_value',
    'TAG_CATEGORIES', 'extract_metadata', 'print_metadata', 'extract_all_metadata',
    'ProfileParser', 'ProfileAnalyzer'
]