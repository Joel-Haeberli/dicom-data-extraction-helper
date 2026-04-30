import os
import pydicom
from pydicom.datadict import keyword_for_tag

def find_dicom_file_by_uid(directory, sop_instance_uid):
    """Search for a DICOM file in the directory with the given SOP Instance UID."""
    for root, _, files in os.walk(directory):
        for file in files:
            try:
                filepath = os.path.join(root, file)
                ds = pydicom.dcmread(filepath, stop_before_pixels=True)
                if hasattr(ds, 'SOPInstanceUID') and ds.SOPInstanceUID == sop_instance_uid:
                    return filepath
            except:
                continue
    return None

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

        if vr == "SQ":  # Sequence
            print("  " * indent + f"{keyword} ({tag}, {vr}): [Sequence]")
            for i, item in enumerate(value):
                print("  " * (indent + 1) + f"Item {i + 1}:")
                print_ps_attributes(item, indent + 2)
        else:
            if len(str(value)) > 100:
                value_str = str(value)[:100] + "..."
            else:
                value_str = str(value)
            print("  " * indent + f"{keyword} ({tag}, {vr}): {value_str}")

def main(ps_filepath, dicom_directory=None):
    """Read a Presentation State file and print all attributes, resolving referenced files."""
    # Load the Presentation State
    ps = pydicom.dcmread(ps_filepath)

    print("=== Presentation State Attributes ===")
    print_ps_attributes(ps)

    # Resolve referenced images
    print("\n=== Referenced Files ===")
    if hasattr(ps, 'ReferencedImageSequence'):
        for ref in ps.ReferencedImageSequence:
            sop_instance_uid = ref.ReferencedSOPInstanceUID
            if dicom_directory:
                filepath = find_dicom_file_by_uid(dicom_directory, sop_instance_uid)
                print(f"SOP Instance UID: {sop_instance_uid} -> {filepath if filepath else 'NOT FOUND'}")
            else:
                print(f"SOP Instance UID: {sop_instance_uid} -> (Provide a DICOM directory to resolve paths)")
    else:
        print("No ReferencedImageSequence found in Presentation State.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Read DICOM Presentation State and resolve referenced files.")
    parser.add_argument("ps_file", help="Path to the Presentation State DICOM file.")
    parser.add_argument("--dicom_dir", help="Directory to search for referenced DICOM files.", default=None)
    args = parser.parse_args()

    main(args.ps_file, args.dicom_dir)
