import os
import argparse
import numpy as np
import pydicom
from PIL import Image

def unpack_bits(data, rows, cols, msb_first=False):
    """Unpack 1-bit overlay data, with optional MSB first."""
    unpacked = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
    if msb_first:
        unpacked = unpacked.reshape(-1, 8)[:, ::-1].reshape(-1)
    return unpacked.reshape((rows, cols))

def find_referenced_image(ps, dicom_dir):
    """Find the first referenced DICOM image in the given directory."""
    ref_sequence = None

    if hasattr(ps, 'ReferencedImageSequence'):
        ref_sequence = ps.ReferencedImageSequence
    elif hasattr(ps, 'ReferencedSeriesSequence') and len(ps.ReferencedSeriesSequence) > 0:
        ref_sequence = ps.ReferencedSeriesSequence[0].ReferencedImageSequence

    if ref_sequence is None or len(ref_sequence) == 0:
        print("No ReferencedImageSequence or ReferencedSeriesSequence found in Presentation State.")
        return None

    ref = ref_sequence[0]
    sop_instance_uid = ref.ReferencedSOPInstanceUID
    print(f"Searching for referenced image with UID: {sop_instance_uid}")
    print(f"Searching in directory: {dicom_dir}")

    for root, _, files in os.walk(dicom_dir):
        for file in files:
            try:
                filepath = os.path.join(root, file)
                ds = pydicom.dcmread(filepath, stop_before_pixels=True)
                if hasattr(ds, 'SOPInstanceUID') and ds.SOPInstanceUID == sop_instance_uid:
                    print(f"Found referenced image: {filepath}")
                    return filepath
            except Exception as e:
                print(f"Skipping {filepath} (error: {e})")
                continue
    print(f"Referenced image with UID {sop_instance_uid} not found in {dicom_dir}.")
    return None

def extract_roi_mask(ps, output_path="roi_mask.png", msb_first=False):
    """Extract ROI mask from OverlayData and save as PNG."""
    overlay_groups = [group for group in range(0x6000, 0x60FF, 2) if (group, 0x3000) in ps]
    if not overlay_groups:
        print("No OverlayData found in Presentation State.")
        return

    for group in overlay_groups:
        rows = ps[(group, 0x0010)].value
        cols = ps[(group, 0x0011)].value
        bits_allocated = ps[(group, 0x0100)].value
        overlay_data = ps[(group, 0x3000)].value

        if bits_allocated == 1:
            overlay_array = unpack_bits(overlay_data, rows, cols, msb_first)
        else:
            overlay_array = np.frombuffer(overlay_data, dtype=np.uint16 if bits_allocated == 16 else np.uint8)
            overlay_array = overlay_array.reshape((rows, cols))

        roi_mask = (overlay_array == 0).astype(np.uint8) * 255
        img = Image.fromarray(roi_mask)
        img.save(output_path)
        print(f"Saved ROI mask to {output_path}")
        return

def render_roi_on_image(ps, dicom_dir, output_path="image_with_roi.png", msb_first=False):
    """Render the referenced image in grayscale with ROI overlay in red, positioned correctly."""
    image_path = find_referenced_image(ps, dicom_dir)
    if not image_path:
        return

    # Load the referenced image
    image_ds = pydicom.dcmread(image_path)
    pixel_array = image_ds.pixel_array

    # Apply windowing (use first window if multiple)
    if hasattr(image_ds, "WindowCenter") and hasattr(image_ds, "WindowWidth"):
        def get_first_value(attr):
            if hasattr(attr, '__getitem__') and not isinstance(attr, str):
                return float(attr[0])
            return float(attr)
        center = get_first_value(image_ds.WindowCenter)
        width = get_first_value(image_ds.WindowWidth)
        pixel_array = np.clip((pixel_array - center) / width * 255, 0, 255).astype(np.uint8)
    else:
        pixel_array = ((pixel_array - pixel_array.min()) / (pixel_array.max() - pixel_array.min()) * 255).astype(np.uint8)

    # Convert to grayscale PIL Image
    img_gray = Image.fromarray(pixel_array).convert("L")
    img_width, img_height = img_gray.size

    # Extract ROI mask from OverlayData
    overlay_groups = [group for group in range(0x6000, 0x60FF, 2) if (group, 0x3000) in ps]
    if not overlay_groups:
        print("No OverlayData found in Presentation State.")
        return

    for group in overlay_groups:
        # Overlay dimensions and origin
        overlay_rows = ps[(group, 0x0010)].value
        overlay_cols = ps[(group, 0x0011)].value
        overlay_origin = ps[(group, 0x0050)].value if (group, 0x0050) in ps else [0, 0]
        overlay_x, overlay_y = overlay_origin[0], overlay_origin[1]
        bits_allocated = ps[(group, 0x0100)].value
        overlay_data = ps[(group, 0x3000)].value

        # Decode overlay data
        if bits_allocated == 1:
            overlay_array = unpack_bits(overlay_data, overlay_rows, overlay_cols, msb_first)
        else:
            overlay_array = np.frombuffer(overlay_data, dtype=np.uint16 if bits_allocated == 16 else np.uint8)
            overlay_array = overlay_array.reshape((overlay_rows, overlay_cols))

        # For ROI: 1 = inside ROI, 0 = outside ROI (adjust if needed)
        roi_mask = (overlay_array == 1).astype(np.uint8) * 255
        roi_pil = Image.fromarray(roi_mask).convert("L")

        # Create a blank RGBA image for the overlay
        overlay_img = Image.new("RGBA", (img_width, img_height), (0, 0, 0, 0))

        # Paste the ROI mask at (overlay_x, overlay_y)
        # Crop the ROI if it extends beyond the image boundaries
        roi_width, roi_height = roi_pil.size
        paste_box = (
            max(0, overlay_x),
            max(0, overlay_y),
            min(overlay_x + roi_width, img_width),
            min(overlay_y + roi_height, img_height)
        )
        if paste_box[2] > paste_box[0] and paste_box[3] > paste_box[1]:
            # Crop the ROI to the visible region
            roi_cropped = roi_pil.crop((
                max(0, -overlay_x),
                max(0, -overlay_y),
                min(roi_width, img_width - overlay_x),
                min(roi_height, img_height - overlay_y)
            ))
            overlay_img.paste(
                Image.new("RGBA", roi_cropped.size, (255, 0, 0, 180)),
                paste_box,
                roi_cropped
            )

        # Convert grayscale image to RGBA and composite with overlay
        img_rgba = img_gray.convert("RGBA")
        combined = Image.alpha_composite(img_rgba, overlay_img)
        combined.save(output_path)
        print(f"Saved image with ROI overlay to {output_path}")
        return

    print("No valid ROI overlay to render.")

def main():
    parser = argparse.ArgumentParser(description="Render ROI overlay from DICOM Presentation State with MSB/LSB toggle.")
    parser.add_argument("ps_file", help="Path to the Presentation State DICOM file.")
    parser.add_argument("--overlay-only", action="store_true", help="Save ROI mask as PNG.")
    parser.add_argument("--overlay", action="store_true", help="Save referenced image with ROI overlay in red.")
    parser.add_argument("--dicom_dir", help="Directory to search for referenced DICOM files.", default=None)
    parser.add_argument("--msb", action="store_true", help="Use MSB first bit order (default: LSB first).")
    args = parser.parse_args()

    ps = pydicom.dcmread(args.ps_file)

    if args.overlay_only:
        extract_roi_mask(ps, "roi_mask.png", args.msb)
    if args.overlay:
        if not args.dicom_dir:
            print("Error: --dicom_dir is required for --overlay.")
            return
        render_roi_on_image(ps, args.dicom_dir, "image_with_roi.png", args.msb)

if __name__ == "__main__":
    main()
