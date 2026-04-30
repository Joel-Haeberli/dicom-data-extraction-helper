#!/usr/bin/env python3
import pydicom
import numpy as np
import argparse
import matplotlib.pyplot as plt
from matplotlib.colors import hsv_to_rgb

def dicom_to_colored_png(dicom_path, png_path, use_hu=True):
    """
    Convert a DICOM file to a high-contrast color-mapped PNG.
    Each unique pixel value (or HU) is assigned a distinct color.
    """
    # Load DICOM
    ds = pydicom.dcmread(dicom_path)

    # Print basic metadata
    print("=== DICOM Metadata ===")
    print(f"Patient Name: {ds.get('PatientName', 'N/A')}")
    print(f"Modality: {ds.get('Modality', 'N/A')}")
    print(f"Image Size: {ds.get('Rows', 'N/A')} x {ds.get('Columns', 'N/A')}")

    # Extract pixel array
    pixel_array = ds.pixel_array

    # Convert to HU if requested and possible (CT, PET, etc.)
    if use_hu and hasattr(ds, 'RescaleSlope') and hasattr(ds, 'RescaleIntercept'):
        pixel_array = pixel_array * float(ds.RescaleSlope) + float(ds.RescaleIntercept)
        print(f"Converted to HU (range: {pixel_array.min():.1f} to {pixel_array.max():.1f})")

    # Get unique values
    unique_values = np.unique(pixel_array)
    num_colors = len(unique_values)
    print(f"Unique pixel values: {num_colors} (min: {unique_values.min()}, max: {unique_values.max()})")

    # Dynamically generate high-contrast colors using golden ratio in HSV space
    golden_ratio = (1 + 5**0.5) / 2  # ~1.618, ensures maximal perceptual separation
    hues = np.mod(np.arange(num_colors) * golden_ratio, 1.0)
    colors_hsv = np.zeros((num_colors, 3))
    colors_hsv[:, 0] = hues  # Hue
    colors_hsv[:, 1] = 1.0   # Full saturation
    colors_hsv[:, 2] = 1.0   # Full brightness
    colors_rgb = hsv_to_rgb(colors_hsv)

    # Map each pixel to a color (vectorized)
    indices = np.searchsorted(unique_values, pixel_array.ravel())
    rgb_image = colors_rgb[indices].reshape(pixel_array.shape + (3,))

    # Save as PNG (1:1 pixel mapping, no DPI metadata issues)
    plt.imsave(
        png_path,
        rgb_image,
        format='png',
        origin='upper'
    )
    print(f"✅ Saved color-mapped PNG to {png_path} (shape: {rgb_image.shape})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert a DICOM file to a high-contrast color-mapped PNG."
    )
    parser.add_argument("dicom", help="Path to the input DICOM file")
    parser.add_argument("png", help="Path to the output PNG file")
    parser.add_argument("--no-hu", action="store_true",
                        help="Skip HU conversion (use raw pixel values)")
    args = parser.parse_args()

    dicom_to_colored_png(args.dicom, args.png, use_hu=not args.no_hu)
