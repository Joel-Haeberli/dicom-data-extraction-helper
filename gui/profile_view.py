#!/usr/bin/env python3
"""
Profile View Tab

Left column  : DICOM image with a moveable crosshair (click / drag).
Right column : two chart groups (horizontal top, vertical bottom).
               Each group has "px" and "mm" sub-tabs.
               All saved measurements are overlaid on every chart.
Bottom strip : X/Y spinboxes · image-nav spinbox · chunk-factor spinbox
               Measure · Export Charts ▼ · Export (JSON) · Import
               Compact measurements table (#, X, Y, kVp, Spacing, Color, Delete).

Clicking a table row moves the crosshair to that measurement's position.
"""

import json
from typing import Optional, List, Dict, Tuple, Any

import numpy as np

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QSplitter, QTabWidget,
    QLabel, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
    QSizePolicy, QFileDialog, QColorDialog, QMenu, QCheckBox,
)
from PySide6.QtCore import Qt, QPointF, Signal, QDateTime, QSize
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QPixmap, QImage

try:
    from gui.utils.image_utils import dicom_to_qimage
    _HAS_IMAGE_UTILS = True
except ImportError:
    _HAS_IMAGE_UTILS = False

from gui.range_slider import RangeSliderWidget


_COLORS: List[QColor] = [
    QColor("#FF6B6B"), QColor("#FFA500"), QColor("#98FB98"), QColor("#87CEEB"),
    QColor("#DDA0DD"), QColor("#F0E68C"), QColor("#20B2AA"), QColor("#FF69B4"),
]

_COL_LABEL   = 0
_COL_X       = 1
_COL_Y       = 2
_COL_Z       = 3
_COL_KVP     = 4
_COL_SPACING = 5
_COL_COLOR   = 6
_COL_DELETE  = 7
_NUM_COLS    = 8


# ══════════════════════════════════════════════════════ crosshair image widget

class CrosshairImageWidget(QWidget):
    """Scales a QImage to fit; yellow live crosshair + optional per-measurement
    crosshairs (in each measurement's color).  Click / drag moves the live
    crosshair."""

    position_changed = Signal(int, int)   # col x, row y

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: Optional[QPixmap] = None
        self._iw: int = 0
        self._ih: int = 0
        self._cx: int = 0
        self._cy: int = 0
        self._meas_crosshairs: List[Tuple[int, int, QColor]] = []
        self._show_meas: bool = True
        # range that the live crosshair lines are clipped to
        self._h_from: int = 0
        self._h_to:   int = 999999
        self._v_from: int = 0
        self._v_to:   int = 999999
        # chart-hover highlights
        self._hover_col: Optional[int] = None  # column highlighted from H-chart hover
        self._hover_row: Optional[int] = None  # row    highlighted from V-chart hover
        self.setCursor(Qt.CrossCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(200, 200)

    # ── public API ────────────────────────────────────────────────────────────

    def set_image(self, qimage: Optional[QImage]):
        if qimage is None or qimage.isNull():
            self._pixmap = None
            self._iw = self._ih = 0
        else:
            self._pixmap = QPixmap.fromImage(qimage)
            self._iw, self._ih = qimage.width(), qimage.height()
        self.update()

    def set_crosshair(self, x: int, y: int):
        self._cx, self._cy = x, y
        self.update()

    def set_hover_col(self, col: Optional[int]):
        self._hover_col = col
        self.update()

    def set_hover_row(self, row: Optional[int]):
        self._hover_row = row
        self.update()

    def set_profile_range(self,
                          h_from: int, h_to: int,
                          v_from: int, v_to: int):
        self._h_from = h_from
        self._h_to   = h_to
        self._v_from = v_from
        self._v_to   = v_to
        self.update()

    def set_measurement_crosshairs(self,
                                    crosshairs: List[Tuple[int, int, QColor]],
                                    show: bool):
        self._meas_crosshairs = crosshairs
        self._show_meas = show
        self.update()

    def grab_with_crosshairs(self) -> QPixmap:
        """Return a QPixmap of the widget as currently rendered."""
        return self.grab()

    # ── internal helpers ──────────────────────────────────────────────────────

    def _draw_rect(self) -> Optional[Tuple[int, int, int, int]]:
        if not self._pixmap or self._iw == 0:
            return None
        ww, wh = self.width(), self.height()
        if ww <= 0 or wh <= 0:
            return None
        s = min(ww / self._iw, wh / self._ih)
        dw, dh = int(self._iw * s), int(self._ih * s)
        return (ww - dw) // 2, (wh - dh) // 2, dw, dh

    def _img_to_display(self, ix, iy, dx, dy, dw, dh):
        return (dx + int(ix / self._iw * dw),
                dy + int(iy / self._ih * dh))

    # ── Qt overrides ──────────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(20, 20, 20))
        rc = self._draw_rect()
        if not rc:
            p.setPen(QColor(100, 100, 100))
            p.drawText(self.rect(), Qt.AlignCenter, "No image")
            return
        dx, dy, dw, dh = rc
        p.drawPixmap(dx, dy, dw, dh, self._pixmap)

        if not (self._iw and self._ih):
            return

        # — saved measurement crosshairs (drawn first, under live crosshair) —
        if self._show_meas:
            for mx, my, color in self._meas_crosshairs:
                cx, cy = self._img_to_display(mx, my, dx, dy, dw, dh)
                p.setPen(QPen(color, 1))
                p.drawLine(dx, cy, dx + dw - 1, cy)
                p.drawLine(cx, dy, cx, dy + dh - 1)
                # small filled dot at intersection
                p.setBrush(QBrush(color))
                p.setPen(Qt.NoPen)
                p.drawEllipse(cx - 4, cy - 4, 8, 8)

        # — chart-hover highlight (drawn above measurements, below live crosshair)
        hover_pen = QPen(QColor(255, 140, 0), 1, Qt.PenStyle.DashLine)
        p.setBrush(Qt.NoBrush)
        p.setPen(hover_pen)
        if self._hover_col is not None and self._iw:
            hx, _ = self._img_to_display(
                max(0, min(self._iw - 1, self._hover_col)), 0, dx, dy, dw, dh)
            p.drawLine(hx, dy, hx, dy + dh - 1)
        if self._hover_row is not None and self._ih:
            _, hy = self._img_to_display(
                0, max(0, min(self._ih - 1, self._hover_row)), dx, dy, dw, dh)
            p.drawLine(dx, hy, dx + dw - 1, hy)

        # — live crosshair (drawn last, always on top) ————————————————————
        cx, cy = self._img_to_display(self._cx, self._cy, dx, dy, dw, dh)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 220, 0), 1))
        # horizontal line — clipped to H range
        h_x1, _ = self._img_to_display(
            max(0, min(self._iw - 1, self._h_from)), self._cy, dx, dy, dw, dh)
        h_x2, _ = self._img_to_display(
            max(0, min(self._iw - 1, self._h_to)),   self._cy, dx, dy, dw, dh)
        p.drawLine(h_x1, cy, h_x2, cy)
        # vertical line — clipped to V range
        _, v_y1 = self._img_to_display(
            self._cx, max(0, min(self._ih - 1, self._v_from)), dx, dy, dw, dh)
        _, v_y2 = self._img_to_display(
            self._cx, max(0, min(self._ih - 1, self._v_to)),   dx, dy, dw, dh)
        p.drawLine(cx, v_y1, cx, v_y2)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._move(e.position())

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            self._move(e.position())

    def _move(self, pos):
        rc = self._draw_rect()
        if not rc or not self._iw:
            return
        dx, dy, dw, dh = rc
        mx = max(dx, min(dx + dw - 1, pos.x()))
        my = max(dy, min(dy + dh - 1, pos.y()))
        ix = max(0, min(self._iw - 1, int((mx - dx) / dw * self._iw)))
        iy = max(0, min(self._ih - 1, int((my - dy) / dh * self._ih)))
        self._cx, self._cy = ix, iy
        self.update()
        self.position_changed.emit(ix, iy)


# ══════════════════════════════════════════════════════ hover-aware chart view

class ProfileChartView(QChartView):
    """QChartView that emits the chart-axis x-value under the cursor."""

    chart_hovered   = Signal(float)  # x-axis value at current mouse position
    chart_hover_left = Signal()      # mouse left the plot area

    def __init__(self, chart, parent=None):
        super().__init__(chart, parent)
        self.setMouseTracking(True)

    def mouseMoveEvent(self, e):
        scene_pos = self.mapToScene(e.position().toPoint())
        chart_pos = self.chart().mapFromScene(scene_pos)
        if self.chart().plotArea().contains(chart_pos):
            value = self.chart().mapToValue(chart_pos)
            self.chart_hovered.emit(value.x())
        else:
            self.chart_hover_left.emit()
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        self.chart_hover_left.emit()
        super().leaveEvent(e)


# ══════════════════════════════════════════════════════════════ profile view

class ProfileView(QWidget):
    """
    Full profile-view tab.

    Signals
    -------
    image_index_changed(int)  — 0-based index; emitted when the image nav
                                spinbox changes.
    """

    image_index_changed = Signal(int)
    load_file_requested  = Signal(str)   # absolute path of the image to load

    def __init__(self, parent=None):
        super().__init__(parent)

        self._pixel_array: Optional[np.ndarray] = None
        self._slope: float = 1.0
        self._intercept: float = 0.0
        self._has_hu: bool = False
        self._pixel_spacing: Optional[Tuple[float, float]] = None
        self._kvp: Optional[float] = None
        self._z:   Optional[float] = None
        self._chunk_factor: int = 1
        self._light_mode: bool = False
        self._show_all_meas: bool = False
        self._current_path: Optional[str] = None   # path of the image currently displayed

        self._measurements: List[Dict[str, Any]] = []
        self._next_id: int = 1
        # id → (h_px, h_mm, v_px, v_mm)
        self._series_map: Dict[int, Tuple[QLineSeries, QLineSeries,
                                          QLineSeries, QLineSeries]] = {}

        self._setup_ui()

    # ══════════════════════════════════════════════════════════ UI setup

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        # ── top: image | charts ───────────────────────────────────────────────
        h_split = QSplitter(Qt.Horizontal)
        h_split.setChildrenCollapsible(False)

        self._img = CrosshairImageWidget()
        self._img.position_changed.connect(self._on_image_position_changed)

        # Grid: [reset | H-slider]
        #       [V-slider | image  ]
        img_container = QWidget()
        img_grid = QGridLayout(img_container)
        img_grid.setContentsMargins(0, 0, 0, 0)
        img_grid.setSpacing(2)

        self._h_slider = RangeSliderWidget(Qt.Horizontal)
        self._h_slider.setToolTip("Horizontal profile range — drag handles or scroll wheel")
        self._h_slider.range_changed.connect(self._on_range_changed)

        self._v_slider = RangeSliderWidget(Qt.Vertical)
        self._v_slider.setToolTip("Vertical profile range — drag handles or scroll wheel")
        self._v_slider.range_changed.connect(self._on_range_changed)

        _reset_btn = QPushButton("↺")
        _reset_btn.setFixedSize(28, 28)
        _reset_btn.setToolTip("Reset both range selectors to the full image extent")
        _reset_btn.clicked.connect(self._on_reset_range)

        img_grid.addWidget(_reset_btn,       0, 0, Qt.AlignCenter)
        img_grid.addWidget(self._h_slider,   0, 1)
        img_grid.addWidget(self._v_slider,   1, 0)
        img_grid.addWidget(self._img,        1, 1)
        img_grid.setColumnStretch(1, 1)
        img_grid.setRowStretch(1, 1)

        h_split.addWidget(img_container)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(2)

        v_split = QSplitter(Qt.Vertical)
        v_split.setChildrenCollapsible(False)

        # — horizontal profile (px + mm) ———————————————————————————————————
        (self._hc_px, self._hc_ax_px, self._hc_ay_px) = self._make_chart(
            "Horizontal Profile", "Column", "Value")
        self._h_live_px = self._attach_series(
            self._hc_px, self._hc_ax_px, self._hc_ay_px,
            "live", QColor(0, 210, 210), width=2)

        (self._hc_mm, self._hc_ax_mm, self._hc_ay_mm) = self._make_chart(
            "Horizontal Profile", "Column (mm)", "Value")
        self._h_live_mm = self._attach_series(
            self._hc_mm, self._hc_ax_mm, self._hc_ay_mm,
            "live", QColor(0, 210, 210), width=2)

        self._h_cv_px = ProfileChartView(self._hc_px)
        self._h_cv_mm = ProfileChartView(self._hc_mm)
        self._h_stats_px, h_tab_px = self._make_chart_tab(self._h_cv_px)
        self._h_stats_mm, h_tab_mm = self._make_chart_tab(self._h_cv_mm)
        self._h_chart_tabs = QTabWidget()
        self._h_chart_tabs.addTab(h_tab_px, "px")
        self._h_chart_tabs.addTab(h_tab_mm, "mm")
        self._h_chart_tabs.setMinimumHeight(120)

        # — vertical profile (px + mm) ——————————————————————————————————————
        (self._vc_px, self._vc_ax_px, self._vc_ay_px) = self._make_chart(
            "Vertical Profile", "Row", "Value")
        self._v_live_px = self._attach_series(
            self._vc_px, self._vc_ax_px, self._vc_ay_px,
            "live", QColor(0, 210, 210), width=2)

        (self._vc_mm, self._vc_ax_mm, self._vc_ay_mm) = self._make_chart(
            "Vertical Profile", "Row (mm)", "Value")
        self._v_live_mm = self._attach_series(
            self._vc_mm, self._vc_ax_mm, self._vc_ay_mm,
            "live", QColor(0, 210, 210), width=2)

        self._v_cv_px = ProfileChartView(self._vc_px)
        self._v_cv_mm = ProfileChartView(self._vc_mm)
        self._v_stats_px, v_tab_px = self._make_chart_tab(self._v_cv_px)
        self._v_stats_mm, v_tab_mm = self._make_chart_tab(self._v_cv_mm)
        self._v_chart_tabs = QTabWidget()
        self._v_chart_tabs.addTab(v_tab_px, "px")
        self._v_chart_tabs.addTab(v_tab_mm, "mm")
        self._v_chart_tabs.setMinimumHeight(120)

        # — wire chart hover → image highlight ————————————————————————————
        self._h_cv_px.chart_hovered.connect(
            lambda x: self._on_h_chart_hovered(x, False))
        self._h_cv_mm.chart_hovered.connect(
            lambda x: self._on_h_chart_hovered(x, True))
        self._h_cv_px.chart_hover_left.connect(
            lambda: self._img.set_hover_col(None))
        self._h_cv_mm.chart_hover_left.connect(
            lambda: self._img.set_hover_col(None))

        self._v_cv_px.chart_hovered.connect(
            lambda x: self._on_v_chart_hovered(x, False))
        self._v_cv_mm.chart_hovered.connect(
            lambda x: self._on_v_chart_hovered(x, True))
        self._v_cv_px.chart_hover_left.connect(
            lambda: self._img.set_hover_row(None))
        self._v_cv_mm.chart_hover_left.connect(
            lambda: self._img.set_hover_row(None))

        v_split.addWidget(self._h_chart_tabs)
        v_split.addWidget(self._v_chart_tabs)
        right_layout.addWidget(v_split, 1)
        h_split.addWidget(right)
        h_split.setSizes([420, 380])
        outer.addWidget(h_split, 1)

        # ── controls row ──────────────────────────────────────────────────────
        ctrl = QHBoxLayout()
        ctrl.setSpacing(6)

        ctrl.addWidget(QLabel("X (col):"))
        self._x_spin = QSpinBox()
        self._x_spin.setRange(0, 9999)
        self._x_spin.valueChanged.connect(self._on_xy_spin_changed)
        ctrl.addWidget(self._x_spin)

        ctrl.addWidget(QLabel("Y (row):"))
        self._y_spin = QSpinBox()
        self._y_spin.setRange(0, 9999)
        self._y_spin.valueChanged.connect(self._on_xy_spin_changed)
        ctrl.addWidget(self._y_spin)

        ctrl.addWidget(QLabel("|"))

        ctrl.addWidget(QLabel("Image:"))
        self._img_spin = QSpinBox()
        self._img_spin.setRange(1, 1)
        self._img_spin.setToolTip("Scroll through images in the series")
        self._img_spin.valueChanged.connect(self._on_img_spin_changed)
        ctrl.addWidget(self._img_spin)
        self._img_total_label = QLabel("/ 1")
        ctrl.addWidget(self._img_total_label)

        ctrl.addWidget(QLabel("|"))

        ctrl.addWidget(QLabel("Chunk size:"))
        self._chunk_spin = QSpinBox()
        self._chunk_spin.setRange(1, 512)
        self._chunk_spin.setValue(1)
        self._chunk_spin.setToolTip(
            "Average every N consecutive pixels into one point (smoothing)")
        self._chunk_spin.valueChanged.connect(self._on_chunk_changed)
        ctrl.addWidget(self._chunk_spin)

        self._light_check = QCheckBox("Light mode")
        self._light_check.setChecked(False)
        self._light_check.toggled.connect(self._on_theme_toggled)
        ctrl.addWidget(self._light_check)

        self._all_meas_check = QCheckBox("All Measurements")
        self._all_meas_check.setChecked(False)
        self._all_meas_check.setToolTip(
            "Show measurements from all images in the charts\n"
            "(unchecked = current image only)")
        self._all_meas_check.toggled.connect(self._on_all_meas_toggled)
        ctrl.addWidget(self._all_meas_check)

        ctrl.addStretch(1)

        self._measure_btn = QPushButton("Measure")
        self._measure_btn.setToolTip("Save current crosshair as a measurement")
        self._measure_btn.clicked.connect(self._on_measure)
        ctrl.addWidget(self._measure_btn)

        self._show_meas_check = QCheckBox("Show Meas.")
        self._show_meas_check.setChecked(True)
        self._show_meas_check.setToolTip(
            "Show/hide saved measurement crosshairs on the image")
        self._show_meas_check.toggled.connect(self._on_show_meas_toggled)
        ctrl.addWidget(self._show_meas_check)

        # Export charts + image dropdown button
        self._export_charts_btn = QPushButton("Export ▼")
        charts_menu = QMenu(self._export_charts_btn)
        charts_menu.addAction("Export Image",
                               self._on_export_image)
        charts_menu.addSeparator()
        charts_menu.addAction("Export Charts Separate (2 files)",
                               self._on_export_charts_separate)
        charts_menu.addAction("Export Charts Side-by-Side (1 file)",
                               self._on_export_charts_sidebyside)
        self._export_charts_btn.setMenu(charts_menu)
        ctrl.addWidget(self._export_charts_btn)

        self._export_btn = QPushButton("Export (JSON)")
        self._export_btn.setToolTip("Export measurements to JSON")
        self._export_btn.clicked.connect(self._on_export_json)
        ctrl.addWidget(self._export_btn)

        self._import_btn = QPushButton("Import")
        self._import_btn.setToolTip("Import measurements from JSON")
        self._import_btn.clicked.connect(self._on_import)
        ctrl.addWidget(self._import_btn)

        outer.addLayout(ctrl, 0)

        # ── measurements table ────────────────────────────────────────────────
        self._table = QTableWidget(0, _NUM_COLS)
        self._table.setHorizontalHeaderLabels(
            ["#", "X (col)", "Y (row)", "Z (mm)", "kVp", "Spacing (mm)", "Color", "Delete"])
        for col in range(_COL_COLOR):
            self._table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_COLOR, QHeaderView.Fixed)
        self._table.setColumnWidth(_COL_COLOR, 50)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setMaximumHeight(140)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet("""
            QTableWidget { background:#2b2b2b; color:#e0e0e0; gridline-color:#444; }
            QHeaderView::section { background:#3c3c3c; color:#e0e0e0;
                                   padding:3px; border:1px solid #444; }
        """)
        self._table.cellClicked.connect(self._on_table_cell_clicked)
        outer.addWidget(self._table, 0)

    # ══════════════════════════════════════════════════════ chart helpers

    @staticmethod
    def _make_chart_tab(chart_view: QChartView) -> Tuple["QLabel", QWidget]:
        """Wrap a QChartView with a compact stats bar. Returns (stats_label, container)."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(chart_view, 1)
        stats = QLabel("Mean: —   Std: —   Min: —   Max: —")
        stats.setStyleSheet(
            "color:#aaaaaa; font-size:10px; padding:2px 4px;"
            "background:#111111; border-top:1px solid #333;")
        stats.setAlignment(Qt.AlignLeft)
        layout.addWidget(stats, 0)
        return stats, container

    @staticmethod
    def _make_chart(title: str, x_label: str, y_label: str):
        chart = QChart()
        chart.setTitle(title)
        chart.setTitleBrush(Qt.white)
        chart.setBackgroundBrush(Qt.black)
        chart.setPlotAreaBackgroundBrush(Qt.black)
        chart.setPlotAreaBackgroundVisible(True)
        chart.legend().setVisible(True)
        chart.legend().setLabelColor(Qt.white)
        chart.setAnimationOptions(QChart.NoAnimation)

        def _ax(label, fmt="%.0f"):
            a = QValueAxis()
            a.setTitleText(label)
            a.setLabelFormat(fmt)
            a.setLabelsColor(Qt.white)
            a.setTitleBrush(Qt.white)
            a.setGridLineColor(Qt.darkGray)
            a.setLinePenColor(Qt.white)
            return a

        ax = _ax(x_label)
        ay = _ax(y_label, "%.1f")
        chart.addAxis(ax, Qt.AlignBottom)
        chart.addAxis(ay, Qt.AlignLeft)
        return chart, ax, ay

    @staticmethod
    def _attach_series(chart, ax, ay, name: str, color: QColor,
                       width: int = 1) -> QLineSeries:
        s = QLineSeries()
        s.setName(name)
        pen = s.pen()
        pen.setColor(color)
        pen.setWidth(width)
        s.setPen(pen)
        chart.addSeries(s)
        s.attachAxis(ax)
        s.attachAxis(ay)
        return s

    # ══════════════════════════════════════════════════════ data / chunk helpers

    def _hu(self) -> Optional[np.ndarray]:
        if self._pixel_array is None:
            return None
        return self._pixel_array.astype(np.float32) * self._slope + self._intercept

    def _h_profile(self, y: int) -> List[float]:
        arr = self._hu()
        if arr is None or arr.ndim < 2 or y >= arr.shape[0]:
            return []
        return arr[y, :].tolist()

    def _v_profile(self, x: int) -> List[float]:
        arr = self._hu()
        if arr is None or arr.ndim < 2 or x >= arr.shape[1]:
            return []
        return arr[:, x].tolist()

    def _h_x_mm(self, n: int) -> Optional[List[float]]:
        if self._pixel_spacing is None:
            return None
        return [i * self._pixel_spacing[1] for i in range(n)]

    def _v_x_mm(self, n: int) -> Optional[List[float]]:
        if self._pixel_spacing is None:
            return None
        return [i * self._pixel_spacing[0] for i in range(n)]

    @staticmethod
    def _apply_chunk(y_vals: List[float],
                     x_vals: Optional[List[float]],
                     factor: int) -> Tuple[List[float], Optional[List[float]]]:
        """Average every `factor` consecutive samples into one point."""
        if factor <= 1 or not y_vals:
            return y_vals, x_vals
        n_chunks = len(y_vals) // factor
        if n_chunks == 0:
            return y_vals, x_vals
        chunked_y = [
            sum(y_vals[i * factor:(i + 1) * factor]) / factor
            for i in range(n_chunks)
        ]
        if x_vals is not None:
            chunked_x: Optional[List[float]] = [
                sum(x_vals[i * factor:(i + 1) * factor]) / factor
                for i in range(n_chunks)
            ]
        else:
            chunked_x = None
        return chunked_y, chunked_x

    @staticmethod
    def _apply_range(y_vals: List[float],
                     from_idx: int, to_idx: int
                     ) -> Tuple[List[float], List[int]]:
        """Clip y_vals to [from_idx, to_idx] inclusive.
        Returns (clipped_y, absolute_x_indices)."""
        from_idx = max(0, from_idx)
        to_idx   = min(len(y_vals) - 1, to_idx)
        if from_idx > to_idx or not y_vals:
            return [], []
        sliced = y_vals[from_idx:to_idx + 1]
        x_idx  = list(range(from_idx, from_idx + len(sliced)))
        return sliced, x_idx

    @staticmethod
    def _fill(series: QLineSeries, y_vals: List[float],
              x_vals: Optional[List[float]] = None):
        if x_vals is None:
            pts = [QPointF(i, v) for i, v in enumerate(y_vals)]
        else:
            pts = [QPointF(x, v) for x, v in zip(x_vals, y_vals)]
        series.replace(pts)

    @staticmethod
    def _fit_y_axis(axis: QValueAxis, *profiles: List[float]):
        all_v = [v for p in profiles for v in p]
        if not all_v:
            return
        lo, hi = min(all_v), max(all_v)
        pad = (hi - lo) * 0.05 if hi != lo else 1.0
        axis.setRange(lo - pad, hi + pad)

    @staticmethod
    def _fit_x_axis(axis: QValueAxis, vals: List[float]):
        if vals:
            axis.setRange(min(vals), max(vals))

    @staticmethod
    def _update_stats(label: "QLabel", values: List[float]):
        if not values:
            label.setText("Mean: —   Std: —   Min: —   Max: —")
            return
        arr = np.array(values, dtype=np.float64)
        label.setText(
            f"Mean: {arr.mean():.2f}   "
            f"Std: {arr.std():.2f}   "
            f"Min: {arr.min():.2f}   "
            f"Max: {arr.max():.2f}"
        )

    def _update_mm_chart_titles(self):
        suffix = "" if self._pixel_spacing is not None else " (spacing N/A)"
        self._hc_mm.setTitle(f"Horizontal Profile{suffix}")
        self._vc_mm.setTitle(f"Vertical Profile{suffix}")

    def _apply_chart_theme(self, light: bool):
        """Switch all charts between dark (default) and light mode."""
        if light:
            bg         = QColor(255, 255, 255)
            plot_bg    = QColor(245, 245, 245)
            text_color = QColor(20,  20,  20)
            grid_color = QColor(200, 200, 200)
            live_color = QColor(0,   110, 180)
        else:
            bg         = QColor(0,   0,   0)
            plot_bg    = QColor(0,   0,   0)
            text_color = QColor(255, 255, 255)
            grid_color = Qt.darkGray
            live_color = QColor(0,   210, 210)

        chart_axes = [
            (self._hc_px, self._hc_ax_px, self._hc_ay_px),
            (self._hc_mm, self._hc_ax_mm, self._hc_ay_mm),
            (self._vc_px, self._vc_ax_px, self._vc_ay_px),
            (self._vc_mm, self._vc_ax_mm, self._vc_ay_mm),
        ]
        for chart, ax, ay in chart_axes:
            chart.setBackgroundBrush(bg)
            chart.setPlotAreaBackgroundBrush(plot_bg)
            chart.setTitleBrush(text_color)
            chart.legend().setLabelColor(text_color)
            for axis in (ax, ay):
                axis.setLabelsColor(text_color)
                axis.setTitleBrush(text_color)
                axis.setGridLineColor(grid_color)
                axis.setLinePenColor(text_color)

        for s in (self._h_live_px, self._h_live_mm,
                  self._v_live_px, self._v_live_mm):
            pen = s.pen()
            pen.setColor(live_color)
            s.setPen(pen)

        # Update stats bar styling to match theme
        if light:
            stats_style = ("color:#333333; font-size:10px; padding:2px 4px;"
                           "background:#f0f0f0; border-top:1px solid #ccc;")
        else:
            stats_style = ("color:#aaaaaa; font-size:10px; padding:2px 4px;"
                           "background:#111111; border-top:1px solid #333;")
        for lbl in (self._h_stats_px, self._h_stats_mm,
                    self._v_stats_px, self._v_stats_mm):
            lbl.setStyleSheet(stats_style)

    def _on_all_meas_toggled(self, show_all: bool):
        self._show_all_meas = show_all
        self._rerender_all_saved_series()
        self._refresh_live()

    def _on_theme_toggled(self, light: bool):
        self._light_mode = light
        self._apply_chart_theme(light)

    def _on_show_meas_toggled(self, show: bool):
        self._update_image_crosshairs()

    def _is_meas_visible(self, meas: Dict) -> bool:
        """True if this measurement should appear in the charts."""
        if self._show_all_meas:
            return True
        mp = meas.get("image_path")
        return not mp or mp == self._current_path

    def _update_image_crosshairs(self):
        """Sync saved-measurement crosshairs into the image widget.
        Only measurements whose image_path matches the current image are shown.
        Measurements without a stored path are always included (legacy data).
        """
        crosshairs = [
            (m["x"], m["y"], QColor(m["color"]))
            for m in self._measurements
            if not m.get("image_path") or m["image_path"] == self._current_path
        ]
        show = self._show_meas_check.isChecked()
        self._img.set_measurement_crosshairs(crosshairs, show)

    # ══════════════════════════════════════════════════════ refresh / render

    def _refresh_live(self):
        x, y = self._x_spin.value(), self._y_spin.value()
        hp_raw = self._h_profile(y)
        vp_raw = self._v_profile(x)
        cf = self._chunk_factor
        y_label = "HU" if self._has_hu else "Value"

        h_from = self._h_slider.low
        h_to   = self._h_slider.high
        v_from = self._v_slider.low
        v_to   = self._v_slider.high

        hp_ranged, h_xi = self._apply_range(hp_raw, h_from, h_to)
        vp_ranged, v_xi = self._apply_range(vp_raw, v_from, v_to)

        # — px charts (x = absolute column/row index) —
        h_xi_f = [float(i) for i in h_xi]
        v_xi_f = [float(i) for i in v_xi]
        hp, h_xi_c = self._apply_chunk(hp_ranged, h_xi_f, cf)
        vp, v_xi_c = self._apply_chunk(vp_ranged, v_xi_f, cf)
        self._fill(self._h_live_px, hp, h_xi_c)
        self._fill(self._v_live_px, vp, v_xi_c)
        if hp:
            self._fit_x_axis(self._hc_ax_px, h_xi_c or h_xi_f or [0])
            self._hc_ay_px.setTitleText(y_label)
        if vp:
            self._fit_x_axis(self._vc_ax_px, v_xi_c or v_xi_f or [0])
            self._vc_ay_px.setTitleText(y_label)

        # — mm charts —
        h_xmm_r = ([i * self._pixel_spacing[1] for i in h_xi]
                    if self._pixel_spacing and h_xi else None)
        v_xmm_r = ([i * self._pixel_spacing[0] for i in v_xi]
                    if self._pixel_spacing and v_xi else None)
        hp_mm, h_xmm = self._apply_chunk(hp_ranged, h_xmm_r, cf)
        vp_mm, v_xmm = self._apply_chunk(vp_ranged, v_xmm_r, cf)
        self._fill(self._h_live_mm, hp_mm, h_xmm)
        self._fill(self._v_live_mm, vp_mm, v_xmm)
        if h_xmm:
            self._fit_x_axis(self._hc_ax_mm, h_xmm)
            self._hc_ay_mm.setTitleText(y_label)
        if v_xmm:
            self._fit_x_axis(self._vc_ax_mm, v_xmm)
            self._vc_ay_mm.setTitleText(y_label)

        # — fit Y axes across live + all saved (range + chunk applied) —
        def _rc(raw, f, t):
            sl, _ = self._apply_range(raw, f, t)
            cy, _ = self._apply_chunk(sl, None, cf)
            return cy

        saved_h = [_rc(m["h_profile"], h_from, h_to)
                   for m in self._measurements if self._is_meas_visible(m)]
        saved_v = [_rc(m["v_profile"], v_from, v_to)
                   for m in self._measurements if self._is_meas_visible(m)]
        self._fit_y_axis(self._hc_ay_px, hp, *saved_h)
        self._fit_y_axis(self._vc_ay_px, vp, *saved_v)
        self._fit_y_axis(self._hc_ay_mm, hp_mm, *saved_h)
        self._fit_y_axis(self._vc_ay_mm, vp_mm, *saved_v)

        # — stats bars (live, post-range, post-chunk) —
        self._update_stats(self._h_stats_px, hp)
        self._update_stats(self._h_stats_mm, hp_mm)
        self._update_stats(self._v_stats_px, vp)
        self._update_stats(self._v_stats_mm, vp_mm)

    def _rerender_all_saved_series(self):
        """Refill every saved series — called when chunk factor or range changes."""
        cf = self._chunk_factor
        h_from = self._h_slider.low
        h_to   = self._h_slider.high
        v_from = self._v_slider.low
        v_to   = self._v_slider.high

        for meas in self._measurements:
            mid = meas["id"]
            if mid not in self._series_map:
                continue
            h_px, h_mm, v_px, v_mm = self._series_map[mid]

            if not self._is_meas_visible(meas):
                for s in (h_px, h_mm, v_px, v_mm):
                    s.clear()
                continue

            hp_raw = meas["h_profile"]
            vp_raw = meas["v_profile"]
            ps = meas.get("pixel_spacing")

            hp_r, h_xi = self._apply_range(hp_raw, h_from, h_to)
            vp_r, v_xi = self._apply_range(vp_raw, v_from, v_to)

            h_xi_f = [float(i) for i in h_xi]
            v_xi_f = [float(i) for i in v_xi]
            hp, h_xi_c = self._apply_chunk(hp_r, h_xi_f, cf)
            vp, v_xi_c = self._apply_chunk(vp_r, v_xi_f, cf)
            self._fill(h_px, hp, h_xi_c)
            self._fill(v_px, vp, v_xi_c)

            if ps and len(ps) >= 2 and h_xi and v_xi:
                h_xmm_r = [i * ps[1] for i in h_xi]
                v_xmm_r = [i * ps[0] for i in v_xi]
                hp_mm_v, h_xmm = self._apply_chunk(hp_r, h_xmm_r, cf)
                vp_mm_v, v_xmm = self._apply_chunk(vp_r, v_xmm_r, cf)
                self._fill(h_mm, hp_mm_v, h_xmm)
                self._fill(v_mm, vp_mm_v, v_xmm)
            else:
                h_mm.clear()
                v_mm.clear()

    # ══════════════════════════════════════════════════════ public API

    def set_dataset(self, ds, slope: float = 1.0, intercept: float = 0.0):
        if ds is None:
            self._pixel_array = None
            self._img.set_image(None)
            for s in (self._h_live_px, self._h_live_mm,
                      self._v_live_px, self._v_live_mm):
                s.clear()
            return

        try:
            if hasattr(ds, 'PixelData'):
                arr = ds.pixel_array
                self._pixel_array = arr[0] if arr.ndim == 3 else arr
            else:
                self._pixel_array = None
        except Exception:
            self._pixel_array = None

        self._slope = slope
        self._intercept = intercept
        self._has_hu = (slope != 1.0 or intercept != 0.0)

        ps = getattr(ds, 'PixelSpacing', None) or getattr(ds, 'ImagerPixelSpacing', None)
        self._pixel_spacing = (float(ps[0]), float(ps[1])) if ps and len(ps) >= 2 else None

        try:
            self._kvp = float(ds.KVP) if hasattr(ds, 'KVP') else None
        except Exception:
            self._kvp = None

        try:
            ipp = getattr(ds, 'ImagePositionPatient', None)
            self._z = float(ipp[2]) if ipp and len(ipp) >= 3 else None
        except Exception:
            self._z = None

        self._update_mm_chart_titles()

        if self._pixel_array is not None:
            h, w = self._pixel_array.shape[:2]
            self._x_spin.blockSignals(True)
            self._y_spin.blockSignals(True)
            self._x_spin.setRange(0, w - 1)
            self._y_spin.setRange(0, h - 1)
            cx, cy = w // 2, h // 2
            self._x_spin.setValue(cx)
            self._y_spin.setValue(cy)
            self._x_spin.blockSignals(False)
            self._y_spin.blockSignals(False)
            self._img.set_crosshair(cx, cy)

            for sl in (self._h_slider, self._v_slider):
                sl.blockSignals(True)
            self._h_slider.set_range(0, w - 1)
            self._v_slider.set_range(0, h - 1)
            for sl in (self._h_slider, self._v_slider):
                sl.blockSignals(False)
            self._img.set_profile_range(0, w - 1, 0, h - 1)

        if _HAS_IMAGE_UTILS:
            try:
                self._img.set_image(dicom_to_qimage(ds))
            except Exception:
                self._img.set_image(None)

        self._refresh_live()

    def set_image_path(self, path: Optional[str]):
        self._current_path = path
        self._update_image_crosshairs()
        if not self._show_all_meas:
            self._rerender_all_saved_series()
            self._refresh_live()

    def set_navigation(self, current: int, total: int):
        self._img_spin.blockSignals(True)
        self._img_spin.setRange(1, max(total, 1))
        self._img_spin.setValue(current)
        self._img_spin.blockSignals(False)
        self._img_total_label.setText(f"/ {total}")

    def clear_image(self):
        self._pixel_array = None
        self._img.set_image(None)
        for s in (self._h_live_px, self._h_live_mm,
                  self._v_live_px, self._v_live_mm):
            s.clear()

    # ══════════════════════════════════════════════════════ slots

    def _on_image_position_changed(self, x: int, y: int):
        self._x_spin.blockSignals(True)
        self._y_spin.blockSignals(True)
        self._x_spin.setValue(x)
        self._y_spin.setValue(y)
        self._x_spin.blockSignals(False)
        self._y_spin.blockSignals(False)
        self._refresh_live()

    def _on_xy_spin_changed(self):
        self._img.set_crosshair(self._x_spin.value(), self._y_spin.value())
        self._refresh_live()

    def _on_img_spin_changed(self, value: int):
        self.image_index_changed.emit(value - 1)

    def _on_chunk_changed(self, value: int):
        self._chunk_factor = value
        self._rerender_all_saved_series()
        self._refresh_live()

    def _on_range_changed(self):
        self._img.set_profile_range(
            self._h_slider.low, self._h_slider.high,
            self._v_slider.low, self._v_slider.high)
        self._rerender_all_saved_series()
        self._refresh_live()

    def _on_reset_range(self):
        if self._pixel_array is None:
            return
        h, w = self._pixel_array.shape[:2]
        for sl in (self._h_slider, self._v_slider):
            sl.blockSignals(True)
        self._h_slider.set_range(0, w - 1)
        self._v_slider.set_range(0, h - 1)
        for sl in (self._h_slider, self._v_slider):
            sl.blockSignals(False)
        self._img.set_profile_range(
            self._h_slider.low, self._h_slider.high,
            self._v_slider.low, self._v_slider.high)
        self._rerender_all_saved_series()
        self._refresh_live()

    def _on_h_chart_hovered(self, x_val: float, is_mm: bool):
        """Highlight the column on the image corresponding to the H-chart hover."""
        if is_mm:
            if not self._pixel_spacing:
                return
            col = int(round(x_val / self._pixel_spacing[1]))
        else:
            col = int(round(x_val))
        self._img.set_hover_col(col)

    def _on_v_chart_hovered(self, x_val: float, is_mm: bool):
        """Highlight the row on the image corresponding to the V-chart hover."""
        if is_mm:
            if not self._pixel_spacing:
                return
            row = int(round(x_val / self._pixel_spacing[0]))
        else:
            row = int(round(x_val))
        self._img.set_hover_row(row)

    def _on_table_cell_clicked(self, row: int, col: int):
        """Move crosshair to the clicked measurement's position.
        If the measurement belongs to a different image, request loading it first.
        """
        if col in (_COL_COLOR, _COL_DELETE):
            return
        if row < 0 or row >= len(self._measurements):
            return
        meas = self._measurements[row]

        # If the measurement was taken on a different image, ask the main window
        # to load it.  The signal is connected synchronously, so set_dataset will
        # have been called by the time the next line executes.
        path = meas.get("image_path")
        if path and path != self._current_path:
            self.load_file_requested.emit(path)
            # set_dataset reset the crosshair to centre; we override it below.

        x, y = meas["x"], meas["y"]
        self._x_spin.blockSignals(True)
        self._y_spin.blockSignals(True)
        self._x_spin.setValue(x)
        self._y_spin.setValue(y)
        self._x_spin.blockSignals(False)
        self._y_spin.blockSignals(False)
        self._img.set_crosshair(x, y)
        self._refresh_live()

    # ══════════════════════════════════════════════════════ measure / table

    def _on_measure(self):
        if self._pixel_array is None:
            return
        x, y = self._x_spin.value(), self._y_spin.value()
        hp = self._h_profile(y)
        vp = self._v_profile(x)
        if not hp or not vp:
            return

        mid = self._next_id
        self._next_id += 1
        color = _COLORS[(mid - 1) % len(_COLORS)]
        meas: Dict[str, Any] = {
            "id": mid, "x": x, "y": y,
            "label": f"M{mid}",
            "color": color.name(),
            "h_profile": hp,
            "v_profile": vp,
            "kvp": self._kvp,
            "z": self._z,
            "pixel_spacing": list(self._pixel_spacing) if self._pixel_spacing else None,
            "image_path": self._current_path,
        }
        self._measurements.append(meas)
        self._add_series_for(meas)
        self._add_table_row(meas)
        self._update_image_crosshairs()
        self._refresh_live()

    def _add_series_for(self, meas: Dict):
        mid = meas["id"]
        color = QColor(meas["color"])
        label = meas["label"]
        hp_raw = meas["h_profile"]
        vp_raw = meas["v_profile"]
        ps = meas.get("pixel_spacing")
        cf = self._chunk_factor

        h_px = self._attach_series(self._hc_px, self._hc_ax_px, self._hc_ay_px, label, color)
        h_mm = self._attach_series(self._hc_mm, self._hc_ax_mm, self._hc_ay_mm, label, color)
        v_px = self._attach_series(self._vc_px, self._vc_ax_px, self._vc_ay_px, label, color)
        v_mm = self._attach_series(self._vc_mm, self._vc_ax_mm, self._vc_ay_mm, label, color)

        hp, _ = self._apply_chunk(hp_raw, None, cf)
        vp, _ = self._apply_chunk(vp_raw, None, cf)
        self._fill(h_px, hp)
        self._fill(v_px, vp)

        if ps and len(ps) >= 2:
            h_xmm_raw = [i * ps[1] for i in range(len(hp_raw))]
            v_xmm_raw = [i * ps[0] for i in range(len(vp_raw))]
            hp_mm, h_xmm = self._apply_chunk(hp_raw, h_xmm_raw, cf)
            vp_mm, v_xmm = self._apply_chunk(vp_raw, v_xmm_raw, cf)
            self._fill(h_mm, hp_mm, h_xmm)
            self._fill(v_mm, vp_mm, v_xmm)

        self._series_map[mid] = (h_px, h_mm, v_px, v_mm)

    def _add_table_row(self, meas: Dict):
        row = self._table.rowCount()
        self._table.insertRow(row)
        color = QColor(meas["color"])

        kvp_str     = f"{meas['kvp']:.0f} kV" if meas.get("kvp") is not None else "N/A"
        z_str       = f"{meas['z']:.2f}" if meas.get("z") is not None else "N/A"
        ps          = meas.get("pixel_spacing")
        spacing_str = f"{ps[0]:.3f} × {ps[1]:.3f}" if ps else "N/A"

        for col, text in [(_COL_LABEL,   meas["label"]),
                           (_COL_X,       str(meas["x"])),
                           (_COL_Y,       str(meas["y"])),
                           (_COL_Z,       z_str),
                           (_COL_KVP,     kvp_str),
                           (_COL_SPACING, spacing_str)]:
            item = QTableWidgetItem(text)
            item.setForeground(color)
            self._table.setItem(row, col, item)

        color_btn = QPushButton()
        color_btn.setToolTip("Click to change color")
        self._apply_color_btn_style(color_btn, color)
        mid = meas["id"]
        color_btn.clicked.connect(lambda _, m=mid: self._change_color(m))
        self._table.setCellWidget(row, _COL_COLOR, color_btn)

        del_btn = QPushButton("✕")
        del_btn.setMaximumWidth(36)
        del_btn.clicked.connect(lambda _, m=mid: self._delete_measurement(m))
        self._table.setCellWidget(row, _COL_DELETE, del_btn)

    @staticmethod
    def _apply_color_btn_style(btn: QPushButton, color: QColor):
        luma = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
        fg = "#000" if luma > 128 else "#fff"
        btn.setStyleSheet(
            f"background:{color.name()}; color:{fg}; border:1px solid #888;")

    def _change_color(self, mid: int):
        meas = next((m for m in self._measurements if m["id"] == mid), None)
        if not meas:
            return
        new_color = QColorDialog.getColor(
            QColor(meas["color"]), self, "Measurement Color")
        if not new_color.isValid():
            return
        meas["color"] = new_color.name()
        if mid in self._series_map:
            for s in self._series_map[mid]:
                pen = s.pen()
                pen.setColor(new_color)
                s.setPen(pen)
        self._rebuild_table()

    def _delete_measurement(self, mid: int):
        self._measurements = [m for m in self._measurements if m["id"] != mid]
        if mid in self._series_map:
            all_charts = (self._hc_px, self._hc_mm, self._vc_px, self._vc_mm)
            for s in self._series_map.pop(mid):
                for chart in all_charts:
                    if s in chart.series():
                        chart.removeSeries(s)
                        break
        self._rebuild_table()
        self._refresh_live()

    def _rebuild_table(self):
        self._table.setRowCount(0)
        for meas in self._measurements:
            self._add_table_row(meas)
        self._update_image_crosshairs()

    # ══════════════════════════════════════════════════════ chart export

    def _active_chart_views(self) -> Tuple[QChartView, QChartView]:
        """Return the currently visible (H, V) chart views."""
        h_idx = self._h_chart_tabs.currentIndex()
        v_idx = self._v_chart_tabs.currentIndex()
        h_cv = self._h_cv_px if h_idx == 0 else self._h_cv_mm
        v_cv = self._v_cv_px if v_idx == 0 else self._v_cv_mm
        return h_cv, v_cv

    @staticmethod
    def _grab_chart(cv: QChartView, fallback_size: QSize = QSize(800, 400)) -> QPixmap:
        pm = cv.grab()
        if pm.isNull() or pm.width() < 10:
            pm = QPixmap(fallback_size)
            pm.fill(Qt.black)
            p = QPainter(pm)
            cv.render(p)
            p.end()
        return pm

    def _on_export_image(self):
        ts = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Image with Crosshairs",
            f"image_{ts}.png", "PNG Files (*.png)")
        if not path:
            return
        self._img.grab_with_crosshairs().save(path, "PNG")

    def _on_export_charts_separate(self):
        ts = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
        dir_path = QFileDialog.getExistingDirectory(
            self, "Export Charts (Separate) — Choose Directory")
        if not dir_path:
            return
        h_cv, v_cv = self._active_chart_views()
        self._grab_chart(h_cv).save(f"{dir_path}/h_profile_{ts}.png", "PNG")
        self._grab_chart(v_cv).save(f"{dir_path}/v_profile_{ts}.png", "PNG")

    def _on_export_charts_sidebyside(self):
        ts = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Charts Side-by-Side",
            f"profiles_{ts}.png", "PNG Files (*.png)")
        if not path:
            return
        h_cv, v_cv = self._active_chart_views()
        h_img = self._grab_chart(h_cv).toImage()
        v_img = self._grab_chart(v_cv).toImage()
        combined = QImage(h_img.width() + v_img.width(),
                          max(h_img.height(), v_img.height()),
                          QImage.Format_ARGB32)
        combined.fill(Qt.black)
        p = QPainter(combined)
        p.drawImage(0, 0, h_img)
        p.drawImage(h_img.width(), 0, v_img)
        p.end()
        combined.save(path, "PNG")

    # ══════════════════════════════════════════════════════ JSON export / import

    def _on_export_json(self):
        if not self._measurements:
            return
        ts = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Profile Measurements",
            f"profile_measurements_{ts}.json", "JSON Files (*.json)")
        if not path:
            return
        with open(path, "w") as f:
            json.dump(self._measurements, f, indent=2, default=str)

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Profile Measurements", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception as e:
            print(f"Failed to import profile measurements: {e}")
            return

        for entry in data:
            try:
                x = int(entry["x"])
                y = int(entry["y"])
                hp = [float(v) for v in entry["h_profile"]]
                vp = [float(v) for v in entry["v_profile"]]
                label = str(entry.get("label", f"M{self._next_id}"))
                color = QColor(str(entry.get("color", _COLORS[0].name())))
                if not color.isValid():
                    color = _COLORS[(self._next_id - 1) % len(_COLORS)]
                kvp    = float(entry["kvp"]) if entry.get("kvp") is not None else None
                z      = float(entry["z"])   if entry.get("z")   is not None else None
                ps_raw = entry.get("pixel_spacing")
                ps = [float(ps_raw[0]), float(ps_raw[1])] if ps_raw else None
            except (KeyError, ValueError, TypeError):
                continue

            image_path = entry.get("image_path") or None
            mid = self._next_id
            self._next_id += 1
            meas: Dict[str, Any] = {
                "id": mid, "x": x, "y": y,
                "label": label, "color": color.name(),
                "h_profile": hp, "v_profile": vp,
                "kvp": kvp, "z": z, "pixel_spacing": ps,
                "image_path": image_path,
            }
            self._measurements.append(meas)
            self._add_series_for(meas)
            self._add_table_row(meas)

        self._update_image_crosshairs()
        self._rerender_all_saved_series()
        self._refresh_live()
