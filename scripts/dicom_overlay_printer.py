import os
import argparse
import numpy as np
import pydicom
from pydicom.datadict import keyword_for_tag
from PIL import Image, ImageDraw

# --- Helper Functions ---
def print_ps_attributes(ps_dataset, indent=0):
    """Recursively print all attributes of a DICOM dataset."""
    for elem in ps_dataset:
        tag = elem.tag
        try:
            keyword = keyword_for_tag(tag)
        except KeyError:
            keyword = f"Unknown({tag})"
        vr = elem.VR
        value = elem.value

        if vr == "SQ":
            print("  " * indent + f"{keyword} ({tag}, {vr}): [Sequence]")
            for i, item in enumerate(value):
                print("  " * (indent + 1) + f"Item {i + 1}:")
                print_ps_attributes(item, indent + 2)
        else:
            value_str = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
            print("  " * indent + f"{keyword} ({tag}, {vr}): {value_str}")

def extract_overlay_only(ps, output_path="overlay_only.png"):
    """Extract OverlayData from Presentation State and save as PNG."""
    # Check for overlay groups (6000, 6002, 6004, etc.)
    overlay_groups = [group for group in range(0x6000, 0x60FF, 2) if (group, 0x3000) in ps]

    if not overlay_groups:
        print("No OverlayData found in Presentation State.")
        return

    for group in overlay_groups:
        # Extract overlay parameters
        rows = ps[(group, 0x0010)].value if (group, 0x0010) in ps else 512
        cols = ps[(group, 0x0011)].value if (group, 0x0011) in ps else 512
        bits_allocated = ps[(group, 0x0100)].value if (group, 0x0100) in ps else 1
        overlay_data = ps[(group, 0x3000)].value

        # Decode the overlay data
        if bits_allocated == 1:
            overlay_array = np.unpackbits(np.frombuffer(overlay_data, dtype=np.uint8))
            overlay_array = overlay_array.reshape((rows, cols))
        else:
            overlay_array = np.frombuffer(overlay_data, dtype=np.uint16 if bits_allocated == 16 else np.uint8)
            overlay_array = overlay_array.reshape((rows, cols))

        # Normalize and invert for visibility
        overlay_image = overlay_array.astype(np.uint8)
        if bits_allocated == 1:
            overlay_image = 255 - overlay_image  # Invert so 0=black, 1=white

        # Save as PNG
        img = Image.fromarray(overlay_image)
        img.save(output_path)
        print(f"Saved overlay (group {group:04X}) to {output_path}")
        return

    print("No valid OverlayData found.")

def render_overlay_on_image(ps, dicom_dir=None, output_path="overlayed.png"):
    """Render the referenced image in grayscale with overlay in red."""
    if not hasattr(ps, 'ReferencedImageSequence'):
        print("No ReferencedImageSequence found in Presentation State.")
        return

    # Find the first referenced image
    ref = ps.ReferencedImageSequence[0]
    sop_instance_uid = ref.ReferencedSOPInstanceUID
    if not dicom_dir:
        print("Please provide --dicom_dir to locate the referenced image.")
        return

    # Locate the referenced DICOM file
    image_path = None
    for root, _, files in os.walk(dicom_dir):
        for file in files:
            try:
                filepath = os.path.join(root, file)
                ds = pydicom.dcmread(filepath, stop_before_pixels=True)
                if hasattr(ds, 'SOPInstanceUID') and ds.SOPInstanceUID == sop_instance_uid:
                    image_path = filepath
                    break
            except:
                continue
        if image_path:
            break

    if not image_path:
        print(f"Referenced image with UID {sop_instance_uid} not found in {dicom_dir}.")
        return

    # Load the referenced image
    image_ds = pydicom.dcmread(image_path)
    pixel_array = image_ds.pixel_array

    # Apply windowing if available
    if hasattr(image_ds, "WindowCenter") and hasattr(image_ds, "WindowWidth"):
        center = image_ds.WindowCenter[0] if isinstance(image_ds.WindowCenter, list) else image_ds.WindowCenter
        width = image_ds.WindowWidth[0] if isinstance(image_ds.WindowWidth, list) else image_ds.WindowWidth
        pixel_array = np.clip((pixel_array - center) / width * 255, 0, 255).astype(np.uint8)
    else:
        pixel_array = ((pixel_array - pixel_array.min()) / (pixel_array.max() - pixel_array.min()) * 255).astype(np.uint8)

    # Convert to PIL Image (grayscale)
    img = Image.fromarray(pixel_array).convert("L")

    # Extract overlay data
    overlay_groups = [group for group in range(0x6000, 0x60FF, 2) if (group, 0x3000) in ps]
    if not overlay_groups:
        print("No OverlayData found in Presentation State.")
        return

    for group in overlay_groups:
        rows = ps[(group, 0x0010)].value if (group, 0x0010) in ps else image_ds.Rows
        cols = ps[(group, 0x0011)].value if (group, 0x0011) in ps else image_ds.Columns
        bits_allocated = ps[(group, 0x0100)].value if (group, 0x0100) in ps else 1
        overlay_data = ps[(group, 0x3000)].value
        origin_x = ps[(group, 0x0050)].value[0] if (group, 0x0050) in ps else 0
        origin_y = ps[(group, 0x0050)].value[1] if (group, 0x0050) in ps else 0

        # Decode overlay
        if bits_allocated == 1:
            overlay_array = np.unpackbits(np.frombuffer(overlay_data, dtype=np.uint8))
            overlay_array = overlay_array.reshape((rows, cols))
        else:
            overlay_array = np.frombuffer(overlay_data, dtype=np.uint16 if bits_allocated == 16 else np.uint8)
            overlay_array = overlay_array.reshape((rows, cols))

        overlay_image = overlay_array.astype(np.uint8)
        if bits_allocated == 1:
            overlay_image = 255 - overlay_image  # Invert for visibility

        # Create a red overlay
        red_overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        overlay_pil = Image.fromarray(overlay_image).convert("L")
        overlay_pil = overlay_pil.resize(img.size, Image.LANCZOS)

        # Paste the overlay in red
        red_pixels = [(255, 0, 0, 200) if p > 0 else (0, 0, 0, 0) for p in overlay_pil.getdata()]
        red_overlay.putdata(red_pixels)

        # Combine images
        img = img.convert("RGBA")
        combined = Image.alpha_composite(img, red_overlay)
        combined.save(output_path)
        print(f"Saved overlayed image (group {group:04X}) to {output_path}")
        return

    print("No valid overlay to render.")

# --- Main ---
def main():
    parser = argparse.ArgumentParser(description="Process DICOM Presentation State.")
    parser.add_argument("ps_file", help="Path to the Presentation State DICOM file.")
    parser.add_argument("--details", action="store_true", help="Print all attributes.")
    parser.add_argument("--overlay-only", action="store_true", help="Save OverlayData as PNG.")
    parser.add_argument("--overlay", action="store_true", help="Save referenced image with overlay in red.")
    parser.add_argument("--dicom_dir", help="Directory to search for referenced DICOM files.", default=None)
    args = parser.parse_args()

    ps = pydicom.dcmread(args.ps_file)

    if args.details:
        print("=== Presentation State Attributes ===")
        print_ps_attributes(ps)

    if args.overlay_only:
        extract_overlay_only(ps, "overlay_only.png")

    if args.overlay:
        render_overlay_on_image(ps, args.dicom_dir, "overlayed.png")

if __name__ == "__main__":
    main()
