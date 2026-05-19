#!/usr/bin/env python3
"""
RangeSliderWidget — a two-handle range selector (horizontal or vertical).

Drag either handle to adjust the low / high boundary.
Mouse-wheel over the track nudges the nearest handle by 1.
"""

from PySide6.QtWidgets import QWidget, QSizePolicy, QToolTip
from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont


class RangeSliderWidget(QWidget):
    """
    Emits range_changed(low: int, high: int) whenever either handle moves.

    Public API
    ----------
    set_range(min_val, max_val)  — set the allowed extent (resets low/high)
    set_values(low, high)        — programmatically position the handles
    low  /  high                 — current integer values (read-only properties)
    """

    range_changed = Signal(int, int)

    _TRACK_THICK   = 5   # thickness of the track bar
    _MARGIN        = 10  # inset at each end of the track
    _HANDLE_ALONG  = 12  # handle size in the track direction
    _HANDLE_ACROSS = 22  # handle size perpendicular to the track

    def __init__(self, orientation=Qt.Horizontal, parent=None):
        super().__init__(parent)
        self._ori  = orientation
        self._min  = 0
        self._max  = 100
        self._low  = 0
        self._high = 100
        self._drag : str | None = None   # 'low' | 'high'
        self._hover: str | None = None

        if orientation == Qt.Vertical:
            self.setFixedWidth(32)
            self.setMinimumHeight(100)
            self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        else:
            self.setMinimumHeight(34)
            self.setMinimumWidth(100)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.setMouseTracking(True)

    # ── public API ─────────────────────────────────────────────────────────────

    def set_range(self, min_val: int, max_val: int):
        self._min  = min_val
        self._max  = max(min_val, max_val)
        self._low  = self._min
        self._high = self._max
        self.update()

    def set_values(self, low: int, high: int):
        self._low  = max(self._min, min(self._max, low))
        self._high = max(self._min, min(self._max, high))
        if self._low > self._high:
            self._high = self._low
        self.update()

    @property
    def low(self) -> int:
        return self._low

    @property
    def high(self) -> int:
        return self._high

    # ── coordinate helpers ─────────────────────────────────────────────────────

    def _track_len(self) -> int:
        if self._ori == Qt.Horizontal:
            return max(1, self.width()  - 2 * self._MARGIN)
        else:
            return max(1, self.height() - 2 * self._MARGIN)

    def _val_to_pos(self, val: int) -> int:
        span = self._max - self._min
        if span == 0:
            return self._MARGIN
        return self._MARGIN + int((val - self._min) / span * self._track_len())

    def _pos_to_val(self, pos: float) -> int:
        span = self._max - self._min
        if span == 0:
            return self._min
        frac = max(0.0, min(1.0, (pos - self._MARGIN) / self._track_len()))
        return self._min + int(round(frac * span))

    def _event_coord(self, pos) -> float:
        return pos.x() if self._ori == Qt.Horizontal else pos.y()

    def _cross_center(self) -> int:
        """Center coordinate perpendicular to the track."""
        if self._ori == Qt.Horizontal:
            return self.height() // 2
        else:
            return self.width() // 2

    def _handle_rect(self, val: int) -> QRect:
        p   = self._val_to_pos(val)
        ctr = self._cross_center()
        ha, hb = self._HANDLE_ALONG // 2, self._HANDLE_ACROSS // 2
        if self._ori == Qt.Horizontal:
            return QRect(p - ha, ctr - hb, self._HANDLE_ALONG, self._HANDLE_ACROSS)
        else:
            return QRect(ctr - hb, p - ha, self._HANDLE_ACROSS, self._HANDLE_ALONG)

    def _nearest_handle(self, coord: float) -> str:
        dl = abs(coord - self._val_to_pos(self._low))
        dh = abs(coord - self._val_to_pos(self._high))
        return 'low' if dl <= dh else 'high'

    # ── paint ──────────────────────────────────────────────────────────────────

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        ctr  = self._cross_center()
        lp   = self._val_to_pos(self._low)
        hp   = self._val_to_pos(self._high)
        half = self._TRACK_THICK // 2

        # ── track background ──────────────────────────────────────────────
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(55, 55, 65))
        if self._ori == Qt.Horizontal:
            p.drawRoundedRect(self._MARGIN, ctr - half,
                              self._track_len(), self._TRACK_THICK, 3, 3)
        else:
            p.drawRoundedRect(ctr - half, self._MARGIN,
                              self._TRACK_THICK, self._track_len(), 3, 3)

        # ── active region ─────────────────────────────────────────────────
        if hp > lp:
            p.setBrush(QColor(0, 160, 200))
            if self._ori == Qt.Horizontal:
                p.drawRoundedRect(lp, ctr - half, hp - lp, self._TRACK_THICK, 2, 2)
            else:
                p.drawRoundedRect(ctr - half, lp, self._TRACK_THICK, hp - lp, 2, 2)

        # ── handles ───────────────────────────────────────────────────────
        for which, val in (('low', self._low), ('high', self._high)):
            rect   = self._handle_rect(val)
            active = (self._drag == which or self._hover == which)
            fill   = QColor(220, 220, 230) if active else QColor(180, 180, 195)
            border = QColor(80, 130, 180)  if active else QColor(110, 110, 130)
            p.setBrush(QBrush(fill))
            p.setPen(QPen(border, 1))
            p.drawRoundedRect(rect, 3, 3)

            # grip lines (3 parallel lines across the handle)
            rcx, rcy = rect.center().x(), rect.center().y()
            p.setPen(QPen(border, 1))
            if self._ori == Qt.Horizontal:
                for dy in (-3, 0, 3):
                    p.drawLine(rcx - 2, rcy + dy, rcx + 2, rcy + dy)
            else:
                for dx in (-3, 0, 3):
                    p.drawLine(rcx + dx, rcy - 2, rcx + dx, rcy + 2)

        # ── numeric labels (horizontal only — vertical is too narrow) ─────
        if self._ori == Qt.Horizontal:
            font = QFont()
            font.setPixelSize(9)
            p.setFont(font)
            fm   = p.fontMetrics()
            p.setPen(QColor(160, 160, 175))
            lo_s, hi_s = str(self._low), str(self._high)
            lo_w, hi_w = fm.horizontalAdvance(lo_s), fm.horizontalAdvance(hi_s)
            label_y    = ctr - self._HANDLE_ACROSS // 2 - 1
            lo_lx = max(self._MARGIN, lp - lo_w // 2)
            hi_lx = min(self.width() - self._MARGIN - hi_w, hp - hi_w // 2)
            if lo_lx + lo_w + 3 > hi_lx:
                lo_lx = hi_lx - lo_w - 4
            p.drawText(lo_lx, label_y, lo_s)
            p.drawText(hi_lx, label_y, hi_s)

    # ── mouse events ──────────────────────────────────────────────────────────

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        coord = self._event_coord(e.position())
        self._drag = self._nearest_handle(coord)
        self._apply_drag(coord)

    def mouseMoveEvent(self, e):
        coord = self._event_coord(e.position())
        if self._drag:
            self._apply_drag(coord)
        else:
            prev = self._hover
            self._hover = self._nearest_handle(coord)
            if self._hover != prev:
                self.update()
            self.setCursor(Qt.SizeHorCursor if self._ori == Qt.Horizontal
                           else Qt.SizeVerCursor)

    def mouseReleaseEvent(self, _e):
        self._drag = None
        self.update()

    def leaveEvent(self, _e):
        self._hover = None
        self.update()

    def wheelEvent(self, e):
        delta = 1 if e.angleDelta().y() > 0 else -1
        which = self._nearest_handle(self._event_coord(e.position()))
        if which == 'low':
            self._low  = max(self._min, min(self._high, self._low  + delta))
        else:
            self._high = max(self._low,  min(self._max,  self._high + delta))
        self._emit_and_tooltip()

    def _apply_drag(self, coord: float):
        val = max(self._min, min(self._max, self._pos_to_val(coord)))
        if self._drag == 'low':
            self._low  = min(val, self._high)
        else:
            self._high = max(val, self._low)
        self._emit_and_tooltip()

    def _emit_and_tooltip(self):
        self.update()
        self.range_changed.emit(self._low, self._high)
        QToolTip.showText(
            self.mapToGlobal(self.rect().center()),
            f"{self._low} – {self._high}", self)
