#!/usr/bin/env python3
"""
Comparison Window for DICOM Data Extraction Helper GUI

Allows comparing multiple measurement curves in a single view.
"""

from typing import Optional, List, Dict, Any, Tuple
import numpy as np

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QSpinBox, QColorDialog, QFrame, QSizePolicy, QFileDialog,
    QTabWidget, QComboBox,
)
from PySide6.QtCore import Qt, Signal, QDateTime
from PySide6.QtGui import QColor, QPixmap, QImage, QPainter, QPen, QBrush
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis, QSplineSeries
from gui.utils.image_utils import dicom_to_qimage


class MeasurementToggle(QWidget):
    """Widget for toggling a measurement with row offset and color picker."""

    color_changed = Signal(int, QColor)  # measurement index, new color
    row_changed = Signal(int, int)       # measurement index, new row
    toggled = Signal(int, bool)          # measurement index, enabled state

    def __init__(self, index: int, color: QColor = QColor(Qt.red), row: int = 0, parent=None):
        super().__init__(parent)
        self._index = index
        self._color = color
        self._row = row

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._checkbox = QCheckBox(f"Measurement {index + 1}")
        self._checkbox.setChecked(True)
        self._checkbox.stateChanged.connect(self._on_toggled)
        layout.addWidget(self._checkbox)

        self._row_spin = QSpinBox()
        self._row_spin.setRange(0, 1000)
        self._row_spin.setValue(row)
        self._row_spin.setToolTip("Row offset within measurement window")
        self._row_spin.valueChanged.connect(self._on_row_changed)
        layout.addWidget(self._row_spin)

        self._color_button = QPushButton()
        self._color_button.setFixedSize(24, 24)
        self._color_button.setStyleSheet(f"background-color: {color.name()}; border: 1px solid black;")
        self._color_button.setToolTip("Pick color for measurement overlay")
        self._color_button.clicked.connect(self._on_color_picked)
        layout.addWidget(self._color_button)

    def _on_toggled(self, state: int):
        self.toggled.emit(self._index, bool(state))

    def _on_row_changed(self, value: int):
        self._row = value
        self.row_changed.emit(self._index, value)

    def _on_color_picked(self):
        color = QColorDialog.getColor(self._color, self, "Pick Measurement Color")
        if color.isValid():
            self._color = color
            self._color_button.setStyleSheet(f"background-color: {color.name()}; border: 1px solid black;")
            self.color_changed.emit(self._index, color)

    def set_color(self, color: QColor):
        self._color = color
        self._color_button.setStyleSheet(f"background-color: {color.name()}; border: 1px solid black;")

    def set_row(self, row: int):
        self._row = row
        self._row_spin.setValue(row)

    def set_checked(self, checked: bool):
        self._checkbox.setChecked(checked)

    def is_checked(self) -> bool:
        return self._checkbox.isChecked()

    def get_color(self) -> QColor:
        return self._color

    def get_row(self) -> int:
        return self._row


class ComparisonWindow(QDialog):
    """
    Window for comparing measurement curves.

    Layout:
      [Image: <dropdown>]                        ← image selector
      [========= QTabWidget ================]
        Tab 1 – Overview : image left + chart right
        Tab 2 – Curve    : full-width chart
        Tab 3 – Image    : full-width image
      [toggle1] [toggle2] … [Export PNG]         ← always visible
    """

    def __init__(self, measurements: List[Dict[str, Any]],
                 dataset=None,
                 image_files=None,
                 parent=None):
        super().__init__(parent)

        self._measurements = measurements
        self._image_files = image_files or []

        # Build image-name → dataset lookup from the supplied file list
        self._image_dataset_map: Dict[str, Any] = {}
        for f in self._image_files:
            if f.dataset is not None:
                self._image_dataset_map[f.filepath.name] = f.dataset

        # Collect unique image names from measurements (insertion order)
        seen: set = set()
        self._image_names: List[str] = []
        for m in measurements:
            name = m.get('image_name', '')
            if name and name not in seen:
                seen.add(name)
                self._image_names.append(name)
        if not self._image_names:
            self._image_names = ['(unknown)']

        # Default selection: match the passed dataset, fall back to first entry
        self._current_image_name: str = self._image_names[0]
        if dataset is not None:
            for name, ds in self._image_dataset_map.items():
                if ds is dataset and name in self._image_names:
                    self._current_image_name = name
                    break

        self._dataset = self._image_dataset_map.get(self._current_image_name, dataset)

        # Per-measurement UI state (color, row offset, enabled)
        self._measurement_states: List[Dict[str, Any]] = []
        default_colors = [
            QColor(Qt.red), QColor(Qt.green), QColor(Qt.blue), QColor(Qt.cyan),
            QColor(Qt.magenta), QColor(Qt.yellow), QColor(Qt.darkRed), QColor(Qt.darkGreen),
            QColor(Qt.darkBlue), QColor(Qt.darkCyan),
        ]
        for i in range(len(measurements)):
            self._measurement_states.append({
                'enabled': True,
                'color': default_colors[i % len(default_colors)],
                'row_offset': 0,
            })

        self.setWindowTitle("Compare Measurement Curves")
        self.setMinimumSize(800, 600)
        
        # Theme mode (default: dark)
        self._dark_mode: bool = True

        self._setup_ui()
        self._setup_connections()

        self._update_toggle_visibility()
        self._update_image_display()
        self._update_curve_display()

    # ── helpers ───────────────────────────────────────────────────────

    def _measurements_for_current_image(self) -> List[Tuple[int, Dict[str, Any]]]:
        """Return (original_index, measurement) pairs belonging to the selected image."""
        return [
            (i, m) for i, m in enumerate(self._measurements)
            if m.get('image_name', '') == self._current_image_name
        ]

    @staticmethod
    def _create_chart() -> QChart:
        chart = QChart()
        chart.setTitle("Combined Measurement Curves")
        chart.legend().hide()
        chart.setAnimationOptions(QChart.SeriesAnimations)
        return chart

    # ── UI construction ───────────────────────────────────────────────

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # ── Image selector row (above tabs) ───────────────────────────
        selector_layout = QHBoxLayout()
        selector_layout.setContentsMargins(0, 0, 0, 0)
        selector_layout.setSpacing(6)
        selector_layout.addWidget(QLabel("Image:"))
        self._image_combo = QComboBox()
        for name in self._image_names:
            self._image_combo.addItem(name)
        idx = self._image_names.index(self._current_image_name)
        self._image_combo.setCurrentIndex(idx)
        self._image_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._image_combo.currentIndexChanged.connect(self._on_image_selected)
        selector_layout.addWidget(self._image_combo)
        main_layout.addLayout(selector_layout, 0)

        # ── Tab widget ────────────────────────────────────────────────
        self._tab_widget = QTabWidget()

        # Tab 1: Overview
        tab1 = QWidget()
        tab1_layout = QVBoxLayout(tab1)
        tab1_layout.setContentsMargins(0, 0, 0, 0)
        tab1_layout.setSpacing(4)

        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(4)

        self._image_frame = QFrame()
        self._image_frame.setFrameShape(QFrame.StyledPanel)
        self._image_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        image_layout = QVBoxLayout(self._image_frame)
        image_layout.setContentsMargins(2, 2, 2, 2)
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        image_layout.addWidget(self._image_label)
        columns_layout.addWidget(self._image_frame, 1)

        self._chart_frame = QFrame()
        self._chart_frame.setFrameShape(QFrame.StyledPanel)
        self._chart_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        chart_layout = QVBoxLayout(self._chart_frame)
        chart_layout.setContentsMargins(2, 2, 2, 2)
        self._chart = self._create_chart()
        self._chart_view = QChartView(self._chart)
        self._chart_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._chart_view.setRenderHint(QPainter.Antialiasing)
        chart_layout.addWidget(self._chart_view)
        columns_layout.addWidget(self._chart_frame, 1)

        tab1_layout.addLayout(columns_layout, 1)
        self._tab_widget.addTab(tab1, "Overview")

        # Tab 2: full-width chart
        tab2 = QWidget()
        tab2_layout = QVBoxLayout(tab2)
        tab2_layout.setContentsMargins(2, 2, 2, 2)
        self._chart_full = self._create_chart()
        self._chart_view_full = QChartView(self._chart_full)
        self._chart_view_full.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._chart_view_full.setRenderHint(QPainter.Antialiasing)
        tab2_layout.addWidget(self._chart_view_full)
        self._tab_widget.addTab(tab2, "Curve")

        # Tab 3: full-width image
        tab3 = QWidget()
        tab3_layout = QVBoxLayout(tab3)
        tab3_layout.setContentsMargins(2, 2, 2, 2)
        self._image_label_full = QLabel()
        self._image_label_full.setAlignment(Qt.AlignCenter)
        self._image_label_full.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        tab3_layout.addWidget(self._image_label_full)
        self._tab_widget.addTab(tab3, "Image")

        main_layout.addWidget(self._tab_widget, 1)

        # ── Bottom row: measurement toggles + export ──────────────────
        toggles_layout = QHBoxLayout()
        toggles_layout.setContentsMargins(0, 0, 0, 0)
        toggles_layout.setSpacing(4)

        self._toggle_widgets: List[MeasurementToggle] = []
        for i, m in enumerate(self._measurements):
            toggle = MeasurementToggle(
                i,
                color=self._measurement_states[i]['color'],
                row=self._measurement_states[i]['row_offset'],
            )
            toggle.set_checked(self._measurement_states[i]['enabled'])
            self._toggle_widgets.append(toggle)
            toggles_layout.addWidget(toggle)

        self._export_button = QPushButton("Export PNG")
        self._export_button.setToolTip("Export the active tab as PNG")
        self._export_button.clicked.connect(self._on_export_png)
        toggles_layout.addWidget(self._export_button)
        
        # Theme toggle button
        self._theme_button = QPushButton("🌓")
        self._theme_button.setToolTip("Toggle Light/Dark mode")
        self._theme_button.setFixedWidth(32)
        self._theme_button.clicked.connect(self._toggle_theme)
        toggles_layout.addWidget(self._theme_button)
        
        toggles_layout.addStretch()

        main_layout.addLayout(toggles_layout, 0)

    def _setup_connections(self):
        for i, toggle in enumerate(self._toggle_widgets):
            toggle.color_changed.connect(lambda idx, color, i=i: self._on_color_changed(i, color))
            toggle.row_changed.connect(lambda idx, row, i=i: self._on_row_changed(i, row))
            toggle.toggled.connect(lambda idx, enabled, i=i: self._on_toggle_changed(i, enabled))

    # ── Signal handlers ───────────────────────────────────────────────

    def _on_image_selected(self, combo_index: int):
        self._current_image_name = self._image_names[combo_index]
        self._dataset = self._image_dataset_map.get(self._current_image_name, None)
        self._update_toggle_visibility()
        self._update_image_display()
        self._update_curve_display()

    def _on_color_changed(self, index: int, color: QColor):
        self._measurement_states[index]['color'] = color
        self._update_image_display()
        self._update_curve_display()

    def _on_row_changed(self, index: int, row: int):
        self._measurement_states[index]['row_offset'] = row
        self._update_image_display()
        self._update_curve_display()

    def _on_toggle_changed(self, index: int, enabled: bool):
        self._measurement_states[index]['enabled'] = enabled
        self._update_image_display()
        self._update_curve_display()

    def _on_export_png(self):
        timestamp = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
        default_filename = f"comparison_{timestamp}.png"
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Comparison as PNG",
            default_filename,
            "PNG Files (*.png);;All Files (*)"
        )
        if not filepath:
            return

        tab = self._tab_widget.currentIndex()

        if tab == 0:
            image_frame_size = self._image_frame.size()
            chart_frame_size = self._chart_frame.size()
            combined_width = image_frame_size.width() + chart_frame_size.width()
            combined_height = max(image_frame_size.height(), chart_frame_size.height())
            pixmap = QPixmap(combined_width, combined_height)
            pixmap.fill(Qt.black)
            painter = QPainter(pixmap)
            if self._image_label.pixmap() and not self._image_label.pixmap().isNull():
                painter.drawPixmap(0, 0, self._image_label.pixmap())
            chart_pixmap = QPixmap(chart_frame_size)
            chart_pixmap.fill(Qt.transparent)
            chart_painter = QPainter(chart_pixmap)
            self._chart_view.render(chart_painter)
            chart_painter.end()
            painter.drawPixmap(image_frame_size.width(), 0, chart_pixmap)
            painter.end()
        elif tab == 1:
            pixmap = QPixmap(self._chart_view_full.size())
            pixmap.fill(Qt.black)
            painter = QPainter(pixmap)
            self._chart_view_full.render(painter)
            painter.end()
        else:
            if self._image_label_full.pixmap() and not self._image_label_full.pixmap().isNull():
                pixmap = self._image_label_full.pixmap().copy()
            else:
                pixmap = QPixmap(self._image_label_full.size())
                pixmap.fill(Qt.black)

        if pixmap.save(filepath, "PNG"):
            print(f"Comparison exported to {filepath}")
        else:
            print(f"Failed to export comparison to {filepath}")

    # ── Display updates ───────────────────────────────────────────────

    def _update_toggle_visibility(self):
        """Show only the toggles that belong to the currently selected image."""
        current_indices = {i for i, _ in self._measurements_for_current_image()}
        for i, toggle in enumerate(self._toggle_widgets):
            toggle.setVisible(i in current_indices)

    def _update_image_display(self):
        """Render the DICOM image with measurement-row overlays on both image labels."""
        if self._dataset is None:
            for label in (self._image_label, self._image_label_full):
                label.setPixmap(QPixmap())
                label.setText("No image data")
            return

        try:
            qimage = dicom_to_qimage(self._dataset)
            if qimage is None or qimage.isNull():
                for label in (self._image_label, self._image_label_full):
                    label.setText("No image data")
                return
        except Exception as e:
            for label in (self._image_label, self._image_label_full):
                label.setText(f"Error: {str(e)}")
            return

        pixmap = QPixmap.fromImage(qimage)
        painter = QPainter(pixmap)

        for i, m in self._measurements_for_current_image():
            state = self._measurement_states[i]
            if not state['enabled']:
                continue

            win_x = m.get('win_x', 0)
            win_y = m.get('win_y', 0)
            win_w = m.get('win_w', m.get('cursor_size', 7))
            color = state['color']
            row = m.get('row', 0) + state['row_offset']

            window_pixels = m.get('window_pixels', [])
            if window_pixels:
                row = max(0, min(row, len(window_pixels) - 1))

            img_width = pixmap.width()
            img_height = pixmap.height()
            win_x_clamped = max(0, min(win_x, img_width - 1))
            win_w_clamped = max(1, min(win_w, img_width - win_x_clamped))
            line_y = max(0, min(win_y + row, img_height - 1))

            pen = QPen(color)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawLine(win_x_clamped, line_y, win_x_clamped + win_w_clamped - 1, line_y)

        painter.end()
        self._image_label.setPixmap(pixmap)
        self._image_label_full.setPixmap(pixmap)

    def _update_curve_display(self):
        """Full rebuild of all series and axes for the selected image.

        Creates brand-new QValueAxis objects every call to avoid the PySide6
        ownership bug where removeAxis makes stored axis objects stale so that
        subsequent addAxis/attachAxis calls silently fail.

        Series are added before axes (required by Qt Charts), then axes are
        attached to series afterward.

        Axis ranges are derived from ALL measurements (enabled or not) so the
        scale stays stable when toggling individual curves.
        """
        for chart in (self._chart, self._chart_full):
            chart.removeAllSeries()
            for axis in list(chart.axes()):
                chart.removeAxis(axis)

        if not self._measurements:
            return

        all_hu_values: List[float] = []
        all_window_widths: List[int] = []
        # (measurement_index, x_values, hu_values, color) for enabled series only
        enabled_series: List[Tuple] = []

        for i, m in self._measurements_for_current_image():
            state = self._measurement_states[i]

            win_w = m.get('win_w', m.get('cursor_size', 7))
            row = m.get('row', 0) + state['row_offset']
            slope = m.get('slope', 1.0)
            intercept = m.get('intercept', 0.0)

            window_pixels = m.get('window_pixels', [])
            if not window_pixels:
                continue

            all_window_widths.append(win_w)

            window_arr = np.array(window_pixels, dtype=np.float32)
            row = max(0, min(row, window_arr.shape[0] - 1))
            row_data = window_arr[row][:win_w]

            hu_values = [float(v) * slope + intercept for v in row_data]
            all_hu_values.extend(hu_values)  # always — keeps axis range stable on toggle

            if state['enabled']:
                enabled_series.append((i, list(range(len(row_data))), hu_values, state['color']))

        # Compute axis ranges from all measurements regardless of enabled state
        if all_hu_values:
            y_min = min(all_hu_values)
            y_max = max(all_hu_values)
            y_padding = (y_max - y_min) * 0.1 if y_max > y_min else 20
            y_min -= y_padding
            y_max += y_padding
        else:
            y_min, y_max = 0, 1

        x_max = max(all_window_widths) - 1 if all_window_widths else 1

        for chart in (self._chart, self._chart_full):
            # 1. Add series first (Qt Charts requirement)
            chart_series = []
            for i, x_values, hu_values, color in enabled_series:
                series = QSplineSeries()
                series.setName(f"M{i + 1}")
                series.setColor(color)
                for x, y in zip(x_values, hu_values):
                    series.append(x, y)
                chart.addSeries(series)
                chart_series.append(series)

            # 2. Create brand-new axis objects and add them to the chart
            axis_x = QValueAxis()
            axis_x.setTitleText("X Position (window-relative)")
            axis_x.setLabelFormat("%d")
            axis_x.setTickCount(10)
            axis_x.setRange(0, x_max)
            chart.addAxis(axis_x, Qt.AlignBottom)

            axis_y = QValueAxis()
            axis_y.setTitleText("HU Value")
            axis_y.setLabelFormat("%.1f")
            axis_y.setTickCount(10)
            axis_y.setRange(y_min, y_max)
            chart.addAxis(axis_y, Qt.AlignLeft)

            # 3. Attach axes to each series
            for series in chart_series:
                series.attachAxis(axis_x)
                series.attachAxis(axis_y)

        self._apply_theme()
        self._chart_view.repaint()
        self._chart_view_full.repaint()

    def _toggle_theme(self):
        """Toggle between light and dark mode."""
        self._dark_mode = not self._dark_mode
        self._apply_theme()
        # Update button icon
        self._theme_button.setText("🌓" if self._dark_mode else "☀️")

    def _apply_theme(self):
        """Apply the current theme (light or dark) to the charts."""
        if self._dark_mode:
            self._apply_dark_mode()
        else:
            self._apply_light_mode()

    def _apply_dark_mode(self):
        for chart in (self._chart, self._chart_full):
            chart.setBackgroundBrush(Qt.black)
            chart.setPlotAreaBackgroundBrush(Qt.black)
            chart.setPlotAreaBackgroundVisible(True)
            for axis in chart.axes():
                axis.setLabelsColor(Qt.white)
                axis.setTitleBrush(Qt.white)
                axis.setGridLineColor(Qt.darkGray)
                axis.setLinePenColor(Qt.white)

    def _apply_light_mode(self):
        for chart in (self._chart, self._chart_full):
            chart.setBackgroundBrush(Qt.white)
            chart.setPlotAreaBackgroundBrush(Qt.white)
            chart.setPlotAreaBackgroundVisible(True)
            for axis in chart.axes():
                axis.setLabelsColor(Qt.black)
                axis.setTitleBrush(Qt.black)
                axis.setGridLineColor(Qt.lightGray)
                axis.setLinePenColor(Qt.black)
