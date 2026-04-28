#!/usr/bin/env python3
import pydicom
import numpy as np
import argparse
import matplotlib.pyplot as plt

def dicom_to_grayscale_png(dicom_path, png_path, use_hu=True, window=None, level=None):
    """
    Convert a DICOM file to a grayscale PNG (standard medical view).
    Optional: Apply window/level (contrast) settings.
    """
    ds = pydicom.dcmread(dicom_path)

    # Extract pixel array
    pixel_array = ds.pixel_array

    # Convert to HU if requested
    if use_hu and hasattr(ds, 'RescaleSlope') and hasattr(ds, 'RescaleIntercept'):
        pixel_array = pixel_array * float(ds.RescaleSlope) + float(ds.RescaleIntercept)

    # Apply window/level if specified (e.g., window=2000, level=300 for bone)
    if window and level:
        lower = level - window // 2
        upper = level + window // 2
        pixel_array = np.clip(pixel_array, lower, upper)
        pixel_array = (pixel_array - lower) / (upper - lower) * 255
        pixel_array = pixel_array.astype(np.uint8)
    else:
        # Auto-scale to 0-255
        pixel_array = (pixel_array - pixel_array.min()) / (pixel_array.max() - pixel_array.min()) * 255
        pixel_array = pixel_array.astype(np.uint8)

    # Save as grayscale PNG
    plt.imsave(png_path, pixel_array, cmap='gray', format='png', origin='upper')
    print(f"✅ Saved grayscale PNG to {png_path} (shape: {pixel_array.shape})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert DICOM to grayscale PNG (medical view).")
    parser.add_argument("dicom", help="Path to the input DICOM file")
    parser.add_argument("png", help="Path to the output PNG file")
    parser.add_argument("--no-hu", action="store_true", help="Skip HU conversion")
    parser.add_argument("--window", type=int, help="Window width (for contrast, e.g., 2000 for bone)")
    parser.add_argument("--level", type=int, help="Window level (for contrast, e.g., 300 for bone)")
    args = parser.parse_args()

    use_hu = not args.no_hu
    window = args.window if args.window else None
    level = args.level if args.level else None
    dicom_to_grayscale_png(args.dicom, args.png, use_hu=use_hu, window=window, level=level)
