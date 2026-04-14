# DICOM Headers in Radiological Imaging

**DICOM** (Digital Imaging and Communications in Medicine) is the international standard for storing, exchanging, and transmitting medical imaging data and metadata.

## File Structure

A DICOM file consists of:
- **File Meta Information** (optional file header, 128-byte preamble + 4-byte "DICM" prefix)
- **DICOM Dataset** (the actual header + pixel data)

## DICOM Header

The header contains **metadata** organized as **Data Elements** (tags) that describe:
- Patient information (name, ID, birth date, sex)
- Study information (date, time, description, referring physician)
- Series information (modality, body part, laterality, protocol)
- Image information (slice thickness, orientation, position, window settings)
- Equipment information (manufacturer, institution, software version)

### Tag Format

Each data element is identified by a **tag** in the format `(gggg, eeee)`:
- `gggg`: Group number (2 bytes, hexadecimal)
- `eeee`: Element number (2 bytes, hexadecimal)

**Common tag groups:**

| Group | Category | Example Elements |
|-------|----------|------------------|
| 0008  | Study    | Study Date, Study Time, Study Description, Modality |
| 0010  | Patient  | Patient Name, Patient ID, Patient Birth Date, Patient Sex |
| 0020  | Study/Series/Image | Study Instance UID, Series Instance UID, SOP Instance UID, Image Position, Image Orientation |
| 0028  | Image    | Rows, Columns, Pixel Spacing, Window Center, Window Width |
| 0040  | Equipment | Institution Name, Performed Procedure Step Description |

### Data Element Structure

Each element has:
- **Tag**: (gggg,eeee) — identifies the element
- **VR**: Value Representation (e.g., `PN`=Person Name, `DA`=Date, `UI`=Unique Identifier, `DS`=Decimal String, `IS`=Integer String, `SH`=Short String, `LO`=Long String, `SQ`=Sequence)
- **VM**: Value Multiplicity — number of values
- **Length**: Size of the value field
- **Value**: The actual data

### Example Tags

```
(0010, 0010) PN Patient's Name
(0010, 0020) ID Patient ID
(0010, 0030) DA Patient Birth Date
(0010, 0040) CS Patient's Sex
(0008, 0020) DA Study Date
(0008, 0060) CS Modality (CT, MR, US, etc.)
(0020, 000D) UI Study Instance UID
(0020, 000E) UI Series Instance UID
(0008, 0018) UI SOP Instance UID
(0028, 0010) US Rows
(0028, 0011) US Columns
```

## Image-Specific DICOM Tags

These tags describe the image pixel data and spatial properties:

| Tag | Name | VR | Description |
|-----|------|----|-------------|
| (0028, 0010) | Rows | US | Image height in pixels |
| (0028, 0011) | Columns | US | Image width in pixels |
| (0028, 0030) | Pixel Spacing | DS | Physical row/column spacing (mm) |
| (0028, 0002) | Samples per Pixel | US | Color channels (1=grayscale, 3=RGB) |
| (0028, 0100) | Bits Allocated | US | Storage bits per sample |
| (0028, 0101) | Bits Stored | US | Significant bits |
| (0028, 0004) | Photometric Interpretation | CS | MONOCHROME1/2, RGB, YBR etc. |
| (0020, 0032) | Image Position (Patient) | DS | [x,y,z] of top-left corner (mm) |
| (0020, 0037) | Image Orientation (Patient) | DS | Row/column direction cosines |
| (0018, 0050) | Slice Thickness | DS | Slice thickness (mm) |
| (0028, 0008) | Number of Frames | IS | Multi-frame image count |
| (0028, 0009) | Frame Increment Pointer | AT | Points to spacing between frames |
| (0028, 0006) | Planar Configuration | US | 0=axial, 1=sagittal/coronal |
| (0028, 1050) | Window Center | DS | Default display window center |
| (0028, 1051) | Window Width | DS | Default display window width |
| (0028, 1052) | Rescale Intercept | DS | Value intercept (e.g., -1024 for CT) |
| (0028, 1053) | Rescale Slope | DS | Value multiplier (e.g., 1 for CT) |
| (0028, 0106) | Smallest Pixel Value | US/SS | Minimum pixel value in data |
| (0028, 0107) | Largest Pixel Value | US/SS | Maximum pixel value in data |

## Patient Metadata

All patient-related information is stored **within the DICOM dataset** (not separate from the header). Below is the **complete list** of patient tags from group **0010**:

| Tag | Name | VR | Description |
|-----|------|----|-------------|
| (0010, 0010) | Patient's Name | PN | Full name (Last^First^Middle) |
| (0010, 0020) | Patient ID | LO | Internal identifier |
| (0010, 0021) | Issuer of Patient ID | LO | Institution assigning the ID |
| (0010, 0022) | Type of Patient ID | CS | Type of identifier |
| (0010, 0030) | Patient's Birth Date | DA | YYYYMMDD format |
| (0010, 0032) | Patient's Birth Time | TM | HHMMSS.SSSS |
| (0010, 0040) | Patient's Sex | CS | M, F, O |
| (0010, 0050) | Patient's Insurance Plan Code Sequence | SQ | Insurance plan identifiers |
| (0010, 1000) | Other Patient IDs | LO | External identifiers (retired) |
| (0010, 1001) | Other Patient Names | PN | Alternate name formats |
| (0010, 1002) | Other Patient IDs Sequence | SQ | External identifiers (sequence) |
| (0010, 1005) | Patient's Birth Name | PN | Birth/family name |
| (0010, 1010) | Patient's Age | AS | Age string (e.g., "042Y", "005M", "012D") |
| (0010, 1020) | Patient's Size | DS | Height in meters |
| (0010, 1030) | Patient's Weight | DS | Weight in kg |
| (0010, 1040) | Patient's Address | LO | Street address |
| (0010, 1050) | Insurance Plan Identification | LO | Insurance identifier |
| (0010, 1060) | Patient's Mother's Birth Name | PN | Maternal surname |
| (0010, 1080) | Military Rank | LO | Military rank |
| (0010, 1081) | Branch of Service | LO | Military branch |
| (0010, 1090) | Medical Record Locator | LO | Reference to medical record |
| (0010, 2000) | Medical Alerts | LO | Patient allergies/alerts |
| (0010, 2110) | Allergies | LO | Allergy information (text) |
| (0010, 2150) | Country of Residence | LO | Patient's country |
| (0010, 2152) | Region of Residence | LO | State/region of residence |
| (0010, 2154) | Patient's Telephone Numbers | LO | Contact numbers |
| (0010, 2160) | Ethnic Group | LO | Ethnic classification |
| (0010, 2180) | Occupation | LO | Patient's job/occupation |
| (0010, 21A0) | Smoking Status | CS | Smoking history/status |
| (0010, 21B0) | Additional Patient History | LO | Free-text medical history |
| (0010, 21C0) | Pregnancy Status | US | 0=unknown, 1=not pregnant, 2=pregnant, 3=possibly pregnant |
| (0010, 21D0) | Last Menstrual Date | DA | Date of last menstrual period |
| (0010, 21F0) | Patient's Religious Preference | LO | Religious preference |
| (0010, 2201) | Patient Species Description | LO | For non-human patients |
| (0010, 2202) | Patient Species Code Sequence | SQ | Non-human species identifiers |
| (0010, 2203) | Patient's Sex Neutered | LO | Neutered status (veterinary) |
| (0010, 2210) | Anatomical Orientation Type | LO | Orientation (e.g., human, animal) |
| (0010, 2292) | Patient Breed Description | LO | Breed description (veterinary) |
| (0010, 2293) | Patient Breed Code Sequence | SQ | Breed identifiers |
| (0010, 2294) | Breed Registration Sequence | SQ | Registration details |
| (0010, 2295) | Breed Registration Number | LO | Registration number |
| (0010, 2296) | Breed Registry Code Sequence | SQ | Registry codes |
| (0010, 2297) | Responsible Person | PN | Person responsible for patient |
| (0010, 2298) | Responsible Person Role | LO | Role of responsible person |
| (0010, 2299) | Responsible Organization | LO | Organization responsible for patient |

### Medical Condition Tags (Related to Patient)

| Tag | Name | VR | Description |
|-----|------|----|-------------|
| (0010, 2110) | Allergies | LO | Free-text allergy information |
| (0010, 2000) | Medical Alerts | LO | Critical patient alerts |
| (0010, 21A0) | Smoking Status | CS | Current/former/never smoker |
| (0010, 21B0) | Additional Patient History | LO | Clinical history |
| (0010, 21C0) | Pregnancy Status | US | Pregnancy indicator |

## Physician and Doctor Tags

Tags identifying medical professionals involved in the imaging study:

| Tag | Name | VR | Description |
|-----|------|----|-------------|
| (0008, 0090) | Referring Physician's Name | PN | Physician who referred patient for study |
| (0008, 0092) | Referring Physician's Address | ST | Address of referring physician |
| (0008, 0094) | Referring Physician's Telephone Numbers | LO | Contact numbers |
| (0008, 0096) | Referring Physician Identification Sequence | SQ | Detailed identifiers for referring physician |
| (0008, 1048) | Physician(s) of Record | PN | Physician(s) primarily responsible for patient |
| (0008, 1049) | Physician(s) of Record Identification Sequence | SQ | Identifiers for physicians of record |
| (0008, 1050) | Performing Physician's Name | PN | Physician(s) who performed the procedure |
| (0008, 1052) | Performing Physician Identification Sequence | SQ | Identifiers for performing physicians |
| (0008, 1060) | Name of Physician(s) Reading Study | PN | Radiologist reading/interpretation |
| (0008, 1062) | Physician(s) Reading Study Identification Sequence | SQ | Identifiers for reading physicians |
| (0008, 1070) | Operators' Name | PN | Technicians/operators performing procedure |
| (0008, 1072) | Operator Identification Sequence | SQ | Identifiers for operators |
| (0032, 1032) | Requesting Physician | PN | Physician requesting the procedure (HL7 mapping) |
| (0040, A075) | Concept Name Code Sequence | SQ | Coded name for clinical concepts |

### Additional Metadata Beyond Standard Header

- **Private Tags**: Manufacturer-specific metadata (odd group numbers, e.g., (0019,xxxx), (0021,xxxx), etc.). Vendor documentation required for interpretation.
- **Derived Properties**: Calculated from existing tags (e.g., patient age from birth date, body mass index from weight/height).
- **Pixel Data**: The actual image voxel values (7FE0,0010). Technically not metadata, but contains quantified imaging data (Hounsfield Units for CT, signal intensity for MRI).
- **Overlay Data**: Graphic annotations burned into separate planes (60xx, xxxx group).
- **Structured Reports**: DICOM SR objects (RDSR, CDSR) containing detailed findings, measurements, and annotations as separate DICOM instances.
- **Presentation States**: Stored display preferences (window/level, annotations) as separate DICOM objects.

## Importance

DICOM headers enable **interoperability** between different vendors' equipment and PACS (Picture Archiving and Communication Systems), ensuring consistent image interpretation and data management across healthcare systems. They allow radiologists and software to access complete imaging context without relying on visual pixel data alone.

## References

- [Official DICOM Standard](https://www.dicomstandard.org/)
- [DICOM Standard Browser](https://dicom.innolitics.com/)
- [DICOM Key Concepts](https://www.dicomstandard.org/concepts)
