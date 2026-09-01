"""Live Python scripting tab for DICOM image analysis with overlay rendering."""

import io
import contextlib
from typing import List, Optional, Tuple

import numpy as np
from PySide6.QtWidgets import (
    QWidget, QSplitter, QVBoxLayout, QHBoxLayout,
    QPlainTextEdit, QPushButton, QCheckBox, QLabel, QSpinBox,
)
from PySide6.QtGui import (
    QImage, QPainter, QSyntaxHighlighter, QTextCharFormat,
    QColor, QFont,
)
from PySide6.QtCore import Qt, QRegularExpression

try:
    from gui.utils.image_utils import dicom_to_qimage
    HAS_IMAGE_UTILS = True
except ImportError:
    HAS_IMAGE_UTILS = False

_STARTER_SCRIPT = """\
# Available variables:
#   image         — raw pixel array (H, W), dtype int16/uint16
#   slope, intercept — HU conversion: hu = image * slope + intercept
#   pixel_spacing — (row_mm, col_mm) or None
#   slice_index   — current slice index in series
#   ds            — pydicom.Dataset (full metadata)
#   series        — list of all DICOMFile objects
#   np            — numpy
#
# Set 'overlay' to a (H, W) mask, (H, W, 3) RGB or (H, W, 4) RGBA float array.

hu = image * slope + intercept

# Example: highlight pixels above 400 HU (bone)
overlay = (hu > 400).astype(np.float32)
"""


class ScriptImageLabel(QLabel):
    """QLabel that composites a base DICOM image with a semi-transparent overlay."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(200, 200)
        self._base: Optional[QImage] = None
        self._overlay: Optional[QImage] = None

    def set_image(self, qimage: Optional[QImage]):
        self._base = qimage
        self.update()

    def set_overlay(self, qimage: Optional[QImage]):
        self._overlay = qimage
        self.update()

    def paintEvent(self, event):
        from PySide6.QtCore import QRect
        if not self._base or self._base.isNull():
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Fill background
        painter.fillRect(self.rect(), self.palette().window())

        # Fit base image inside widget preserving aspect ratio
        w, h = self.width(), self.height()
        iw, ih = self._base.width(), self._base.height()
        if iw == 0 or ih == 0:
            painter.end()
            return
        scale = min(w / iw, h / ih)
        dw, dh = int(iw * scale), int(ih * scale)
        dx, dy = (w - dw) // 2, (h - dh) // 2

        dst = QRect(dx, dy, dw, dh)
        src = QRect(0, 0, iw, ih)
        painter.drawImage(dst, self._base, src)

        if self._overlay and not self._overlay.isNull():
            ow, oh = self._overlay.width(), self._overlay.height()
            painter.drawImage(dst, self._overlay, QRect(0, 0, ow, oh))

        painter.end()


class PythonHighlighter(QSyntaxHighlighter):
    """Minimal Python syntax highlighter — no external dependencies."""

    _KEYWORDS = (
        r'\b(False|None|True|and|as|assert|async|await|break|class|continue|'
        r'def|del|elif|else|except|finally|for|from|global|if|import|in|is|'
        r'lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)\b'
    )
    _BUILTINS = r'\b(np|image|overlay|ds|series|slice_index|pixel_spacing|slope|intercept|print|len|range|int|float|str|list|dict|tuple|set|bool|type|abs|min|max|sum|zip|enumerate|map|filter)\b'
    _STRING_SQ = r"'[^'\\]*(?:\\.[^'\\]*)*'"
    _STRING_DQ = r'"[^"\\]*(?:\\.[^"\\]*)*"'
    _COMMENT   = r'#[^\n]*'
    _NUMBER    = r'\b\d+\.?\d*([eE][+-]?\d+)?\b'

    def __init__(self, document):
        super().__init__(document)

        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor('#0000CC'))
        kw_fmt.setFontWeight(QFont.Weight.Bold)

        builtin_fmt = QTextCharFormat()
        builtin_fmt.setForeground(QColor('#7B00A0'))

        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor('#007700'))

        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor('#888888'))
        comment_fmt.setFontItalic(True)

        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor('#AA0000'))

        self._rules = [
            (QRegularExpression(self._KEYWORDS),  kw_fmt),
            (QRegularExpression(self._BUILTINS),  builtin_fmt),
            (QRegularExpression(self._STRING_DQ), str_fmt),
            (QRegularExpression(self._STRING_SQ), str_fmt),
            (QRegularExpression(self._NUMBER),    num_fmt),
            (QRegularExpression(self._COMMENT),   comment_fmt),
        ]

    def highlightBlock(self, text: str):
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


class ScriptView(QWidget):
    """Live scripting tab: left = Python editor, right = image + overlay."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._series: list = []
        self._current_index: int = 0
        self._dataset = None
        self._pixel_array: Optional[np.ndarray] = None
        self._rescale_slope: float = 1.0
        self._rescale_intercept: float = 0.0
        self._pixel_spacing: Optional[Tuple[float, float]] = None
        self._setup_ui()

    # ── UI construction ────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        root.addWidget(splitter)

        # ── left: editor panel ────────────────────────────────────────────────
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(4, 4, 4, 4)

        self._editor = QPlainTextEdit()
        self._editor.setPlainText(_STARTER_SCRIPT)
        self._editor.setFont(QFont('Monospace', 10))
        PythonHighlighter(self._editor.document())
        left_layout.addWidget(self._editor, 1)

        btn_row = QHBoxLayout()
        self._run_btn = QPushButton('▶ Run')
        self._run_btn.clicked.connect(self._run_script)
        self._auto_run_chk = QCheckBox('Auto-run on slice change')
        self._clear_btn = QPushButton('Clear overlay')
        self._clear_btn.clicked.connect(self._clear_overlay)
        btn_row.addWidget(self._run_btn)
        btn_row.addWidget(self._auto_run_chk)
        btn_row.addStretch()
        btn_row.addWidget(self._clear_btn)
        left_layout.addLayout(btn_row)

        self._console = QPlainTextEdit()
        self._console.setReadOnly(True)
        self._console.setFont(QFont('Monospace', 9))
        self._console.setFixedHeight(90)
        self._console.setPlaceholderText('Output / errors appear here')
        left_layout.addWidget(self._console)

        splitter.addWidget(left)

        # ── right: image panel ────────────────────────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 4, 4, 4)

        self._img_label = ScriptImageLabel()
        self._img_label.setText('Load a DICOM series to begin')
        right_layout.addWidget(self._img_label, 1)

        nav_row = QHBoxLayout()
        self._prev_btn = QPushButton('◀')
        self._prev_btn.setFixedWidth(32)
        self._prev_btn.clicked.connect(lambda: self._go_to_slice(self._current_index - 1))
        self._slice_spin = QSpinBox()
        self._slice_spin.setMinimum(0)
        self._slice_spin.setMaximum(0)
        self._slice_spin.valueChanged.connect(self._go_to_slice)
        self._slice_count_lbl = QLabel('/ 0')
        self._next_btn = QPushButton('▶')
        self._next_btn.setFixedWidth(32)
        self._next_btn.clicked.connect(lambda: self._go_to_slice(self._current_index + 1))
        nav_row.addWidget(self._prev_btn)
        nav_row.addWidget(self._slice_spin)
        nav_row.addWidget(self._slice_count_lbl)
        nav_row.addStretch()
        nav_row.addWidget(self._next_btn)
        right_layout.addLayout(nav_row)

        splitter.addWidget(right)
        splitter.setSizes([400, 600])

    # ── public API ─────────────────────────────────────────────────────────────

    def set_series(self, image_files: list):
        self._series = image_files or []
        n = len(self._series)
        self._slice_spin.blockSignals(True)
        self._slice_spin.setMaximum(max(n - 1, 0))
        self._slice_spin.blockSignals(False)
        self._slice_count_lbl.setText(f'/ {n}')
        self._current_index = 0

    def set_dataset(self, ds):
        self._dataset = ds
        if ds is None:
            self._pixel_array = None
            self._img_label.set_image(None)
            self._img_label.set_overlay(None)
            return

        self._rescale_slope = float(getattr(ds, 'RescaleSlope', 1.0))
        self._rescale_intercept = float(getattr(ds, 'RescaleIntercept', 0.0))
        ps = getattr(ds, 'PixelSpacing', None) or getattr(ds, 'ImagerPixelSpacing', None)
        self._pixel_spacing = (float(ps[0]), float(ps[1])) if ps and len(ps) >= 2 else None

        try:
            arr = ds.pixel_array
            self._pixel_array = arr[0] if arr.ndim == 3 else arr
        except Exception:
            self._pixel_array = None

        self._update_image_display(ds)

        if self._auto_run_chk.isChecked():
            self._run_script()

    def clear(self):
        self._series = []
        self._current_index = 0
        self._dataset = None
        self._pixel_array = None
        self._img_label.set_image(None)
        self._img_label.set_overlay(None)
        self._console.clear()
        self._slice_spin.blockSignals(True)
        self._slice_spin.setMaximum(0)
        self._slice_spin.setValue(0)
        self._slice_spin.blockSignals(False)
        self._slice_count_lbl.setText('/ 0')

    # ── internal ───────────────────────────────────────────────────────────────

    def _update_image_display(self, ds):
        if not HAS_IMAGE_UTILS:
            return
        try:
            qimg = dicom_to_qimage(ds)
            self._img_label.set_image(qimg)
            self._img_label.set_overlay(None)
        except Exception as e:
            self._console.setPlainText(f'Image display error: {e}')

    def _run_script(self):
        if self._pixel_array is None:
            self._console.setPlainText('No image loaded.')
            return

        namespace = {
            'np':            np,
            'image':         self._pixel_array,
            'ds':            self._dataset,
            'series':        self._series,
            'slice_index':   self._current_index,
            'pixel_spacing': self._pixel_spacing,
            'slope':         self._rescale_slope,
            'intercept':     self._rescale_intercept,
        }

        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                exec(self._editor.toPlainText(), namespace)  # noqa: S102
            overlay_raw = namespace.get('overlay', None)
            self._apply_overlay(overlay_raw)
            out = buf.getvalue()
            self._console.setPlainText(out if out else '✓ OK')
        except Exception as e:
            self._console.setPlainText(f'{type(e).__name__}: {e}')

    def _clear_overlay(self):
        self._img_label.set_overlay(None)

    def _apply_overlay(self, arr):
        if arr is None:
            self._img_label.set_overlay(None)
            return

        if isinstance(arr, QImage):
            self._img_label.set_overlay(arr)
            return

        if not isinstance(arr, np.ndarray):
            self._console.setPlainText(f'overlay must be a numpy array or QImage, got {type(arr).__name__}')
            return

        arr = arr.astype(np.float32)

        if arr.ndim == 2:
            # Mask or scalar field — normalise to 0-1 if not already binary
            mn, mx = arr.min(), arr.max()
            if mx > mn:
                arr = (arr - mn) / (mx - mn)
            h, w = arr.shape
            rgba = np.zeros((h, w, 4), dtype=np.float32)
            rgba[:, :, 0] = 1.0   # red channel
            rgba[:, :, 3] = arr * 0.6
        elif arr.ndim == 3 and arr.shape[2] == 3:
            h, w = arr.shape[:2]
            rgba = np.zeros((h, w, 4), dtype=np.float32)
            rgba[:, :, :3] = np.clip(arr, 0, 1)
            rgba[:, :, 3] = 0.5
        elif arr.ndim == 3 and arr.shape[2] == 4:
            rgba = np.clip(arr, 0, 1)
        else:
            self._console.setPlainText(f'Unsupported overlay shape: {arr.shape}')
            return

        rgba8 = (rgba * 255).astype(np.uint8)
        h, w = rgba8.shape[:2]
        qimg = QImage(rgba8.tobytes(), w, h, w * 4, QImage.Format.Format_RGBA8888).copy()
        self._img_label.set_overlay(qimg)

    def _go_to_slice(self, index: int):
        if not self._series:
            return
        index = max(0, min(index, len(self._series) - 1))
        if index == self._current_index and self._dataset is not None:
            return
        self._current_index = index
        self._slice_spin.blockSignals(True)
        self._slice_spin.setValue(index)
        self._slice_spin.blockSignals(False)

        dicom_file = self._series[index]
        ds = dicom_file.dataset
        if ds is None:
            try:
                import pydicom
                ds = pydicom.dcmread(str(dicom_file.filepath))
            except Exception as e:
                self._console.setPlainText(f'Failed to load slice {index}: {e}')
                return
        self.set_dataset(ds)
