# DICOM Data Extraction Helper

During my civil service at the University Hospital Insel in Bern, I got the task of analyzing the anonymization process of patient data. To support this process and make analyses in the future easier, I implemented a few small helper tools, which can save a lot of time during the analysis of such profiles.

The repository at the moment contains two tools: 

1. [DICOM Header Extraction Tool](#dicom-data-extraction-helper). Simply extracts DICOM headers and writes them to stdout or a specified file.
    
    1.1 usage: `python3 dicom_header_extractor.py -h`

2. [Anonymization Profile Analysis Tool](#anonymization-profile-analysis-tool). CSV based anonymization profile analyzer which can help to automatically analyze and compare anonymization profiles.
   
    2.1 usage: `python3 main.py`

# DICOM Header Extraction Tool

A Python CLI tool for extracting and displaying DICOM metadata from directory exports (e.g., PACS exports).

## Features

- Recursively scans directories for DICOM files
- Extracts comprehensive metadata from all DICOM levels (Patient, Study, Series, Image)
- Supports all standard DICOM tags documented in the DICOM standard
- Organizes output by DICOM hierarchy
- Supports both human-readable text and CSV output formats
- Handles multi-value DICOM tags properly

## Installation

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Basic Usage

```bash
# Print DICOM header report to stdout
python dicom_header_extractor.py /path/to/dicom/directory

# Save text report to file
python dicom_header_extractor.py /path/to/dicom/directory --output report.txt

# Export metadata to CSV file
python dicom_header_extractor.py /path/to/dicom/directory --csv metadata.csv

# Filter by category (text output only)
python dicom_header_extractor.py /path/to/dicom/directory --category patient

# Verbose mode with debug info
python dicom_header_extractor.py /path/to/dicom/directory --verbose
```

### All Options

```bash
python dicom_header_extractor.py --help
```

```
usage: dicom_header_extractor.py [-h] [--output OUTPUT] [--csv FILENAME] [--category {all,Patient,Study,Series,Image,Physicians}] [--verbose] directory

positional arguments:
  directory              Path to directory containing DICOM files

optional arguments:
  -h, --help            show this help message and exit
  --output OUT, -o OUT  Output text file path (default: stdout)
  --csv FILENAME        Write results to CSV file with specified filename
  --category {all,Patient,Study,Series,Image,Physicians}, -c {all,Patient,Study,Series,Image,Physicians}
                        Filter output by category (default: all)
  --verbose, -v         Show additional metadata and debug info
```

## Output Formats

### Text Output

Human-readable report organized by DICOM hierarchy:
- Patient Level: Patient demographics and identifiers
- Study Level: Study information, dates, physicians
- Series Level: Series description, modality, acquisition parameters
- Image Level: Instance-level metadata, pixel data info, spatial information

### CSV Output

Comma-separated values with one row per DICOM image file:
- File Path: Full path to the DICOM file
- SOP Instance UID: Unique identifier for each image
- All selected DICOM tag values as columns
- Multi-value tags are joined with semicolons (`;`)
- Missing values are empty strings

## Supported DICOM Tags

The tool extracts all standard DICOM tags from the following categories:

### Patient Tags (30+ tags)
- Patient's Name, ID, Birth Date, Sex, Age, Size, Weight
- Address, Telephone Numbers, Mother's Birth Name
- Allergies, Medical Alerts, Smoking Status
- Insurance information, Military Rank, Occupation
- And more...

### Study Tags
- Study Instance UID, Date, Time, Description
- Accession Number, Modality
- Referring/Performing/Reading Physicians
- Institution information

### Series Tags
- Series Instance UID, Number, Description
- Modality, Body Part Examined
- Performing Physician, Operators

### Image Tags
- SOP Class/Instance UID
- Rows, Columns, Pixel Spacing
- Slice Thickness, Image Position/Orientation
- Window Center/Width, Rescale Intercept/Slope
- Photometric Interpretation, Bits Allocated/Stored
- And more...

### Physician Tags
- Referring, Performing, Reading physicians
- Operators
- Identification sequences

## Directory Structure

The tool is designed to work with directory structures like:

```
EXPORTED_DICOM_DIR_FROM_VENDOR/
├── DICOM/
│   └── <patient_id>/
│       └── <request_id>/
│           └── <study_uid>/
│               └── <series_uid>/
│                   ├── <sop_instance_uid_1>
│                   ├── <sop_instance_uid_2>
│                   └── ...
├── DICOMDIR
├── README.TXT
└── VENDOR_SPECIFIC/
    └── CONTENT.XML
```

But it will also work with any directory structure containing DICOM files, as it identifies DICOM files by their "DICM" prefix.

## Examples

### Example 1: Quick overview

```bash
python dicom_header_extractor.py .EXPORTED_DICOM_DIR_FROM_VENDOR
```

This will print a summary of all patients, studies, series, and images with their metadata.

### Example 2: CSV export for data analysis

```bash
python dicom_header_extractor.py .EXPORTED_DICOM_DIR_FROM_VENDOR --csv all_metadata.csv
```

Creates a CSV file with all DICOM metadata that can be opened in Excel or analyzed with pandas.

### Example 3: Extract only patient information

```bash
python dicom_header_extractor.py .EXPORTED_DICOM_DIR_FROM_VENDOR --csv patients.csv --category patient
```

Creates a CSV with only patient-level metadata columns.

### Example 4: Save detailed report

```bash
python dicom_header_extractor.py ./data/ --output full_report.txt
```

Saves a comprehensive text report to full_report.txt.

## Performance

- Process files incrementally without loading all pixel data
- Efficient for large datasets (tested with 1,106 DICOM files)
- Uses `stop_before_pixels=True` to avoid loading large image arrays

## Requirements

- Python 3.7+
- pydicom 2.4.0+




# Anonymization Profile Analysis Tool

This tool parses and analyzes anonymization profiles from CSV data to help answer questions about profile differences and find optimal profiles for specific requirements.

## Features Implemented

### 1. Data Parsing
- Parses `profiles.csv` into a structured matrix format
- Operations: `remove`, `modify`, `custom`, `X` (not considered)

### 2. Mathematical Operations
- **Set Difference**: Find differences between profiles using `A - B` operations
- **Set Intersection**: Find profiles matching all requirements using `A ∩ B` operations  
- **Set Complement**: Find profiles excluding specific fields using universal set minus target set
- **Jaccard Similarity**: Calculate profile similarity using |A ∩ B| / |A ∪ B|
- **Mode/Frequency Analysis**: Find consensus operations across multiple profiles

### 3. Core Functionality

#### Profile Comparison (Pairwise)
```python
analyzer.get_profile_differences('profile1', 'profile2')
# Returns: [(field, op1, op2), ...]
```

#### Multi-Profile Comparison (N-way)
```python
analyzer.get_multi_profile_differences(['profile1', 'profile2', 'profile3'])
# Returns: {field: {profile: operation, ...} for differing fields}
```

#### Find Profiles for Specific Operations
```python
analyzer.find_profiles_for_operations({
    'patients name': 'custom',
    'patient id': 'custom'
})
# Returns: ['profile1', 'profile2']
```

#### Find Profiles Excluding Fields
```python
analyzer.find_profiles_excluding_fields({'study date', 'series date'})
# Returns: ['profile1']
```

#### Find Consensus Among Profiles
```python
analyzer.find_consensus_fields(['profile1', 'profile2'], min_agreement=2)
# Returns: {field: operation, ...} where ≥ min_agreement profiles agree
```

#### Rank Profiles by Requirements
```python
analyzer.rank_profiles_by_requirements({
    'patients name': 'custom',
    'study date': 'X'
})
# Returns: [('profile1', 0.85), ('profile2', 0.60), ...]
```

#### Profile Similarity Matrix
```python
analyzer.get_profile_similarity_matrix()
# Returns: {'profile1': {'profile2': 0.95, ...}, ...}
```

#### Cluster Profiles by Similarity
```python
analyzer.cluster_profiles(threshold=0.8)
# Returns: [['profile1', 'profile2'], ['profile3'], ...]
```

#### Profile Statistics
```python
analyzer.get_profile_statistics()
# Returns: {'profile': {'remove': count, 'modify': count, ...}, ...}
```

### 4. CLI Interface
Run `python3 main.py` for interactive menu:
- Show profile differences (pairwise)
- Find profiles for specific operations
- Find profiles excluding certain fields
- Show profile statistics
- Compare multiple profiles (N-way)
- Find consensus among profiles
- Rank profiles by requirements
- Show profile similarity matrix
- Cluster profiles by similarity

### 5. Example Queries Answered

**What are the differences between profiles?**
```python
diffs = analyzer.get_profile_differences('profile 1', 'profile 2')
# Shows 6 fields with different operations
```

**Find differences across multiple profiles (N-way)**
```python
diffs = analyzer.get_multi_profile_differences(['profile 1', 'profile 2', 'profile 3'])
# Shows 19 fields where any profile differs
```

**Find profile where specific fields should be (remove|modify|custom)**
```python
matching = analyzer.find_profiles_for_operations({
    'patients name': 'custom',
    'study date': 'modify'
})
# Returns: ['profile 2']
```

**Find profile that doesn't anonymize certain fields**
```python
matching = analyzer.find_profiles_excluding_fields({'study date'})
# Returns: ['profile 1']
```

**Find consensus among multiple profiles**
```python
consensus = analyzer.find_consensus_fields(['profile 1', 'profile 2'], min_agreement=2)
# Returns: 237 fields where both profiles agree
```

**Rank profiles by how well they match requirements**
```python
ranked = analyzer.rank_profiles_by_requirements({
    'patients name': 'custom',
    'study date': 'X',
    'patient birth date': 'remove'
})
# Returns: [('profile 1', 1.0), ('profile 2', 0.5), ...]
```

**Find similar profiles using Jaccard similarity**
```python
similarity = analyzer.get_profile_similarity_matrix()
# Shows profile 1 ↔ profile 2: 0.951, profile 1 ↔ product support: 0.867
```

**Cluster profiles by similarity**
```python
clusters = analyzer.cluster_profiles(threshold=0.8)
# Returns: [['profile 1', 'profile 2', 'profile 3']]
```

## Files

- `profile_parser.py`: CSV parsing and matrix creation
- `profile_analyzer.py`: Core analysis functions with set operations
- `main.py`: CLI interface
- `test_functionality.py`: Comprehensive test demonstrating all features

## Usage

### Command Line Interface
```bash
# Run with default file
python3 main.py

# Run with custom CSV file
python3 main.py --file data/custom_profiles.csv
python3 main.py -f data/custom_profiles.csv

# Show help
python3 main.py --help
```

### Python API
```python
# Use with default file
from profile_parser import ProfileParser
from profile_analyzer import ProfileAnalyzer

parser = ProfileParser()
analyzer = ProfileAnalyzer(parser)
# Use analyzer methods...

# Use with custom file path
parser = ProfileParser('data/custom_profiles.csv')
analyzer = ProfileAnalyzer(parser)

# Or use ProfileAnalyzer directly with file path
analyzer = ProfileAnalyzer(csv_file='data/custom_profiles.csv')
```

### Testing
```bash
# Run basic functionality tests
python3 test_functionality.py

# Run N-way analysis tests
python3 test_nway_functionality.py
```

## Implementation Details

- Uses Python sets for efficient intersection and difference operations
- Matrix representation: `{fieldname: {profile: operation, ...}, ...}`
- Handles edge cases like empty CSV values (treated as 'X')
- Comprehensive error handling and input validation

## License

GNU GPLv3

credits: ideas, creativity and prompts by me, work by Mistral (devstral-2 mostly)
