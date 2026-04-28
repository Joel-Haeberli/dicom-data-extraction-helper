#!/usr/bin/env python3
import pydicom
import numpy as np
import argparse
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

def dicom_to_anatomical_color_png(dicom_path, png_path, use_hu=True):
    """
    Convert a DICOM file to a color-mapped PNG with anatomical meaning.
    Similar HU ranges (e.g., bone, soft tissue) share similar colors.
    """
    ds = pydicom.dcmread(dicom_path)

    # Print basic metadata
    print("=== DICOM Metadata ===")
    print(f"Patient Name: {ds.get('PatientName', 'N/A')}")
    print(f"Modality: {ds.get('Modality', 'N/A')}")
    print(f"Image Size: {ds.get('Rows', 'N/A')} x {ds.get('Columns', 'N/A')}")

    # Extract pixel array
    pixel_array = ds.pixel_array

    # Convert to HU if requested
    if use_hu and hasattr(ds, 'RescaleSlope') and hasattr(ds, 'RescaleIntercept'):
        pixel_array = pixel_array * float(ds.RescaleSlope) + float(ds.RescaleIntercept)
        print(f"Converted to HU (range: {pixel_array.min():.1f} to {pixel_array.max():.1f})")

    # Define HU ranges and corresponding colors (RGB)
    # Format: (HU_min, HU_max, [R, G, B])
    hu_ranges = [
        (-1024, -800,   [0,   0,   255]),   # Air (blue)
        (-800,  -50,    [255, 255,   0]),   # Fat (yellow)
        (-50,    50,     [0,   255,   0]),   # Soft tissue (green)
        (50,     300,    [255, 165,   0]),   # Muscle (orange)
        (300,    1000,   [255, 255, 255]),   # Bone (white)
        (1000,   3000,   [255, 200, 200])   # High-density (light pink)
    ]

    # Create an RGB image
    rgb_image = np.zeros(pixel_array.shape + (3,), dtype=np.uint8)

    # Assign colors based on HU ranges
    for (hu_min, hu_max, color) in hu_ranges:
        mask = (pixel_array >= hu_min) & (pixel_array <= hu_max)
        rgb_image[mask] = color

    # For HU values outside defined ranges, use a fallback (gray)
    fallback_mask = ~np.any([(pixel_array >= hu_min) & (pixel_array <= hu_max) for (hu_min, hu_max, _) in hu_ranges], axis=0)
    rgb_image[fallback_mask] = [128, 128, 128]  # Gray

    # Save as PNG
    plt.imsave(png_path, rgb_image, format='png', origin='upper')
    print(f"✅ Saved anatomical color-mapped PNG to {png_path} (shape: {rgb_image.shape})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert DICOM to anatomical color-mapped PNG (HU ranges -> colors)."
    )
    parser.add_argument("dicom", help="Path to the input DICOM file")
    parser.add_argument("png", help="Path to the output PNG file")
    parser.add_argument("--no-hu", action="store_true", help="Skip HU conversion")
    args = parser.parse_args()

    dicom_to_anatomical_color_png(args.dicom, args.png, use_hu=not args.no_hu)
