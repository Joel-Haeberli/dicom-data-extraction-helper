#!/usr/bin/env python3
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import numpy as np
from PySide6.QtCore import Qt, QDateTime, Signal
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from gui.utils.dicom_loader import DICOMFile


# ── module-level helper ────────────────────────────────────────────────────────

def _euler_to_rotation_matrix(rx_deg: float, ry_deg: float, rz_deg: float) -> np.ndarray:
    """ZYX Euler angles (degrees) → 3×3 rotation matrix (row-vector convention)."""
    rx, ry, rz = np.radians([rx_deg, ry_deg, rz_deg])
    Rx = np.array([[1, 0,           0          ],
                   [0, np.cos(rx), -np.sin(rx) ],
                   [0, np.sin(rx),  np.cos(rx) ]])
    Ry = np.array([[ np.cos(ry), 0, np.sin(ry)],
                   [0,           1, 0          ],
                   [-np.sin(ry), 0, np.cos(ry)]])
    Rz = np.array([[np.cos(rz), -np.sin(rz), 0],
                   [np.sin(rz),  np.cos(rz), 0],
                   [0,           0,          1]])
    return Rz @ Ry @ Rx


def _make_transform(rotation: np.ndarray, translation: Tuple[float, float, float]):
    """Build a vispy MatrixTransform from a 3×3 rotation and a translation."""
    from vispy.visuals.transforms import MatrixTransform
    M = np.eye(4, dtype=np.float64)
    M[:3, :3] = rotation
    M[3, :3] = list(translation)
    t = MatrixTransform()
    t.matrix = M
    return t


# ── SliceDisplayWidget ─────────────────────────────────────────────────────────

class SliceDisplayWidget(QWidget):
    """Left panel: scaled DICOM slice with hover and click signals."""

    hover_moved  = Signal(int, int)
    hover_left   = Signal()
    wheel_scroll = Signal(int)    # +1 or -1
    clicked      = Signal(int, int)   # pixel_x, pixel_y on left-click

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: Optional[QPixmap] = None
        self._iw = self._ih = 1
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(100, 100)
        self.setStyleSheet("background: #1a1a2e;")

    def set_image(self, qimage: Optional[QImage]):
        if qimage is None:
            self._pixmap = None
            self._iw = self._ih = 1
        else:
            self._pixmap = QPixmap.fromImage(qimage)
            self._iw = qimage.width()
            self._ih = qimage.height()
        self.update()

    def _image_rect(self) -> Tuple[int, int, int, int]:
        if self._pixmap is None:
            return 0, 0, self.width(), self.height()
        ww, wh = self.width(), self.height()
        scale = min(ww / self._iw, wh / self._ih)
        dw = int(self._iw * scale)
        dh = int(self._ih * scale)
        return (ww - dw) // 2, (wh - dh) // 2, dw, dh

    def _to_image_coords(self, wx: float, wy: float) -> Optional[Tuple[int, int]]:
        x0, y0, dw, dh = self._image_rect()
        if dw == 0 or dh == 0:
            return None
        ix = int((wx - x0) / dw * self._iw)
        iy = int((wy - y0) / dh * self._ih)
        if 0 <= ix < self._iw and 0 <= iy < self._ih:
            return ix, iy
        return None

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            coords = self._to_image_coords(e.position().x(), e.position().y())
            if coords:
                self.clicked.emit(*coords)
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        coords = self._to_image_coords(e.position().x(), e.position().y())
        if coords:
            self.hover_moved.emit(*coords)
        else:
            self.hover_left.emit()
        super().mouseMoveEvent(e)

    def wheelEvent(self, e):
        delta = 1 if e.angleDelta().y() < 0 else -1
        self.wheel_scroll.emit(delta)
        e.accept()

    def leaveEvent(self, e):
        self.hover_left.emit()
        super().leaveEvent(e)

    def paintEvent(self, _e):
        from PySide6.QtGui import QPainter
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(26, 26, 46))
        if self._pixmap:
            x0, y0, dw, dh = self._image_rect()
            p.drawPixmap(x0, y0, dw, dh, self._pixmap)


# ── VolumeView ─────────────────────────────────────────────────────────────────

class VolumeView(QWidget):
    """
    3D View tab: 2D slice (left) + MIP volume (right).
    Moving the mouse over the slice shows the configured measurement shape as a
    live preview in the 3D view.  Left-clicking places a persistent measurement.
    """

    slice_changed = Signal(int)   # 0-based, syncs main-window navigation

    _SHAPE_SPHERE   = 0
    _SHAPE_BOX      = 1
    _SHAPE_CYLINDER = 2
    _SHAPE_NAMES    = ["sphere", "box", "cylinder"]

    _TABLE_COLS = ["#", "Shape", "X", "Y", "Z",
                   "Params", "Orient",
                   "Avg (raw)", "Std (raw)", "Avg (HU)", "Std (HU)"]

    def __init__(self, parent=None):
        super().__init__(parent)

        # ── volume data ────────────────────────────────────────────────────────
        self._volume_array: Optional[np.ndarray] = None   # (n, H, W) float32
        self._vol_min: float = 0.0
        self._vol_max: float = 1.0
        self._current_slice_index: int = 0
        self._n_slices: int = 0
        self._img_height: int = 0
        self._img_width: int = 0
        self._rescale_slope: float = 1.0
        self._rescale_intercept: float = 0.0

        # ── vispy ──────────────────────────────────────────────────────────────
        self._vispy_available: bool = False
        self._scene_module = None
        self._canvas = None
        self._view = None
        self._volume_visual = None

        # hover preview — rebuilt when shape/params change, moved on every mouse event
        self._hover_visual = None
        self._hover_pos: Optional[Tuple[float, float, float]] = None
        self._last_hover_px: Optional[Tuple[int, int]] = None

        self._hover_color: Tuple[float, float, float, float] = (1.0, 1.0, 0.0, 0.45)

        # ── measurements ──────────────────────────────────────────────────────
        self._measurements: List[Dict[str, Any]] = []
        self._next_mid: int = 1
        self._selected_mid: Optional[int] = None
        self._measurement_visuals: Dict[int, Any] = {}
        self._meas_color: Tuple[float, float, float, float] = (1.0, 0.5, 0.0, 0.6)
        self._updating_controls: bool = False

        # ── orientation flips ──────────────────────────────────────────────────
        self._orient_flip_x: bool = False   # flip left-right
        self._orient_flip_y: bool = False   # flip superior-inferior
        self._orient_flip_z: bool = False   # flip anterior-posterior

        self._setup_ui()
        self._try_init_vispy()

    # ══════════════════════════════════════════════════════════════ UI setup ══

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # ── Row A: hover colour + orientation flips + export ─────────────────
        row_a = QHBoxLayout()
        row_a.addWidget(QLabel("Preview colour:"))
        self._hover_color_btn = QPushButton()
        self._hover_color_btn.setFixedSize(24, 24)
        self._hover_color_btn.setToolTip("Colour of the hover preview shape")
        self._update_hover_color_button()
        self._hover_color_btn.clicked.connect(self._on_hover_color_clicked)
        row_a.addWidget(self._hover_color_btn)
        row_a.addSpacing(12)
        row_a.addWidget(QLabel("Flip:"))
        self._flip_x_btn = QPushButton("L/R")
        self._flip_x_btn.setCheckable(True)
        self._flip_x_btn.setFixedWidth(38)
        self._flip_x_btn.setToolTip("Flip left/right")
        self._flip_x_btn.toggled.connect(self._on_orient_flip_changed)
        row_a.addWidget(self._flip_x_btn)
        self._flip_y_btn = QPushButton("A/P")
        self._flip_y_btn.setCheckable(True)
        self._flip_y_btn.setFixedWidth(38)
        self._flip_y_btn.setToolTip("Flip anterior/posterior (rows)")
        self._flip_y_btn.toggled.connect(self._on_orient_flip_changed)
        row_a.addWidget(self._flip_y_btn)
        self._flip_z_btn = QPushButton("S/I")
        self._flip_z_btn.setCheckable(True)
        self._flip_z_btn.setFixedWidth(38)
        self._flip_z_btn.setToolTip("Flip superior/inferior (slices)")
        self._flip_z_btn.toggled.connect(self._on_orient_flip_changed)
        row_a.addWidget(self._flip_z_btn)
        row_a.addStretch()
        export_3d_btn = QPushButton("Export 3D…")
        export_3d_btn.setToolTip("Save the 3D view as a PNG image")
        export_3d_btn.clicked.connect(self._on_export_3d)
        row_a.addWidget(export_3d_btn)
        root.addLayout(row_a)

        # ── Row B: measurement shape + params ─────────────────────────────────
        row_b = QHBoxLayout()
        row_b.addWidget(QLabel("Shape:"))
        self._shape_combo = QComboBox()
        self._shape_combo.addItems(["Sphere", "Box", "Cylinder"])
        self._shape_combo.currentIndexChanged.connect(self._on_shape_combo_changed)
        row_b.addWidget(self._shape_combo)

        self._shape_params_stack = QStackedWidget()

        # Page 0: Sphere
        page_sphere = QWidget()
        ps_lay = QHBoxLayout(page_sphere)
        ps_lay.setContentsMargins(0, 0, 0, 0)
        ps_lay.addWidget(QLabel("Radius:"))
        self._sp_radius = QSpinBox()
        self._sp_radius.setRange(1, 200); self._sp_radius.setValue(5); self._sp_radius.setFixedWidth(60)
        self._sp_radius.valueChanged.connect(self._on_shape_param_changed)
        ps_lay.addWidget(self._sp_radius)
        self._shape_params_stack.addWidget(page_sphere)

        # Page 1: Box
        page_box = QWidget()
        pb_lay = QHBoxLayout(page_box)
        pb_lay.setContentsMargins(0, 0, 0, 0)
        for lbl, attr in [("W:", "_sp_bw"), ("H:", "_sp_bh"), ("D:", "_sp_bd")]:
            pb_lay.addWidget(QLabel(lbl))
            sp = QSpinBox(); sp.setRange(1, 500); sp.setValue(10); sp.setFixedWidth(55)
            sp.valueChanged.connect(self._on_shape_param_changed)
            setattr(self, attr, sp); pb_lay.addWidget(sp)
        pb_lay.addWidget(QLabel("  Rx°:"))
        self._sp_rx = QDoubleSpinBox(); self._sp_rx.setRange(-180, 180); self._sp_rx.setFixedWidth(65)
        self._sp_rx.valueChanged.connect(self._on_shape_param_changed); pb_lay.addWidget(self._sp_rx)
        pb_lay.addWidget(QLabel("Ry°:"))
        self._sp_ry = QDoubleSpinBox(); self._sp_ry.setRange(-180, 180); self._sp_ry.setFixedWidth(65)
        self._sp_ry.valueChanged.connect(self._on_shape_param_changed); pb_lay.addWidget(self._sp_ry)
        pb_lay.addWidget(QLabel("Rz°:"))
        self._sp_rz = QDoubleSpinBox(); self._sp_rz.setRange(-180, 180); self._sp_rz.setFixedWidth(65)
        self._sp_rz.valueChanged.connect(self._on_shape_param_changed); pb_lay.addWidget(self._sp_rz)
        self._shape_params_stack.addWidget(page_box)

        # Page 2: Cylinder
        page_cyl = QWidget()
        pc_lay = QHBoxLayout(page_cyl)
        pc_lay.setContentsMargins(0, 0, 0, 0)
        pc_lay.addWidget(QLabel("Radius:"))
        self._sp_cr = QSpinBox(); self._sp_cr.setRange(1, 200); self._sp_cr.setValue(5); self._sp_cr.setFixedWidth(60)
        self._sp_cr.valueChanged.connect(self._on_shape_param_changed); pc_lay.addWidget(self._sp_cr)
        pc_lay.addWidget(QLabel("Height:"))
        self._sp_ch = QSpinBox(); self._sp_ch.setRange(1, 500); self._sp_ch.setValue(10); self._sp_ch.setFixedWidth(60)
        self._sp_ch.valueChanged.connect(self._on_shape_param_changed); pc_lay.addWidget(self._sp_ch)
        pc_lay.addWidget(QLabel("  Rx°:"))
        self._sp_crx = QDoubleSpinBox(); self._sp_crx.setRange(-180, 180); self._sp_crx.setFixedWidth(65)
        self._sp_crx.valueChanged.connect(self._on_shape_param_changed); pc_lay.addWidget(self._sp_crx)
        pc_lay.addWidget(QLabel("Ry°:"))
        self._sp_cry = QDoubleSpinBox(); self._sp_cry.setRange(-180, 180); self._sp_cry.setFixedWidth(65)
        self._sp_cry.valueChanged.connect(self._on_shape_param_changed); pc_lay.addWidget(self._sp_cry)
        self._shape_params_stack.addWidget(page_cyl)

        row_b.addWidget(self._shape_params_stack)

        self._meas_color_btn = QPushButton()
        self._meas_color_btn.setFixedSize(24, 24)
        self._meas_color_btn.setToolTip("Measurement colour")
        self._update_meas_color_button()
        self._meas_color_btn.clicked.connect(self._on_meas_color_clicked)
        row_b.addWidget(self._meas_color_btn)
        row_b.addStretch()

        self._export_meas_btn = QPushButton("Export JSON…")
        self._export_meas_btn.clicked.connect(self._on_export_measurements)
        row_b.addWidget(self._export_meas_btn)
        self._import_meas_btn = QPushButton("Import JSON…")
        self._import_meas_btn.clicked.connect(self._on_import_measurements)
        row_b.addWidget(self._import_meas_btn)
        root.addLayout(row_b)

        # ── Row C: position fine-tune (hidden until a measurement is selected) ─
        self._pos_edit_frame = QFrame()
        self._pos_edit_frame.setFrameShape(QFrame.StyledPanel)
        self._pos_edit_frame.hide()
        pos_lay = QHBoxLayout(self._pos_edit_frame)
        pos_lay.setContentsMargins(4, 2, 4, 2)
        pos_lay.addWidget(QLabel("Edit —  X:"))
        self._pos_x_spin = QSpinBox(); self._pos_x_spin.setRange(0, 9999); self._pos_x_spin.setFixedWidth(65)
        self._pos_x_spin.valueChanged.connect(self._on_pos_spin_changed); pos_lay.addWidget(self._pos_x_spin)
        pos_lay.addWidget(QLabel("Y:"))
        self._pos_y_spin = QSpinBox(); self._pos_y_spin.setRange(0, 9999); self._pos_y_spin.setFixedWidth(65)
        self._pos_y_spin.valueChanged.connect(self._on_pos_spin_changed); pos_lay.addWidget(self._pos_y_spin)
        pos_lay.addWidget(QLabel("Z (slice):"))
        self._pos_z_spin = QSpinBox(); self._pos_z_spin.setRange(0, 9999); self._pos_z_spin.setFixedWidth(65)
        self._pos_z_spin.valueChanged.connect(self._on_pos_spin_changed); pos_lay.addWidget(self._pos_z_spin)
        pos_lay.addStretch()
        self._delete_btn = QPushButton("Delete")
        self._delete_btn.clicked.connect(self._on_delete_btn_clicked)
        pos_lay.addWidget(self._delete_btn)
        root.addWidget(self._pos_edit_frame)

        # ── Splitter ──────────────────────────────────────────────────────────
        self._splitter = QSplitter(Qt.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)

        self._slice_widget = SliceDisplayWidget()
        self._slice_widget.hover_moved.connect(self._on_hover_moved)
        self._slice_widget.hover_left.connect(self._on_hover_left)
        self._slice_widget.wheel_scroll.connect(self._on_wheel_scroll)
        self._slice_widget.clicked.connect(self._on_slice_clicked)
        left_layout.addWidget(self._slice_widget, 1)

        nav = QHBoxLayout()
        nav.addWidget(QLabel("Slice:"))
        self._slice_spin = QSpinBox()
        self._slice_spin.setRange(1, 1); self._slice_spin.setValue(1); self._slice_spin.setEnabled(False)
        self._slice_spin.valueChanged.connect(self._on_slice_spin_changed)
        nav.addWidget(self._slice_spin)
        self._slice_total_label = QLabel("/ –")
        nav.addWidget(self._slice_total_label)
        nav.addStretch()
        left_layout.addLayout(nav)
        self._splitter.addWidget(left_widget)

        self._vispy_container = QWidget()
        self._vispy_container.setStyleSheet("background: black;")
        vc_layout = QVBoxLayout(self._vispy_container)
        vc_layout.setContentsMargins(0, 0, 0, 0)
        self._vispy_placeholder = QLabel("3D view — install vispy to enable")
        self._vispy_placeholder.setAlignment(Qt.AlignCenter)
        self._vispy_placeholder.setStyleSheet("color: #888; font-size: 13px;")
        vc_layout.addWidget(self._vispy_placeholder)
        self._splitter.addWidget(self._vispy_container)

        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 2)
        root.addWidget(self._splitter, 1)

        # ── Measurements table ────────────────────────────────────────────────
        self._meas_table = QTableWidget(0, len(self._TABLE_COLS))
        self._meas_table.setHorizontalHeaderLabels(self._TABLE_COLS)
        self._meas_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._meas_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._meas_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._meas_table.setFixedHeight(150)
        self._meas_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._meas_table.horizontalHeader().setStretchLastSection(True)
        self._meas_table.itemSelectionChanged.connect(self._on_table_selection_changed)
        root.addWidget(self._meas_table)

    def _try_init_vispy(self):
        try:
            import vispy
            vispy.use('pyside6')
            from vispy import scene as _scene
            self._scene_module = _scene
            self._vispy_available = True
            self._vispy_placeholder.setText("Load a DICOM series to render the 3D volume.")
        except Exception as e:
            self._vispy_available = False
            self._vispy_placeholder.setText(f"3D view unavailable:\n{type(e).__name__}: {e}")

    # ══════════════════════════════════════════════════════════ public API ════

    def set_series(self, image_files: List['DICOMFile']):
        if not image_files:
            self.clear()
            return

        try:
            ds = image_files[0].dataset
            self._rescale_slope     = float(getattr(ds, 'RescaleSlope',     1.0))
            self._rescale_intercept = float(getattr(ds, 'RescaleIntercept', 0.0))
        except Exception:
            self._rescale_slope, self._rescale_intercept = 1.0, 0.0

        arrays = []
        for f in image_files:
            if f.dataset is None:
                continue
            try:
                arr = f.dataset.pixel_array
                if arr.ndim == 3:
                    arr = arr[0]
                arrays.append(arr.astype(np.float32))
            except Exception:
                continue

        if not arrays:
            self.clear()
            return

        volume = np.stack(arrays, axis=0)
        self._volume_array = volume
        self._n_slices, self._img_height, self._img_width = volume.shape
        self._vol_min = float(volume.min())
        self._vol_max = float(volume.max()) if volume.max() != volume.min() else self._vol_min + 1.0
        self._current_slice_index = 0
        self._hover_pos = None
        self._last_hover_px = None

        self._pos_x_spin.setRange(0, self._img_width  - 1)
        self._pos_y_spin.setRange(0, self._img_height - 1)
        self._pos_z_spin.setRange(0, self._n_slices   - 1)

        self._update_slice_display(0)
        self._update_nav_label()

        if self._vispy_available:
            self._build_vispy_scene(volume)

    def set_current_slice(self, index: int):
        self._current_slice_index = index
        if self._volume_array is None:
            return
        self._update_slice_display(index)
        self._update_nav_label()
        if self._hover_visual is not None:
            self._hover_visual.visible = False
        if self._canvas is not None:
            self._canvas.update()

    def clear(self):
        self._volume_array = None
        self._slice_widget.set_image(None)
        self._update_nav_label()
        self._hover_pos = None
        for vis in self._measurement_visuals.values():
            try:
                vis.parent = None
            except Exception:
                pass
        self._measurement_visuals.clear()
        self._measurements.clear()
        self._next_mid = 1
        self._selected_mid = None
        self._pos_edit_frame.hide()
        self._meas_table.setRowCount(0)
        self._clear_vispy_scene()

    # ══════════════════════════════════════════════════ orientation helpers ════

    def _prepare_vol_display(self, vol_norm: np.ndarray) -> np.ndarray:
        """Apply user flip buttons to vol_norm before passing to vispy.

        Original axis mapping (no transpose):
          axis-2 (cols)   → vispy X  (left-right)
          axis-1 (rows)   → vispy Y  (anterior-posterior / up-down)
          axis-0 (slices) → vispy Z  (superior-inferior / depth)
        """
        vol = vol_norm
        if self._orient_flip_x:
            vol = np.flip(vol, axis=2)
        if self._orient_flip_y:
            vol = np.flip(vol, axis=1)
        if self._orient_flip_z:
            vol = np.flip(vol, axis=0)
        return np.ascontiguousarray(vol)

    def _voxel_to_world(self, cx: float, cy: float, cz: float):
        """Map original voxel coords (col, row, slice) to vispy world coords."""
        n, h, w = self._n_slices, self._img_height, self._img_width
        ix = cx
        iy = cy
        iz = cz
        if self._orient_flip_x:
            ix = (w - 1) - ix
        if self._orient_flip_y:
            iy = (h - 1) - iy
        if self._orient_flip_z:
            iz = (n - 1) - iz
        return (ix - w / 2, iy - h / 2, iz - n / 2)

    # ══════════════════════════════════════════════════════ vispy scene ═══════

    def _build_vispy_scene(self, volume: np.ndarray):
        self._clear_vispy_scene()
        scene = self._scene_module
        n, h, w = volume.shape
        vol_norm = ((volume - self._vol_min) / (self._vol_max - self._vol_min)).astype(np.float32)

        self._canvas = scene.SceneCanvas(keys='interactive', show=False, bgcolor='black')
        self._vispy_container.layout().addWidget(self._canvas.native)
        self._vispy_placeholder.hide()

        self._view = self._canvas.central_widget.add_view()
        cam = scene.cameras.TurntableCamera(fov=45, elevation=30, azimuth=45)
        self._view.camera = cam

        vol_display = self._prepare_vol_display(vol_norm)
        self._volume_visual = scene.visuals.Volume(
            vol_display, parent=self._view.scene, method='mip', clim=(0.0, 1.0))
        self._volume_visual.transform = scene.transforms.STTransform(
            translate=(-w / 2, -h / 2, -n / 2))

        cam.distance = float(np.sqrt(w**2 + h**2 + n**2)) * 0.85

        for meas in self._measurements:
            self._rebuild_measurement_visual(meas)

        self._canvas.update()

    def _clear_vispy_scene(self):
        if self._canvas is not None:
            native = self._canvas.native
            self._vispy_container.layout().removeWidget(native)
            native.setParent(None)
            try:
                self._canvas.close()
            except Exception:
                pass
            self._canvas = None
            self._view = None
            self._volume_visual = None
            self._hover_visual = None
            self._measurement_visuals.clear()
            self._vispy_placeholder.show()

    # ── hover preview ─────────────────────────────────────────────────────────

    def _current_hover_rotation(self) -> np.ndarray:
        """Return the 3×3 rotation matrix for the currently configured shape."""
        idx = self._shape_combo.currentIndex()
        if idx == self._SHAPE_BOX:
            return _euler_to_rotation_matrix(
                self._sp_rx.value(), self._sp_ry.value(), self._sp_rz.value())
        if idx == self._SHAPE_CYLINDER:
            return _euler_to_rotation_matrix(
                self._sp_crx.value(), self._sp_cry.value(), 0.0)
        return np.eye(3)

    def _rebuild_hover_visual(self, pos: Optional[Tuple[float, float, float]] = None):
        """
        Recreate the hover preview visual using the currently configured shape/params.
        Only needed when shape geometry changes (shape type, dimensions) — position
        changes are handled cheaply by _move_hover_visual().
        """
        if not self._vispy_available or self._view is None:
            return

        use_pos = pos if pos is not None else self._hover_pos
        if self._hover_visual is not None:
            self._hover_visual.parent = None
            self._hover_visual = None

        if use_pos is None:
            return

        scene = self._scene_module
        r, g, b, a = self._hover_color
        color = (r, g, b, a)
        idx = self._shape_combo.currentIndex()

        try:
            if idx == self._SHAPE_SPHERE:
                vis = scene.visuals.Sphere(
                    radius=float(self._sp_radius.value()),
                    method='ico', subdivisions=3,
                    color=color, parent=self._view.scene)
            elif idx == self._SHAPE_BOX:
                vis = scene.visuals.Box(
                    width=float(self._sp_bw.value()),
                    height=float(self._sp_bh.value()),
                    depth=float(self._sp_bd.value()),
                    color=color, parent=self._view.scene)
            else:
                vis = self._make_cylinder_tube(
                    float(self._sp_cr.value()),
                    float(self._sp_ch.value()),
                    color, self._view.scene)
        except (AttributeError, Exception):
            if idx == self._SHAPE_BOX:
                vis = self._make_box_wireframe_at(
                    self._sp_bw.value(), self._sp_bh.value(), self._sp_bd.value(), color)
            else:
                vis = scene.visuals.Sphere(
                    radius=float(self._sp_cr.value()),
                    method='ico', subdivisions=3,
                    color=color, parent=self._view.scene)

        if vis is None:
            return

        vis.transform = _make_transform(self._current_hover_rotation(), use_pos)
        self._hover_visual = vis
        self._hover_pos = use_pos
        if self._canvas is not None:
            self._canvas.update()

    def _move_hover_visual(self, pos: Tuple[float, float, float]):
        """Update only the translation of the existing hover visual — no mesh rebuild."""
        self._hover_visual.transform = _make_transform(
            self._current_hover_rotation(), pos)
        self._hover_visual.visible = True
        self._hover_pos = pos
        if self._canvas is not None:
            self._canvas.update()

    # ── measurement visuals ───────────────────────────────────────────────────

    def _rebuild_measurement_visual(self, meas: dict):
        mid = meas["id"]
        old = self._measurement_visuals.pop(mid, None)
        if old is not None:
            try:
                old.parent = None
            except Exception:
                pass

        if self._view is None:
            return

        scene = self._scene_module
        c = meas["color"]
        color = (float(c[0]), float(c[1]), float(c[2]), float(c[3]))
        shape = meas["shape"]
        vis = None

        try:
            if shape == "sphere":
                vis = scene.visuals.Sphere(
                    radius=float(meas["radius"]),
                    method='ico', subdivisions=3,
                    color=color, parent=self._view.scene)
            elif shape == "box":
                vis = scene.visuals.Box(
                    width=float(meas["box_w"]),
                    height=float(meas["box_h"]),
                    depth=float(meas["box_d"]),
                    color=color, parent=self._view.scene)
            else:
                vis = self._make_cylinder_tube(
                    float(meas["cyl_radius"]),
                    float(meas["cyl_height"]),
                    color, self._view.scene)
        except (AttributeError, Exception):
            if shape == "box":
                vis = self._make_box_wireframe_at(
                    meas["box_w"], meas["box_h"], meas["box_d"], color)
            else:
                vis = self._make_cylinder_tube(
                    float(meas.get("cyl_radius", 5)),
                    float(meas.get("cyl_height", 10)),
                    color, self._view.scene)

        if vis is None:
            return

        R = _euler_to_rotation_matrix(
            meas.get("rot_x", 0), meas.get("rot_y", 0), meas.get("rot_z", 0))
        tx, ty, tz = self._voxel_to_world(meas["cx"], meas["cy"], meas["cz"])
        vis.transform = _make_transform(R, (tx, ty, tz))
        self._measurement_visuals[mid] = vis
        if self._canvas is not None:
            self._canvas.update()

    def _make_cylinder_tube(self, radius: float, height: float, color, parent) -> Any:
        """Create a cylinder using Tube (two-point path along local Z, centered at origin)."""
        scene = self._scene_module
        half = height / 2.0
        points = np.array([[0.0, 0.0, -half], [0.0, 0.0, half]], dtype=np.float32)
        return scene.visuals.Tube(
            points, radius=radius, tube_points=24,
            color=color, parent=parent)

    def _make_box_wireframe_at(self, bw, bh, bd, color) -> Any:
        scene = self._scene_module
        hw, hh, hd = bw / 2, bh / 2, bd / 2
        corners = np.array([
            [-hw, -hh, -hd], [ hw, -hh, -hd], [ hw,  hh, -hd], [-hw,  hh, -hd],
            [-hw, -hh,  hd], [ hw, -hh,  hd], [ hw,  hh,  hd], [-hw,  hh,  hd],
        ], dtype=np.float32)
        edges = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]
        verts = np.vstack([[corners[a], corners[b]] for a, b in edges])
        return scene.visuals.Line(
            verts, color=color, connect='segments', parent=self._view.scene)

    # ══════════════════════════════════════════════════════ voxel sampling ════

    def _sample_voxels(self, meas: dict) -> np.ndarray:
        vol = self._volume_array
        if vol is None:
            return np.array([], dtype=np.float32)
        N, H, W = vol.shape
        cx, cy, cz = int(meas["cx"]), int(meas["cy"]), int(meas["cz"])
        shape = meas["shape"]
        R = _euler_to_rotation_matrix(
            meas.get("rot_x", 0), meas.get("rot_y", 0), meas.get("rot_z", 0))
        R_inv = R.T

        if shape == "sphere":
            pad = int(meas["radius"]) + 1
        elif shape == "box":
            pad = int(max(meas["box_w"], meas["box_h"], meas["box_d"]) / 2) + 2
        else:
            pad = int(max(meas["cyl_radius"], meas["cyl_height"] / 2)) + 2

        x0, x1 = max(0, cx - pad), min(W, cx + pad + 1)
        y0, y1 = max(0, cy - pad), min(H, cy + pad + 1)
        z0, z1 = max(0, cz - pad), min(N, cz + pad + 1)
        if x0 >= x1 or y0 >= y1 or z0 >= z1:
            return np.array([], dtype=np.float32)

        xs = np.arange(x0, x1) - cx
        ys = np.arange(y0, y1) - cy
        zs = np.arange(z0, z1) - cz
        X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
        coords = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1).astype(np.float64)
        local = coords @ R_inv

        if shape == "sphere":
            mask = np.sum(local ** 2, axis=1) <= meas["radius"] ** 2
        elif shape == "box":
            hw, hh, hd = meas["box_w"] / 2, meas["box_h"] / 2, meas["box_d"] / 2
            mask = ((np.abs(local[:, 0]) <= hw) &
                    (np.abs(local[:, 1]) <= hh) &
                    (np.abs(local[:, 2]) <= hd))
        else:
            cr, ch = meas["cyl_radius"], meas["cyl_height"] / 2
            mask = ((local[:, 0]**2 + local[:, 1]**2 <= cr**2) &
                    (np.abs(local[:, 2]) <= ch))

        if not np.any(mask):
            return np.array([], dtype=np.float32)

        abs_xs = (coords[mask, 0] + cx).astype(int)
        abs_ys = (coords[mask, 1] + cy).astype(int)
        abs_zs = (coords[mask, 2] + cz).astype(int)
        return vol[abs_zs, abs_ys, abs_xs]

    def _compute_stats(self, meas: dict):
        voxels = self._sample_voxels(meas)
        if voxels.size == 0:
            meas.update(avg_raw=0.0, std_raw=0.0, avg_hu=0.0, std_hu=0.0)
            return
        meas["avg_raw"] = float(np.mean(voxels))
        meas["std_raw"] = float(np.std(voxels))
        hu = voxels * self._rescale_slope + self._rescale_intercept
        meas["avg_hu"] = float(np.mean(hu))
        meas["std_hu"] = float(np.std(hu))

    # ══════════════════════════════════════════════════ measurement control ═══

    def _get_measurement(self, mid: int) -> Optional[dict]:
        return next((m for m in self._measurements if m["id"] == mid), None)

    def _apply_controls_to_measurement(self, meas: dict):
        idx = self._shape_combo.currentIndex()
        meas["shape"] = self._SHAPE_NAMES[idx]
        meas["rot_x"] = meas["rot_y"] = meas["rot_z"] = 0.0
        if idx == self._SHAPE_SPHERE:
            meas["radius"] = float(self._sp_radius.value())
        elif idx == self._SHAPE_BOX:
            meas["box_w"] = float(self._sp_bw.value())
            meas["box_h"] = float(self._sp_bh.value())
            meas["box_d"] = float(self._sp_bd.value())
            meas["rot_x"] = self._sp_rx.value()
            meas["rot_y"] = self._sp_ry.value()
            meas["rot_z"] = self._sp_rz.value()
        else:
            meas["cyl_radius"] = float(self._sp_cr.value())
            meas["cyl_height"] = float(self._sp_ch.value())
            meas["rot_x"] = self._sp_crx.value()
            meas["rot_y"] = self._sp_cry.value()

    def _load_controls_from_measurement(self, meas: dict):
        self._updating_controls = True
        try:
            idx = self._SHAPE_NAMES.index(meas.get("shape", "sphere"))
            self._shape_combo.setCurrentIndex(idx)
            self._shape_params_stack.setCurrentIndex(idx)
            if idx == self._SHAPE_SPHERE:
                self._sp_radius.setValue(max(1, int(round(meas.get("radius", 5)))))
            elif idx == self._SHAPE_BOX:
                self._sp_bw.setValue(max(1, int(round(meas.get("box_w", 10)))))
                self._sp_bh.setValue(max(1, int(round(meas.get("box_h", 10)))))
                self._sp_bd.setValue(max(1, int(round(meas.get("box_d", 10)))))
                self._sp_rx.setValue(meas.get("rot_x", 0))
                self._sp_ry.setValue(meas.get("rot_y", 0))
                self._sp_rz.setValue(meas.get("rot_z", 0))
            else:
                self._sp_cr.setValue(max(1, int(round(meas.get("cyl_radius", 5)))))
                self._sp_ch.setValue(max(1, int(round(meas.get("cyl_height", 10)))))
                self._sp_crx.setValue(meas.get("rot_x", 0))
                self._sp_cry.setValue(meas.get("rot_y", 0))
            self._pos_x_spin.setValue(int(meas.get("cx", 0)))
            self._pos_y_spin.setValue(int(meas.get("cy", 0)))
            self._pos_z_spin.setValue(int(meas.get("cz", 0)))
            c = meas.get("color", [1, 0.5, 0, 0.6])
            self._meas_color = (float(c[0]), float(c[1]), float(c[2]), float(c[3]))
            self._update_meas_color_button()
        finally:
            self._updating_controls = False

    def _select_measurement(self, mid: int):
        self._selected_mid = mid
        meas = self._get_measurement(mid)
        if meas is None:
            self._deselect_measurement()
            return
        self._load_controls_from_measurement(meas)
        if self._n_slices > 0:
            self._pos_x_spin.setRange(0, self._img_width  - 1)
            self._pos_y_spin.setRange(0, self._img_height - 1)
            self._pos_z_spin.setRange(0, self._n_slices   - 1)
        self._pos_edit_frame.show()
        self._updating_controls = True
        try:
            for row in range(self._meas_table.rowCount()):
                item = self._meas_table.item(row, 0)
                if item and int(item.text()) == mid:
                    self._meas_table.selectRow(row)
                    break
        finally:
            self._updating_controls = False

    def _deselect_measurement(self):
        self._selected_mid = None
        self._pos_edit_frame.hide()
        self._updating_controls = True
        try:
            self._meas_table.clearSelection()
        finally:
            self._updating_controls = False

    def _update_measurements_table(self):
        self._meas_table.setRowCount(0)
        for meas in self._measurements:
            row = self._meas_table.rowCount()
            self._meas_table.insertRow(row)
            shape = meas["shape"]
            if shape == "sphere":
                params = f"r={meas.get('radius', 0):.1f}"
                orient = "–"
            elif shape == "box":
                params = f"{meas.get('box_w',0):.0f}×{meas.get('box_h',0):.0f}×{meas.get('box_d',0):.0f}"
                rx, ry, rz = meas.get("rot_x",0), meas.get("rot_y",0), meas.get("rot_z",0)
                orient = f"Rx={rx:.0f}° Ry={ry:.0f}° Rz={rz:.0f}°" if (rx or ry or rz) else "–"
            else:
                params = f"r={meas.get('cyl_radius',0):.1f} h={meas.get('cyl_height',0):.1f}"
                rx, ry = meas.get("rot_x",0), meas.get("rot_y",0)
                orient = f"Rx={rx:.0f}° Ry={ry:.0f}°" if (rx or ry) else "–"
            values = [
                str(meas["id"]), shape.capitalize(),
                str(meas["cx"]), str(meas["cy"]), str(meas["cz"]),
                params, orient,
                f"{meas.get('avg_raw',0):.1f}", f"{meas.get('std_raw',0):.1f}",
                f"{meas.get('avg_hu', 0):.1f}", f"{meas.get('std_hu', 0):.1f}",
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                self._meas_table.setItem(row, col, item)

    # ══════════════════════════════════════════════════════════════ slots ═════

    def _on_slice_clicked(self, pixel_x: int, pixel_y: int):
        if self._volume_array is None:
            return
        mid = self._next_mid
        self._next_mid += 1
        meas: Dict[str, Any] = {
            "id": mid, "shape": "sphere",
            "cx": pixel_x, "cy": pixel_y, "cz": self._current_slice_index,
            "radius": 5.0,
            "box_w": 10.0, "box_h": 10.0, "box_d": 10.0,
            "cyl_radius": 5.0, "cyl_height": 10.0,
            "rot_x": 0.0, "rot_y": 0.0, "rot_z": 0.0,
            "avg_raw": 0.0, "std_raw": 0.0,
            "avg_hu":  0.0, "std_hu":  0.0,
            "color": list(self._meas_color),
        }
        self._apply_controls_to_measurement(meas)
        self._measurements.append(meas)
        self._compute_stats(meas)
        self._rebuild_measurement_visual(meas)
        self._update_measurements_table()
        self._select_measurement(mid)

    def _on_table_selection_changed(self):
        if self._updating_controls:
            return
        rows = self._meas_table.selectedItems()
        if not rows:
            self._selected_mid = None
            self._pos_edit_frame.hide()
            return
        row = self._meas_table.currentRow()
        item = self._meas_table.item(row, 0)
        if item is None:
            return
        mid = int(item.text())
        if mid == self._selected_mid:
            return
        self._selected_mid = mid
        meas = self._get_measurement(mid)
        if meas:
            self._load_controls_from_measurement(meas)
            if self._n_slices > 0:
                self._pos_x_spin.setRange(0, self._img_width  - 1)
                self._pos_y_spin.setRange(0, self._img_height - 1)
                self._pos_z_spin.setRange(0, self._n_slices   - 1)
            self._pos_edit_frame.show()

    def _on_shape_combo_changed(self, index: int):
        self._shape_params_stack.setCurrentIndex(index)
        if self._updating_controls:
            return
        if self._selected_mid is not None:
            meas = self._get_measurement(self._selected_mid)
            if meas:
                self._apply_controls_to_measurement(meas)
                self._compute_stats(meas)
                self._rebuild_measurement_visual(meas)
                self._update_measurements_table()
        # Rebuild hover preview with new shape
        if self._hover_pos is not None:
            self._rebuild_hover_visual()

    def _on_shape_param_changed(self):
        if self._updating_controls:
            return
        if self._selected_mid is not None:
            meas = self._get_measurement(self._selected_mid)
            if meas:
                self._apply_controls_to_measurement(meas)
                self._compute_stats(meas)
                self._rebuild_measurement_visual(meas)
                self._update_measurements_table()
        # Rebuild hover preview with new params
        if self._hover_pos is not None:
            self._rebuild_hover_visual()

    def _on_pos_spin_changed(self):
        if self._updating_controls:
            return
        if self._selected_mid is not None:
            meas = self._get_measurement(self._selected_mid)
            if meas:
                meas["cx"] = self._pos_x_spin.value()
                meas["cy"] = self._pos_y_spin.value()
                meas["cz"] = self._pos_z_spin.value()
                self._compute_stats(meas)
                self._rebuild_measurement_visual(meas)
                self._update_measurements_table()

    def _on_delete_btn_clicked(self):
        if self._selected_mid is None:
            return
        mid = self._selected_mid
        self._measurements = [m for m in self._measurements if m["id"] != mid]
        vis = self._measurement_visuals.pop(mid, None)
        if vis is not None:
            try:
                vis.parent = None
            except Exception:
                pass
        if self._canvas is not None:
            self._canvas.update()
        self._deselect_measurement()
        self._update_measurements_table()

    def _on_hover_moved(self, pixel_x: int, pixel_y: int):
        self._last_hover_px = (pixel_x, pixel_y)
        if not self._vispy_available or self._volume_array is None or self._view is None:
            return
        n, h, w = self._volume_array.shape
        pos = self._voxel_to_world(float(pixel_x), float(pixel_y),
                                   float(self._current_slice_index))
        if self._hover_visual is None:
            self._rebuild_hover_visual(pos)
        else:
            self._move_hover_visual(pos)

    def _on_hover_left(self):
        self._last_hover_px = None
        if self._hover_visual is not None:
            self._hover_visual.visible = False
        if self._canvas is not None:
            self._canvas.update()

    def _on_wheel_scroll(self, delta: int):
        if self._n_slices > 0:
            self._slice_spin.setValue(
                max(1, min(self._n_slices, self._slice_spin.value() + delta)))

    def _on_slice_spin_changed(self, value: int):
        if self._volume_array is None:
            return
        self._current_slice_index = value - 1
        self._update_slice_display(self._current_slice_index)
        self.slice_changed.emit(self._current_slice_index)
        if self._last_hover_px is not None:
            self._on_hover_moved(*self._last_hover_px)
        elif self._hover_visual is not None:
            self._hover_visual.visible = False
            if self._canvas is not None:
                self._canvas.update()

    def _on_orient_flip_changed(self):
        self._orient_flip_x = self._flip_x_btn.isChecked()
        self._orient_flip_y = self._flip_y_btn.isChecked()
        self._orient_flip_z = self._flip_z_btn.isChecked()
        if self._volume_array is None or self._view is None:
            return
        n, h, w = self._volume_array.shape
        vol_norm = ((self._volume_array - self._vol_min) /
                    (self._vol_max - self._vol_min)).astype(np.float32)
        vol_display = self._prepare_vol_display(vol_norm)
        self._volume_visual.set_data(vol_display)
        for meas in self._measurements:
            self._rebuild_measurement_visual(meas)
        if self._hover_pos is not None:
            self._rebuild_hover_visual()
        if self._canvas is not None:
            self._canvas.update()

    def _on_hover_color_clicked(self):
        r, g, b, a = self._hover_color
        initial = QColor(int(r * 255), int(g * 255), int(b * 255))
        color = QColorDialog.getColor(initial, self, "Preview shape colour")
        if color.isValid():
            self._hover_color = (color.redF(), color.greenF(), color.blueF(), 0.45)
            self._update_hover_color_button()
            if self._hover_pos is not None:
                self._rebuild_hover_visual()

    def _on_meas_color_clicked(self):
        r, g, b, a = self._meas_color
        initial = QColor(int(r * 255), int(g * 255), int(b * 255))
        color = QColorDialog.getColor(initial, self, "Measurement colour")
        if not color.isValid():
            return
        self._meas_color = (color.redF(), color.greenF(), color.blueF(), 0.6)
        self._update_meas_color_button()
        if self._selected_mid is not None:
            meas = self._get_measurement(self._selected_mid)
            if meas:
                meas["color"] = list(self._meas_color)
                self._rebuild_measurement_visual(meas)

    def _on_export_measurements(self):
        if not self._measurements:
            return
        ts = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export 3D Measurements",
            f"3d_measurements_{ts}.json", "JSON Files (*.json)")
        if not path:
            return
        with open(path, "w") as f:
            json.dump(self._measurements, f, indent=2, default=str)

    def _on_import_measurements(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import 3D Measurements", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception as e:
            print(f"Failed to import 3D measurements: {e}")
            return
        for m in data:
            try:
                m["id"] = int(m["id"])
                self._next_mid = max(self._next_mid, m["id"] + 1)
                self._measurements.append(m)
                self._rebuild_measurement_visual(m)
            except Exception as e:
                print(f"Skipped invalid measurement entry: {e}")
        self._update_measurements_table()

    # ── slice display ──────────────────────────────────────────────────────────

    def _update_slice_display(self, index: int):
        if self._volume_array is None:
            self._slice_widget.set_image(None)
            return
        idx = max(0, min(self._n_slices - 1, index))
        arr = self._volume_array[idx]
        norm = ((arr - self._vol_min) / (self._vol_max - self._vol_min) * 255).clip(0, 255).astype(np.uint8)
        qimage = QImage(norm.data, norm.shape[1], norm.shape[0],
                        norm.shape[1], QImage.Format_Grayscale8).copy()
        self._slice_widget.set_image(qimage)

    def _update_nav_label(self):
        if self._n_slices > 0:
            self._slice_spin.blockSignals(True)
            self._slice_spin.setRange(1, self._n_slices)
            self._slice_spin.setValue(self._current_slice_index + 1)
            self._slice_spin.setEnabled(True)
            self._slice_spin.blockSignals(False)
            self._slice_total_label.setText(f"/ {self._n_slices}")
        else:
            self._slice_spin.blockSignals(True)
            self._slice_spin.setRange(1, 1)
            self._slice_spin.setValue(1)
            self._slice_spin.setEnabled(False)
            self._slice_spin.blockSignals(False)
            self._slice_total_label.setText("/ –")

    # ── colour buttons ─────────────────────────────────────────────────────────

    def _update_hover_color_button(self):
        r, g, b, _ = self._hover_color
        hex_col = "#{:02x}{:02x}{:02x}".format(int(r*255), int(g*255), int(b*255))
        self._hover_color_btn.setStyleSheet(
            f"background-color: {hex_col}; border: 1px solid #555; border-radius: 3px;")

    def _update_meas_color_button(self):
        r, g, b, _ = self._meas_color
        hex_col = "#{:02x}{:02x}{:02x}".format(int(r*255), int(g*255), int(b*255))
        self._meas_color_btn.setStyleSheet(
            f"background-color: {hex_col}; border: 1px solid #555; border-radius: 3px;")

    def _on_export_3d(self):
        if self._canvas is None:
            return
        ts = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export 3D View", f"3d_view_{ts}.png", "PNG Files (*.png)")
        if not path:
            return
        native = self._canvas.native
        pm = native.grab()
        pm.setDevicePixelRatio(native.devicePixelRatio())
        pm.save(path, "PNG")
