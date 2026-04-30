import pydicom
import sys

def print_hex_dump(data, address=0, bytes_per_line=16):
    """Print a hex dump of the given byte data."""
    for i in range(0, len(data), bytes_per_line):
        chunk = data[i:i+bytes_per_line]
        hex_part = ' '.join(f'{b:02x}' for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
        print(f"{address + i:08x}  {hex_part:<48}  {ascii_part}")

def main(dicom_file):
    ds = pydicom.dcmread(dicom_file)

    # Find all overlay groups (6000, 6002, 6004, etc.)
    overlay_groups = [group for group in range(0x6000, 0x60FF, 2) if (group, 0x3000) in ds]

    if not overlay_groups:
        print("No OverlayData found in the DICOM file.")
        return

    for group in overlay_groups:
        overlay_data = ds[(group, 0x3000)].value
        print(f"\n=== OverlayData for group {group:04X} ===")
        print(f"Length: {len(overlay_data)} bytes")
        print_hex_dump(overlay_data)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python hex_dump_overlay.py <dicom_file>")
        sys.exit(1)
    main(sys.argv[1])
