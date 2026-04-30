#!/usr/bin/env python3
import pydicom
import numpy as np
import argparse
import os
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

def analyze_overlays(filepath, visualize=False, save=False, overlay_index=None):
    """Analyze DICOM overlays or Presentation State annotations."""
    ds = pydicom.dcmread(filepath)

    # Print basic DICOM metadata
    print("=== DICOM Metadata ===")
    print(f"Patient Name: {ds.get('PatientName', 'N/A')}")
    print(f"Modality: {ds.get('Modality', 'N/A')}")
    print(f"SOP Class UID: {ds.get('SOPClassUID', 'N/A')}")

    # Check if this is a Presentation State
    is_presentation_state = ds.get('SOPClassUID') == '1.2.840.10008.5.1.4.1.1.11.1'
    if is_presentation_state:
        print("\n⚠️ This is a DICOM Presentation State file (PR).")
        print("   It may contain graphic annotations or references to other DICOM images.")
        print("   Checking for embedded graphic overlays...")

    # Find all overlays (up to 16, as per DICOM standard)
    overlay_indices = []
    for i in range(16):
        if (hasattr(ds, f'OverlayRows{i}') and
            hasattr(ds, f'OverlayColumns{i}') and
            hasattr(ds, f'OverlayData{i}')):
            overlay_indices.append(i)

    if not overlay_indices:
        print("\n❌ No traditional DICOM overlays found in this file.")
        if is_presentation_state:
            # Check for Presentation State annotations (Graphic or Text)
            if hasattr(ds, 'GraphicAnnotationSequence'):
                print("✅ Found Graphic Annotations in Presentation State.")
                for idx, annotation in enumerate(ds.GraphicAnnotationSequence):
                    print(f"\n=== Graphic Annotation {idx} ===")
                    print(f"Type: {annotation.get('GraphicType', 'N/A')}")
                    print(f"Data: {annotation.get('GraphicData', 'N/A')}")
            else:
                print("❌ No Graphic Annotations found in Presentation State.")
        return

    print(f"\n✅ Found {len(overlay_indices)} overlay(s) in this file.")

    # Analyze each overlay
    for idx in overlay_indices:
        if overlay_index is not None and idx != overlay_index:
            continue

        print(f"\n=== Overlay {idx} ===")
        overlay_rows = getattr(ds, f'OverlayRows{idx}', None)
        overlay_cols = getattr(ds, f'OverlayColumns{idx}', None)
        overlay_type = getattr(ds, f'OverlayType{idx}', 'UNKNOWN')
        overlay_origin = getattr(ds, f'OverlayOrigin{idx}', [1, 1])
        overlay_bits = getattr(ds, f'OverlayBitsAllocated{idx}', 1)
        overlay_desc = getattr(ds, f'OverlayDescription{idx}', 'N/A')

        print(f"Type: {overlay_type}")
        print(f"Description: {overlay_desc}")
        print(f"Dimensions: {overlay_rows} x {overlay_cols}")
        print(f"Bits Allocated: {overlay_bits}")
        print(f"Origin (x, y): {overlay_origin}")

        # Extract overlay data
        overlay_data = getattr(ds, f'OverlayData{idx}').value
        overlay_array = np.frombuffer(overlay_data, dtype=np.uint8)

        # Unpack bits if 1-bit overlay
        if overlay_bits == 1:
            overlay_array = np.unpackbits(overlay_array, axis=None)[:overlay_rows * overlay_cols]
        overlay_array = overlay_array.reshape(overlay_rows, overlay_cols)

        # Calculate statistics
        num_pixels = overlay_array.size
        num_nonzero = np.count_nonzero(overlay_array)
        coverage = (num_nonzero / num_pixels) * 100

        print(f"Non-zero Pixels: {num_nonzero} / {num_pixels} ({coverage:.2f}% coverage)")

        # Visualization (only if main image exists)
        if visualize or save:
            try:
                main_image = ds.pixel_array
                if hasattr(ds, 'RescaleSlope') and hasattr(ds, 'RescaleIntercept'):
                    main_image = main_image * float(ds.RescaleSlope) + float(ds.RescaleIntercept)
                main_image = (main_image - main_image.min()) / (main_image.max() - main_image.min())
            except AttributeError:
                print("⚠️ Main image pixel data not available. Skipping visualization.")
                continue

            # Create RGB image
            rgb_image = np.stack([main_image, main_image, main_image], axis=-1)

            # Apply overlay (red)
            overlay_mask = overlay_array > 0
            rgb_image[overlay_mask] = [1, 0, 0]  # Red

            if visualize:
                plt.figure(figsize=(10, 5))
                plt.title(f"Overlay {idx} (Type: {overlay_type}, Coverage: {coverage:.2f}%)")
                plt.imshow(rgb_image)
                legend_elements = [Patch(facecolor='red', label='Overlay')]
                plt.legend(handles=legend_elements)
                plt.colorbar(label='Intensity')
                plt.show()

            if save:
                output_dir = os.path.splitext(filepath)[0] + "_overlays"
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, f"overlay_{idx}.png")
                plt.imsave(output_path, rgb_image)
                print(f"✅ Saved overlay {idx} visualization to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze DICOM overlays or Presentation State annotations."
    )
    parser.add_argument("file", help="Path to the DICOM file")
    parser.add_argument("--visualize", action="store_true", help="Show overlay visualizations")
    parser.add_argument("--save", action="store_true", help="Save overlay visualizations as PNG")
    parser.add_argument("--overlay-index", type=int, help="Analyze only this overlay index (0-15)")
    args = parser.parse_args()

    analyze_overlays(
        args.file,
        visualize=args.visualize,
        save=args.save,
        overlay_index=args.overlay_index
    )
