import pydicom
import numpy as np
import argparse
import os

def print_dicom_pixel_array(filepath, convert_to_hu=False, apply_overlay=False, overlay_file=None):
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

    # Extract pixel array
    pixel_array = ds.pixel_array

    # Convert to HU if requested and if rescale attributes exist
    if convert_to_hu and hasattr(ds, 'RescaleSlope') and hasattr(ds, 'RescaleIntercept'):
        slope = float(ds.RescaleSlope)
        intercept = float(ds.RescaleIntercept)
        pixel_array = pixel_array * slope + intercept
        print(f"Rescale Slope: {slope}, Rescale Intercept: {intercept}")
        print("Pixel array converted to Hounsfield Units (HU).")

    # Apply overlay if requested
    if apply_overlay:
        if overlay_file is None:
            print("Error: --overlay-file is required when using --apply-overlay")
            return

        # Read overlay file
        overlay_ds = pydicom.dcmread(overlay_file)
        overlay_array = overlay_ds.pixel_array

        # For multi-frame overlays, use the first frame
        if overlay_array.ndim == 3:
            overlay_array = overlay_array[0]

        # Check dimensions
        if pixel_array.shape != overlay_array.shape:
            print(f"Error: Main image shape {pixel_array.shape} does not match overlay shape {overlay_array.shape}")
            return

        # Apply overlay (element-wise multiplication with binary mask)
        pixel_array = pixel_array * (overlay_array > 0)
        print(f"Applied overlay from {overlay_file}")

    # Print pixel array info
    print("\n=== Pixel Array ===")
    print(f"Shape: {pixel_array.shape}")
    print(f"Data Type: {pixel_array.dtype}")
    print(f"Min/Max Pixel Value: {pixel_array.min()} / {pixel_array.max()}")

    # Print a small preview (first 10x10 pixels)
    print("\n=== Pixel Array Preview (Top-Left 10x10) ===")
    preview = pixel_array[:10, :10] if pixel_array.ndim == 2 else pixel_array[0, :10, :10]
    for row in preview:
        print(" ".join(f"{pixel:8.2f}" if convert_to_hu else f"{pixel:5}" for pixel in row))

    # Save to file if overlay was applied
    if apply_overlay:
        base_name = os.path.splitext(filepath)[0]
        suffix = "_hu" if convert_to_hu else ""
        output_filename = f"{base_name}{suffix}_with_overlay.npy"
        np.save(output_filename, pixel_array)
        print(f"\nSaved pixel array with overlay to {output_filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Print DICOM pixel array with optional HU conversion and overlay application.")
    parser.add_argument("file", help="Path to the DICOM file")
    parser.add_argument("--hu", action="store_true", help="Convert pixel values to Hounsfield Units (HU)")
    parser.add_argument("--apply-overlay", action="store_true", help="Apply overlay from a separate DICOM file")
    parser.add_argument("--overlay-file", help="Path to the DICOM file containing the overlay")
    args = parser.parse_args()

    # If --apply-overlay is set, --overlay-file must be provided
    if args.apply_overlay and not args.overlay_file:
        parser.error("--overlay-file is required when using --apply-overlay")

    print_dicom_pixel_array(args.file, convert_to_hu=args.hu, apply_overlay=args.apply_overlay, overlay_file=args.overlay_file)
