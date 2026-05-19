#!/usr/bin/env python3
"""
Stack Position Widget

Draws an isometric 3D representation of a DICOM image stack, highlighting
the currently active slice.
"""

from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QPolygonF, QBrush, QFont


class StackPositionWidget(QWidget):
    """
    Paints an isometric stack-of-slices graphic with the active slice highlighted.

    The stack is drawn as a 3D cuboid viewed from an isometric angle:
      - Front face:  shows all slices as thin horizontal bands; active slice is cyan
      - Right face:  darker shading for depth
      - Top face:    lighter shading for depth

    Call set_stack(total) when the series changes and set_current(index) (0-based)
    whenever the active image changes.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._total: int = 0
        self._current: int = 0  # 0-based index; slice 0 = bottom of stack
        self.setMinimumHeight(150)
        self.setMaximumHeight(220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_stack(self, total: int):
        self._total = max(total, 0)
        self.update()

    def set_current(self, index: int):
        """index is 1-based (matches navigation spinbox)."""
        self._current = max(0, index - 1)
        self.update()

    # ------------------------------------------------------------------ paint

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self._draw(painter)

    def _draw(self, painter: QPainter):
        if self._total <= 0:
            painter.setPen(QColor(120, 120, 120))
            painter.drawText(self.rect(), Qt.AlignCenter, "No series loaded")
            return

        w = self.width()
        h = self.height()

        # ── geometry ──────────────────────────────────────────────────────
        # Isometric offsets (depth projection)
        depth_x = int(w * 0.18)
        depth_y = int(h * 0.12)

        # Front face rectangle (bottom-left anchor)
        margin = 12
        front_x = margin
        front_y = margin + depth_y                    # leave room for top face
        front_w = w - margin * 2 - depth_x
        front_h = h - margin * 2 - depth_y - 24       # leave room for label

        if front_w < 10 or front_h < 10:
            return

        # Corners of the front face
        fl = front_x
        ft = front_y
        fr = front_x + front_w
        fb = front_y + front_h

        # ── colours ───────────────────────────────────────────────────────
        col_front_bg   = QColor(45, 45, 55)
        col_front_line = QColor(70, 70, 85)
        col_right      = QColor(30, 30, 40)
        col_top        = QColor(65, 65, 80)
        col_outline    = QColor(100, 100, 120)
        col_active     = QColor(0, 210, 210)          # cyan highlight
        col_active_r   = QColor(0, 140, 140)          # darker right face
        col_label      = QColor(200, 200, 210)
        col_count      = QColor(130, 130, 150)

        # ── right face ────────────────────────────────────────────────────
        right_poly = QPolygonF([
            QPointF(fr,           ft),
            QPointF(fr + depth_x, ft - depth_y),
            QPointF(fr + depth_x, fb - depth_y),
            QPointF(fr,           fb),
        ])
        painter.setBrush(QBrush(col_right))
        painter.setPen(QPen(col_outline, 1))
        painter.drawPolygon(right_poly)

        # ── top face ──────────────────────────────────────────────────────
        top_poly = QPolygonF([
            QPointF(fl,           ft),
            QPointF(fl + depth_x, ft - depth_y),
            QPointF(fr + depth_x, ft - depth_y),
            QPointF(fr,           ft),
        ])
        painter.setBrush(QBrush(col_top))
        painter.setPen(QPen(col_outline, 1))
        painter.drawPolygon(top_poly)

        # ── front face background ─────────────────────────────────────────
        painter.setBrush(QBrush(col_front_bg))
        painter.setPen(QPen(col_outline, 1))
        painter.drawRect(fl, ft, front_w, front_h)

        # ── slice lines on front face ─────────────────────────────────────
        # Draw at most ~60 visible bands; group slices into bands if N > 60
        max_bands = min(self._total, 60)
        band_h = front_h / max_bands

        # Which band does the active slice fall in?
        # Slice 0 = bottom of stack visually (first slice at bottom)
        active_band = int(self._current / self._total * max_bands) if self._total > 1 else 0
        active_band = min(active_band, max_bands - 1)

        for band in range(max_bands):
            # Band 0 is at the bottom (highest y value)
            band_top    = ft + front_h - (band + 1) * band_h
            band_bottom = ft + front_h - band * band_h

            if band == active_band:
                # Highlight active band on front face
                painter.setBrush(QBrush(col_active))
                painter.setPen(Qt.NoPen)
                painter.drawRect(
                    int(fl + 1), int(band_top + 1),
                    int(front_w - 2), max(int(band_bottom - band_top - 1), 1)
                )

                # Extend highlight onto right face
                active_proj_top = QPolygonF([
                    QPointF(fr,           band_top),
                    QPointF(fr + depth_x, band_top - depth_y),
                    QPointF(fr + depth_x, band_bottom - depth_y),
                    QPointF(fr,           band_bottom),
                ])
                painter.setBrush(QBrush(col_active_r))
                painter.setPen(Qt.NoPen)
                painter.drawPolygon(active_proj_top)
            else:
                # Thin separator line
                painter.setPen(QPen(col_front_line, 1))
                y = int(ft + front_h - band * band_h)
                painter.drawLine(fl + 1, y, fr - 1, y)

        # ── front face outline (redraw on top) ────────────────────────────
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(col_outline, 1))
        painter.drawRect(fl, ft, front_w, front_h)

        # ── label: "Slice X / N" ──────────────────────────────────────────
        font = QFont()
        font.setPixelSize(11)
        painter.setFont(font)

        painter.setPen(QPen(col_label))
        slice_text = f"Slice {self._current + 1}"
        painter.drawText(fl, fb + 18, slice_text)

        painter.setPen(QPen(col_count))
        total_text = f"/ {self._total}"
        fm = painter.fontMetrics()
        painter.drawText(fr - fm.horizontalAdvance(total_text), fb + 18, total_text)
