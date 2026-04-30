import pydicom
import numpy as np

def print_dicom_pixel_array(filepath):
    # Read the DICOM file
    ds = pydicom.dcmread(filepath)

    # Print basic metadata
    print("=== DICOM Metadata ===")
    print(f"Patient Name: {ds.get('PatientName', 'N/A')}")
    print(f"Modality: {ds.get('Modality', 'N/A')}")
    print(f"Image Size: {ds.Rows} x {ds.Columns}")
    print(f"Pixel Spacing: {ds.get('PixelSpacing', 'N/A')}")
    print(f"Bits Allocated: {ds.BitsAllocated}")
    print(f"Photometric Interpretation: {ds.PhotometricInterpretation}")

    # Extract pixel array and convert to NumPy array
    pixel_array = ds.pixel_array

    # Print pixel array info
    print("\n=== Pixel Array ===")
    print(f"Shape: {pixel_array.shape}")
    print(f"Data Type: {pixel_array.dtype}")
    print(f"Min/Max Pixel Value: {pixel_array.min()} / {pixel_array.max()}")

    # Print a small preview (first 10x10 pixels)
    print("\n=== Pixel Array Preview (Top-Left 10x10) ===")
    preview = pixel_array[:20, :20] if pixel_array.ndim == 2 else pixel_array[0, :10, :10]
    for row in preview:
        print(" ".join(f"{pixel:5}" for pixel in row))

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python dicom_pixel_preview.py <path_to_dicom_file>")
    else:
        print_dicom_pixel_array(sys.argv[1])
