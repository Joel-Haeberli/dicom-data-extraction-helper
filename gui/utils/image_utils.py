#!usr/bin/env python3
"""
Image Conversion and Processing Utilities for GUI Application

Converts DICOM pixel data to QImage and handles overlay compositing.
Inspired by existing dicom_to_png.py and dicom_overlay_printer.py scripts.
"""

from typing import Optional, Tuple, List
import numpy as np

from PySide6.QtGui import QImage, QPixmap, QPainter, qRgb
from PySide6.QtCore import QSize, Qt

try:
    import pydicom
    from pydicom.dataset import Dataset
    HAS_PYDICOM = True
except ImportError:
    HAS_PYDICOM = False


def dicom_to_qimage(ds: Dataset) -> Optional[QImage]:
    """
    Convert DICOM pixel data to QImage.
    
    Handles:
    - Rescale slope/intercept (HU conversion for CT)
    - Window center/width application
    - Photometric interpretation (MONOCHROME1, MONOCHROME2, RGB)
    - Bit depth normalization to 8-bit
    
    Args:
        ds: pydicom Dataset with pixel data
        
    Returns:
        QImage in appropriate format, or None if conversion fails
    """
    if not HAS_PYDICOM or 'pixel_array' not in dir(ds):
        return None
    
    try:
        # Get pixel array
        pixel_array = ds.pixel_array
        
        # Apply rescale slope and intercept if available (for CT HU conversion)
        # These can be single values or sequences - handle both
        slope = ds.get('RescaleSlope', 1)
        intercept = ds.get('RescaleIntercept', 0)
        
        # Convert to float, handling sequences by taking first value
        if hasattr(slope, '__iter__') and not isinstance(slope, str):
            slope = float(slope[0]) if len(slope) > 0 else 1.0
        else:
            slope = float(slope)
        
        if hasattr(intercept, '__iter__') and not isinstance(intercept, str):
            intercept = float(intercept[0]) if len(intercept) > 0 else 0.0
        else:
            intercept = float(intercept)
        
        if slope != 1 or intercept != 0:
            pixel_array = pixel_array * slope + intercept
        
        # Apply window center/width if available
        if hasattr(ds, 'WindowCenter') and hasattr(ds, 'WindowWidth'):
            center = ds.WindowCenter
            width = ds.WindowWidth
            
            # Handle sequences - take first value
            if hasattr(center, '__iter__') and not isinstance(center, str):
                center = float(center[0]) if len(center) > 0 else 0
            else:
                center = float(center)
            
            if hasattr(width, '__iter__') and not isinstance(width, str):
                width_val = float(width[0]) if len(width) > 0 else 0
            else:
                width_val = float(width)
            
            if width_val != 0:
                # Window/level transformation
                pixel_array = np.clip(
                    ((pixel_array.astype(np.float32) - center) / width_val) * 255 + 127.5,
                    0,
                    255
                ).astype(np.uint8)
            else:
                # Normalize to 0-255 range
                pixel_array = _normalize_to_8bit(pixel_array)
        else:
            # Normalize to 0-255 range
            pixel_array = _normalize_to_8bit(pixel_array)
        
        # Handle photometric interpretation
        photo_interp = ds.get('PhotometricInterpretation', 'MONOCHROME2')
        
        rows = int(ds.Rows)
        cols = int(ds.Columns)
        
        if photo_interp == 'MONOCHROME1':
            # 0 = white, max = black - invert
            pixel_array = 255 - pixel_array
            qimage = _numpy_to_qimage_grayscale(pixel_array, cols, rows)
        elif photo_interp == 'MONOCHROME2':
            # 0 = black, max = white - direct
            qimage = _numpy_to_qimage_grayscale(pixel_array, cols, rows)
        elif photo_interp == 'RGB':
            qimage = _numpy_to_qimage_rgb(pixel_array, cols, rows)
        elif photo_interp == 'YBR_FULL' or photo_interp == 'YBR_FULL_422':
            # Convert YBR to RGB
            pixel_array = _ybr_to_rgb(pixel_array)
            qimage = _numpy_to_qimage_rgb(pixel_array, cols, rows)
        else:
            # Default: treat as grayscale
            if pixel_array.ndim == 3:
                # If 3D (multi-frame), take first frame
                pixel_array = pixel_array[0]
            qimage = _numpy_to_qimage_grayscale(pixel_array, cols, rows)
        
        return qimage
        
    except Exception as e:
        print(f"Error converting DICOM to QImage: {e}")
        return None


def _normalize_to_8bit(pixel_array: np.ndarray) -> np.ndarray:
    """
    Normalize pixel array to 8-bit range (0-255).
    
    Args:
        pixel_array: Input pixel array of any bit depth
        
    Returns:
        8-bit unsigned integer array
    """
    # Handle different dtypes
    if pixel_array.dtype == np.uint8:
        return pixel_array
    elif pixel_array.dtype == np.uint16:
        # Scale from 16-bit to 8-bit
        return (pixel_array / 256).astype(np.uint8)
    elif pixel_array.dtype == np.int16:
        # Handle signed 16-bit (common for CT)
        # First convert to float for proper scaling
        pixel_array = pixel_array.astype(np.float32)
        img_min = pixel_array.min()
        img_max = pixel_array.max()
        if img_max - img_min > 0:
            pixel_array = ((pixel_array - img_min) / (img_max - img_min) * 255).astype(np.uint8)
        else:
            pixel_array = np.zeros_like(pixel_array, dtype=np.uint8)
        return pixel_array
    elif pixel_array.dtype == np.float32 or pixel_array.dtype == np.float64:
        img_min = pixel_array.min()
        img_max = pixel_array.max()
        if img_max - img_min > 0:
            pixel_array = ((pixel_array - img_min) / (img_max - img_min) * 255).astype(np.uint8)
        else:
            pixel_array = np.zeros_like(pixel_array, dtype=np.uint8)
        return pixel_array
    else:
        # Fallback: clip and convert
        return np.clip(pixel_array, 0, 255).astype(np.uint8)


def _numpy_to_qimage_grayscale(pixel_array: np.ndarray, width: int, height: int) -> QImage:
    """
    Convert a 2D numpy array to a grayscale QImage.
    
    Args:
        pixel_array: 2D numpy array (H, W) with values 0-255
        width: Image width
        height: Image height
        
    Returns:
        QImage in Format_Grayscale8
    """
    # Ensure array is 2D and uint8
    if pixel_array.ndim != 2:
        pixel_array = pixel_array.squeeze()
    
    if pixel_array.shape[0] != height or pixel_array.shape[1] != width:
        # Transpose if needed
        if pixel_array.shape[0] == width and pixel_array.shape[1] == height:
            pixel_array = pixel_array.T
    
    pixel_array = pixel_array.astype(np.uint8)
    
    # Create QImage from numpy array
    # QImage expects bytes in row-major order (width x height)
    bytes_data = pixel_array.tobytes()
    
    qimage = QImage(bytes_data, width, height, QImage.Format_Grayscale8)
    return qimage


def _numpy_to_qimage_rgb(pixel_array: np.ndarray, width: int, height: int) -> QImage:
    """
    Convert a 3D numpy array to an RGB QImage.
    
    Args:
        pixel_array: 3D numpy array (H, W, 3 or H, W, 4) with values 0-255
        width: Image width
        height: Image height
        
    Returns:
        QImage in Format_RGB888 or Format_ARGB32
    """
    # Ensure array is 3D
    if pixel_array.ndim == 2:
        # Convert grayscale to RGB
        pixel_array = np.stack((pixel_array,) * 3, axis=-1)
    
    # Handle shape
    if pixel_array.shape[0] != height or pixel_array.shape[1] != width:
        if pixel_array.shape[0] == width and pixel_array.shape[1] == height:
            pixel_array = np.transpose(pixel_array, (1, 0, 2))
    
    # Ensure we have 3 or 4 channels
    if pixel_array.shape[2] == 4:
        # RGBA
        pixel_array = pixel_array.astype(np.uint8)
        bytes_data = pixel_array.tobytes()
        qimage = QImage(bytes_data, width, height, QImage.Format_ARGB32)
    else:
        # RGB - need to convert to ARGB format
        pixel_array = pixel_array.astype(np.uint8)
        # QImage.Format_RGB888 expects bytes in RGB order, but we need to ensure proper layout
        bytes_data = pixel_array.tobytes()
        qimage = QImage(bytes_data, width, height, QImage.Format_RGB888)
        # Convert to ARGB if needed
        if qimage.format() != QImage.Format_ARGB32:
            qimage = qimage.convertToFormat(QImage.Format_ARGB32)
    
    return qimage


def _ybr_to_rgb(pixel_array: np.ndarray) -> np.ndarray:
    """
    Convert YBR color space to RGB.
    
    Args:
        pixel_array: YBR pixel array
        
    Returns:
        RGB pixel array
    """
    # For 3D array with YBR values
    if pixel_array.ndim == 3 and pixel_array.shape[2] == 3:
        # YBR to RGB conversion matrix
        # This is a simplified conversion
        ybr = pixel_array.astype(np.float32)
        rgb = np.zeros_like(ybr)
        
        rgb[..., 0] = ybr[..., 0] + 1.402 * ybr[..., 2]  # R = Y + 1.402*V
        rgb[..., 1] = ybr[..., 0] - 0.344136 * ybr[..., 1] - 0.714136 * ybr[..., 2]  # G = Y - 0.344*Cb - 0.714*Cr
        rgb[..., 2] = ybr[..., 0] + 1.772 * ybr[..., 1]  # B = Y + 1.772*Cb
        
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)
        return rgb
    
    return pixel_array


def extract_overlay_array(ds: Dataset, overlay_index: int = 0) -> Optional[np.ndarray]:
    """
    Extract overlay array from a DICOM dataset.
    
    Handles MSB/LSB bit ordering via OverlayBitPosition attribute.
    
    Tries multiple methods:
    1. Traditional DICOM overlay (overlay_array method)
    2. Presentation State overlay groups (0x6000-0x60FF)
    3. Image pixel data for mask images
    
    Args:
        ds: pydicom Dataset
        overlay_index: Index of overlay to extract (default 0)
        
    Returns:
        Numpy array of overlay data, or None
    """
    if not HAS_PYDICOM:
        return None
    
    try:
        # Method 1: Try traditional DICOM overlay via pydicom
        # Note: This requires pixel data to be loaded (stop_before_pixels=False)
        
        # Method 2: Check for Presentation State overlay groups or image overlays
        # Look for groups 6000-60FF with OverlayData
        for group in range(0x6000, 0x60FF, 2):
            # Get rows and columns
            rows_tag = (group, 0x0010)
            cols_tag = (group, 0x0011)
            bits_tag = (group, 0x0100)
            bit_pos_tag = (group, 0x0102)
            data_tag = (group, 0x3000)
            
            if data_tag in ds:
                overlay_data = ds[data_tag].value
                rows = ds[rows_tag].value if rows_tag in ds else None
                cols = ds[cols_tag].value if cols_tag in ds else None
                bits_allocated = ds[bits_tag].value if bits_tag in ds else 1
                bit_position = ds[bit_pos_tag].value if bit_pos_tag in ds else 0
                
                if rows is None or cols is None:
                    continue
                
                # Decode overlay data
                if bits_allocated == 1:
                    # Bit-packed overlay (1 bit per pixel)
                    overlay_bytes = np.frombuffer(overlay_data, dtype=np.uint8)
                    
                    # Unpack bits - default is LSB first
                    overlay_array = np.unpackbits(overlay_bytes, bitorder='little')
                    
                    # Trim to expected size
                    if len(overlay_array) > rows * cols:
                        overlay_array = overlay_array[:rows * cols]
                    
                    # Handle bit position (MSB/LSB ordering)
                    # DICOM standard: OverlayBitPosition = bit number of MSB
                    # For 1-bit packed overlays:
                    # - bit 0 is LSB, bit 7 is MSB in standard byte ordering
                    # - OverlayBitPosition tells us which bit is MSB (and for 1-bit, the pixel bit)
                    # If OverlayBitPosition = 0: bit 0 is the pixel bit (LSB first, no reversal)
                    # If OverlayBitPosition = 7: bit 7 is the pixel bit (MSB first, need reversal)
                    # np.unpackbits with bitorder='little' gives [bit0, bit1, ..., bit7]
                    if bit_position == 7:
                        # Bit 7 is MSB - reverse bits in each byte
                        n_bytes = len(overlay_bytes)
                        reversed_bits = np.zeros_like(overlay_array)
                        for byte_idx in range(n_bytes):
                            start = byte_idx * 8
                            end = start + 8
                            byte_bits = overlay_array[start:end]
                            reversed_bits[start:end] = byte_bits[::-1]
                        overlay_array = reversed_bits
                    
                    # Reshape to 2D
                    if len(overlay_array) == rows * cols:
                        overlay_array = overlay_array.reshape((rows, cols))
                    return overlay_array.astype(np.uint8)
                else:
                    # Byte-packed overlay
                    dtype = np.uint16 if bits_allocated == 16 else np.uint8
                    overlay_array = np.frombuffer(overlay_data, dtype=dtype)
                    if len(overlay_array) == rows * cols:
                        overlay_array = overlay_array.reshape((rows, cols))
                    return overlay_array.astype(np.uint8)
        
        # Method 3: Check if this is a mask image (separate DICOM with pixel data)
        if hasattr(ds, 'pixel_array'):
            return ds.pixel_array
        
    except Exception as e:
        print(f"Error extracting overlay: {e}")
        import traceback
        traceback.print_exc()
    
    return None


def extract_overlay_with_origin(ds: Dataset, overlay_index: int = 0) -> Optional[Tuple[np.ndarray, int, int]]:
    """
    Extract overlay array and its origin from a DICOM dataset.

    Handles MSB/LSB bit ordering via OverlayBitPosition attribute.
    Reads OverlayOrigin (60xx,0050) for positioning.

    Args:
        ds: pydicom Dataset
        overlay_index: Index of overlay to extract (default 0)
        
    Returns:
        Tuple of (overlay_array, origin_x, origin_y) or None
    """
    if not HAS_PYDICOM:
        return None
    
    try:
        for group in range(0x6000, 0x60FF, 2):
            data_tag = (group, 0x3000)
            origin_tag = (group, 0x0050)
            
            if data_tag in ds:
                overlay_array = extract_overlay_array(ds, overlay_index)
                if overlay_array is None:
                    continue
                
                # Get origin - defaults to (0, 0) if not specified
                origin_x, origin_y = 0, 0
                if origin_tag in ds:
                    origin = ds[origin_tag].value
                    if isinstance(origin, (list, tuple)) and len(origin) >= 2:
                        origin_x = int(origin[0])
                        origin_y = int(origin[1])
                
                return (overlay_array, origin_x, origin_y)
        
        # For mask images, return with default origin
        if hasattr(ds, 'pixel_array'):
            return (ds.pixel_array, 0, 0)
        
    except Exception as e:
        print(f"Error extracting overlay with origin: {e}")
        import traceback
        traceback.print_exc()
    
    return None


def overlay_to_qimage(
    overlay_array: np.ndarray,
    base_width: int,
    base_height: int,
    color: Tuple[int, int, int] = (255, 0, 0),
    opacity: float = 0.7,
    origin_x: int = 0,
    origin_y: int = 0
) -> Optional[QImage]:
    """
    Convert overlay array to QImage with specified color and opacity.
    
    The overlay is rendered as semi-transparent colored pixels where the
    overlay data is non-zero. Aligned at (0,0) of base image or at specified origin.
    
    Args:
        overlay_array: 2D numpy array of overlay data
        base_width: Width of the base image
        base_height: Height of the base image
        color: RGB tuple for overlay color (default: red)
        opacity: Opacity of overlay (0.0-1.0, default: 0.7)
        origin_x: X offset for overlay positioning (default: 0)
        origin_y: Y offset for overlay positioning (default: 0)
        
    Returns:
        QImage with overlay in specified color and opacity
    """
    try:
        # Ensure overlay is 2D
        if overlay_array.ndim != 2:
            overlay_array = overlay_array.squeeze()
        
        if overlay_array.ndim != 2:
            print(f"Warning: overlay array is {overlay_array.ndim}D, expected 2D")
            return None
        
        # Get overlay dimensions
        overlay_height, overlay_width = overlay_array.shape
        
        # Create RGBA image at base dimensions
        rgba_array = np.zeros((base_height, base_width, 4), dtype=np.uint8)
        
        # Threshold: treat any non-zero value as part of overlay
        overlay_binary = overlay_array > 0
        
        # Position overlay at (origin_x, origin_y), clipping to base image bounds
        # Calculate the region to copy from overlay and to in base image
        start_x = origin_x
        start_y = origin_y
        
        # Clipping: ensure we don't go beyond base image bounds
        if start_x >= base_width or start_y >= base_height:
            # Overlay is completely outside the base image
            pass
        else:
            copy_width = min(overlay_width, base_width - start_x)
            copy_height = min(overlay_height, base_height - start_y)
            
            if copy_width > 0 and copy_height > 0:
                # Copy the overlapping region
                overlay_region = overlay_binary[:copy_height, :copy_width]
                rgba_array[start_y:start_y+copy_height, start_x:start_x+copy_width, 0][overlay_region] = color[0]
                rgba_array[start_y:start_y+copy_height, start_x:start_x+copy_width, 1][overlay_region] = color[1]
                rgba_array[start_y:start_y+copy_height, start_x:start_x+copy_width, 2][overlay_region] = color[2]
                rgba_array[start_y:start_y+copy_height, start_x:start_x+copy_width, 3][overlay_region] = int(opacity * 255)
        
        # Convert to QImage
        bytes_data = rgba_array.tobytes()
        qimage = QImage(bytes_data, base_width, base_height, QImage.Format_ARGB32)
        
        if qimage.isNull():
            print(f"Warning: Created null QImage for overlay")
            return None
        
        return qimage
        
    except Exception as e:
        print(f"Error converting overlay to QImage: {e}")
        import traceback
        traceback.print_exc()
        return None


def apply_overlay_to_base(base: QImage, overlay: QImage) -> QImage:
    """
    Apply overlay onto base image using alpha compositing.
    
    Uses QPainter for direct compositing.
    
    Args:
        base: Base QImage
        overlay: Overlay QImage (same size, Format_ARGB32)
        
    Returns:
        Composited QImage
    """
    if base.size() != overlay.size():
        # Scale overlay to match base
        overlay = overlay.scaled(base.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
    
    # Convert to QPixmap for painting
    base_pixmap = QPixmap.fromImage(base)
    result_pixmap = base_pixmap.copy()
    
    painter = QPainter(result_pixmap)
    painter.drawImage(0, 0, overlay)
    painter.end()
    
    return result_pixmap.toImage()


def apply_overlay_simple(base: QImage, overlay: QImage) -> QImage:
    """
    Simple alpha compositing of overlay onto base image.
    
    This converts to numpy arrays for direct manipulation.
    
    Args:
        base: Base QImage
        overlay: Overlay QImage with alpha channel
        
    Returns:
        Composited QImage
    """
    # Convert both to numpy arrays
    base_array = _qimage_to_numpy(base)
    overlay_array = _qimage_to_numpy(overlay)
    
    if base_array is None or overlay_array is None:
        return base
    
    # Ensure same shape
    if base_array.shape[:2] != overlay_array.shape[:2]:
        return base
    
    # Alpha compositing: result = base * (1 - alpha) + overlay * alpha
    # For grayscale base, convert to RGB first
    if len(base_array.shape) == 2 or base_array.shape[2] == 1:
        base_rgb = np.stack((base_array.squeeze(),) * 3, axis=-1)
    else:
        base_rgb = base_array
    
    # Ensure both are RGB with alpha
    if base_rgb.shape[2] == 3:
        base_rgba = np.dstack((base_rgb, np.full(base_rgb.shape[:2], 255, dtype=np.uint8)))
    else:
        base_rgba = base_rgb
    
    if overlay_array.shape[2] == 2:  # Grayscale + alpha
        overlay_rgba = np.zeros((*overlay_array.shape[:2], 4), dtype=np.uint8)
        overlay_rgba[..., 0] = overlay_array[..., 0]
        overlay_rgba[..., 1] = overlay_array[..., 0]
        overlay_rgba[..., 2] = overlay_array[..., 0]
        overlay_rgba[..., 3] = overlay_array[..., 1]
    elif overlay_array.shape[2] == 3:
        overlay_rgba = np.dstack((overlay_array, np.full(overlay_array.shape[:2], 255, dtype=np.uint8)))
    else:
        overlay_rgba = overlay_array
    
    # Normalize to float for compositing
    base_float = base_rgba.astype(np.float32) / 255.0
    overlay_float = overlay_rgba.astype(np.float32) / 255.0
    
    # Alpha compositing
    alpha = overlay_float[..., 3:4]
    result = base_float * (1 - alpha) + overlay_float * alpha
    result = (result * 255).astype(np.uint8)
    
    return _numpy_to_qimage_rgb(result, result.shape[1], result.shape[0])


def _qimage_to_numpy(qimage: QImage) -> Optional[np.ndarray]:
    """
    Convert QImage to numpy array.
    
    Args:
        qimage: Input QImage
        
    Returns:
        Numpy array (H, W, C) or (H, W) for grayscale
    """
    try:
        qimage = qimage.convertToFormat(QImage.Format_ARGB32)
        width = qimage.width()
        height = qimage.height()
        
        ptr = qimage.bits()
        ptr.setsize(qimage.byteCount())
        arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))
        return arr
    except Exception as e:
        print(f"Error converting QImage to numpy: {e}")
        return None


def get_original_size(ds: Dataset) -> QSize:
    """
    Get the original image dimensions from DICOM dataset.
    
    Args:
        ds: pydicom Dataset
        
    Returns:
        QSize with width and height
    """
    if not HAS_PYDICOM:
        return QSize()
    
    rows = int(ds.get('Rows', 0))
    cols = int(ds.get('Columns', 0))
    return QSize(cols, rows)


def analyze_region_across_series(
    dicom_files: List['DICOMFile'],
    region_def: dict,
) -> List[dict]:
    """
    Analyze a region (circle or rectangle) across all images in a series.
    
    For each image in the series, extracts pixel values within the specified
    region and calculates Raw and HU statistics.
    
    Args:
        dicom_files: List of DICOMFile objects from the series
        region_def: Region definition dictionary with keys:
            - x: X coordinate in pixels (0-indexed)
            - y: Y coordinate in pixels (0-indexed)
            - size: Size/diameter in pixels
            - is_circle: Boolean, True for circle, False for rectangle
            
    Returns:
        List of result dictionaries, one per image, each containing:
            - image_index: Index in the series (0-based)
            - z_coordinate: Z position from ImagePositionPatient (mm)
            - raw_mean, raw_std, raw_min, raw_max: Raw pixel statistics
            - hu_mean, hu_std, hu_min, hu_max: Hounsfield Unit statistics (0 if not available)
            - pixel_count: Number of pixels in the region (after clamping)
            - region_bounds: Tuple of (x, y, width, height) used for this image
            
    Note:
        - Uses pixel coordinates (same x,y applied to all images)
        - Region is clamped to each image's bounds
        - For circles: only pixels within the circle are included
        - For rectangles: all pixels in the rectangular region are included
        - HU conversion uses RescaleSlope and RescaleIntercept if available
    """
    results = []
    
    if not dicom_files:
        return results
    
    # Extract region parameters
    x = region_def.get('x', 0)
    y = region_def.get('y', 0)
    size = region_def.get('size', 7)
    is_circle = region_def.get('is_circle', True)
    
    # Ensure size is odd for proper centering
    if size % 2 == 0:
        size += 1
    
    half_size = size // 2
    
    for idx, dicom_file in enumerate(dicom_files):
        if not dicom_file.dataset or not dicom_file.is_image:
            continue
        
        ds = dicom_file.dataset
        
        try:
            # Get pixel array
            pixel_array = ds.pixel_array
            
            # Handle 3D arrays (multi-frame) - use first frame
            if pixel_array.ndim == 3:
                pixel_array = pixel_array[0]
            
            if pixel_array.ndim != 2:
                # Skip invalid arrays
                continue
            
            rows, cols = pixel_array.shape
            
            # Calculate region bounds centered at (x, y)
            win_x = x - half_size
            win_y = y - half_size
            win_w = size
            win_h = size
            
            # Clamp to image bounds
            win_x = max(0, min(win_x, cols - win_w)) if cols >= win_w else 0
            win_y = max(0, min(win_y, rows - win_h)) if rows >= win_h else 0
            win_w = min(win_w, cols - win_x)
            win_h = min(win_h, rows - win_y)
            
            # Extract region
            region = pixel_array[win_y:win_y + win_h, win_x:win_x + win_w]
            
            # Get HU conversion parameters
            slope = float(getattr(ds, 'RescaleSlope', 1))
            intercept = float(getattr(ds, 'RescaleIntercept', 0))
            has_hu = hasattr(ds, 'RescaleSlope') and hasattr(ds, 'RescaleIntercept') and (slope != 1 or intercept != 0)
            
            # Calculate statistics based on region shape
            # Calculate statistics using same logic as PixelArrayTable
            if is_circle and win_w > 0 and win_h > 0:
                # Circle mode: only use pixels within the circle
                center_x = win_w / 2.0
                center_y = win_h / 2.0
                diameter = min(win_w, win_h)
                radius = diameter / 2.0
                radius_sq = radius * radius
                
                # Create circular mask using pixel center coordinates
                yy, xx = np.ogrid[:win_h, :win_w]
                mask = (xx + 0.5 - center_x)**2 + (yy + 0.5 - center_y)**2 <= radius_sq
                
                # Extract pixels within circle
                circle_pixels = region[mask]
                pixel_count = len(circle_pixels)
                
                if pixel_count > 0:
                    raw_mean = float(np.mean(circle_pixels))
                    raw_std = float(np.std(circle_pixels))
                    raw_min = float(np.min(circle_pixels))
                    raw_max = float(np.max(circle_pixels))
                    
                    if has_hu:
                        hu_pixels = circle_pixels.astype(np.float64) * slope + intercept
                        hu_mean = float(np.mean(hu_pixels))
                        hu_std = float(np.std(hu_pixels))
                        hu_min = float(np.min(hu_pixels))
                        hu_max = float(np.max(hu_pixels))
                    else:
                        hu_mean = hu_std = hu_min = hu_max = 0.0
                else:
                    raw_mean = raw_std = raw_min = raw_max = 0.0
                    hu_mean = hu_std = hu_min = hu_max = 0.0
            else:
                # Rectangle mode: use all pixels in region
                pixel_count = region.size
                
                if pixel_count > 0:
                    raw_mean = float(np.mean(region))
                    raw_std = float(np.std(region))
                    raw_min = float(np.min(region))
                    raw_max = float(np.max(region))
                    
                    if has_hu:
                        hu_region = region.astype(np.float64) * slope + intercept
                        hu_mean = float(np.mean(hu_region))
                        hu_std = float(np.std(hu_region))
                        hu_min = float(np.min(hu_region))
                        hu_max = float(np.max(hu_region))
                    else:
                        hu_mean = hu_std = hu_min = hu_max = 0.0
                else:
                    raw_mean = raw_std = raw_min = raw_max = 0.0
                    hu_mean = hu_std = hu_min = hu_max = 0.0
            
            # Get Z coordinate from ImagePositionPatient
            z_coordinate = 0.0
            if 'ImagePositionPatient' in ds:
                try:
                    position = ds.ImagePositionPatient
                    if isinstance(position, (list, tuple)) and len(position) >= 3:
                        z_coordinate = float(position[2])
                except (ValueError, TypeError, AttributeError):
                    pass
            
            # Build result dictionary
            result = {
                'image_index': idx,
                'image_name': dicom_file.filepath.name if dicom_file.filepath else '',
                'z_coordinate': z_coordinate,
                'raw_mean': raw_mean,
                'raw_std': raw_std,
                'raw_min': raw_min,
                'raw_max': raw_max,
                'hu_mean': hu_mean,
                'hu_std': hu_std,
                'hu_min': hu_min,
                'hu_max': hu_max,
                'pixel_count': pixel_count,
                'region_bounds': (win_x, win_y, win_w, win_h),
                'has_hu': has_hu,
            }
            
            results.append(result)
            
        except Exception as e:
            # Skip this image but continue with others
            print(f"Warning: Could not analyze region for image {idx}: {e}")
            continue
    
    return results


def export_region_series_to_csv(
    results: List[dict],
    filepath: str,
) -> bool:
    """
    Export region analysis results to a CSV file.
    
    Args:
        results: List of result dictionaries from analyze_region_across_series()
        filepath: Path to output CSV file
        
    Returns:
        True if export was successful, False otherwise
    """
    import csv
    
    try:
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Write header
            header = [
                'Image Index',
                'Image Name',
                'Z Coordinate',
                'Raw Mean',
                'Raw Std',
                'Raw Min',
                'Raw Max',
                'HU Mean',
                'HU Std',
                'HU Min',
                'HU Max',
                'Pixel Count',
            ]
            writer.writerow(header)
            
            # Write data rows
            for r in results:
                row = [
                    r.get('image_index', ''),
                    r.get('image_name', ''),
                    r.get('z_coordinate', ''),
                    f"{r.get('raw_mean', 0):.2f}",
                    f"{r.get('raw_std', 0):.2f}",
                    f"{r.get('raw_min', 0):.2f}",
                    f"{r.get('raw_max', 0):.2f}",
                    f"{r.get('hu_mean', 0):.2f}",
                    f"{r.get('hu_std', 0):.2f}",
                    f"{r.get('hu_min', 0):.2f}",
                    f"{r.get('hu_max', 0):.2f}",
                    r.get('pixel_count', 0),
                ]
                writer.writerow(row)
        
        return True
        
    except Exception as e:
        print(f"Error exporting to CSV: {e}")
        return False
