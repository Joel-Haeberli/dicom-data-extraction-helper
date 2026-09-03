#!/usr/bin/env python3
"""
Measurement Table Widget for DICOM Data Extraction Helper.

This widget displays measurements in a 19-column table format matching the legacy implementation.
It provides comprehensive measurement management, display, and export capabilities.
"""

from typing import Optional, List, Dict, Any, TYPE_CHECKING
from pathlib import Path
import csv
import json

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QFileDialog, QMessageBox, QSizePolicy,
    QLabel, QComboBox, QLineEdit
)
from PySide6.QtCore import Qt, Signal, QModelIndex
from PySide6.QtGui import QColor, QBrush, QFont

if TYPE_CHECKING:
    from models.measurement import Measurement, MeasurementCollection
    from services.measurement_service import MeasurementService


class MeasurementTableWidget(QWidget):
    """
    Advanced measurement table widget with 19 columns.
    
    Columns:
    0: # (index)
    1: Study
    2: Image Name  
    3: Z (position)
    4: X (cursor position)
    5: Y (cursor position)
    6: Size (cursor size)
    7: Form (circle/rectangle/cross)
    8: Raw Mean
    9: Raw Std
    10: Raw Min
    11: Raw Max
    12: HU Mean
    13: HU Std
    14: HU Min
    15: HU Max
    16: mm/px
    17: Note (editable)
    18: Delete (button)
    
    Features:
    - Editable cells for notes and names
    - Sorting by column
    - CSV export with all columns
    - JSON import/export
    - Row selection for viewer coordination
    - Delete button in each row
    - Context menu for bulk operations
    """
    
    # Signals
    measurement_selected = Signal(str)  # measurement_id
    measurement_deleted = Signal(str)  # measurement_id
    measurements_exported = Signal(str)  # file_path
    measurements_imported = Signal(str)  # file_path
    
    COLUMN_NAMES = [
        "#", "Study", "Image Name", "Z", "X", "Y", "Size", "Form",
        "Raw Mean", "Raw Std", "Raw Min", "Raw Max",
        "HU Mean", "HU Std", "HU Min", "HU Max",
        "mm/px", "Note", "Delete"
    ]
    
    COLUMN_WIDTHS = [
        40, 120, 150, 40, 40, 40, 60, 80,
        80, 80, 80, 80,
        80, 80, 80, 80,
        90, 300, 60
    ]
    
    def __init__(self, measurement_service: Optional['MeasurementService'] = None, 
                 parent=None):
        """Initialize the measurement table widget."""
        super().__init__(parent)
        
        self._measurement_service = measurement_service
        self._measurements: List[Measurement] = []
        self._filtered_measurements: List[Measurement] = []
        self._current_study_filter: Optional[str] = None
        self._current_series_filter: Optional[str] = None
        
        # Setup UI
        self._setup_ui()
        self._connect_signals()
        
        # Apply styling
        self._apply_styling()
    
    def _setup_ui(self):
        """Setup the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Create filter controls
        self._create_filter_controls(layout)
        
        # Create the table widget
        self._table = QTableWidget(self)
        self._table.setColumnCount(len(self.COLUMN_NAMES))
        self._table.setHorizontalHeaderLabels(self.COLUMN_NAMES)
        
        # Configure table behavior
        self._table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.verticalHeader().setVisible(False)
        
        # Set column widths
        for i, width in enumerate(self.COLUMN_WIDTHS):
            self._table.setColumnWidth(i, width)
        
        # Add table to layout
        layout.addWidget(self._table, 1)
        
        # Create export/import controls
        self._create_export_controls(layout)
        
        # Create info label
        self._info_label = QLabel("0 measurements", self)
        self._info_label.setStyleSheet("color: #e0e0e0; font-style: italic;")
        layout.addWidget(self._info_label)
    
    def _create_filter_controls(self, layout):
        """Create filter controls for the table."""
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(8)
        
        # Study filter
        filter_layout.addWidget(QLabel("Study:", self))
        self._study_filter_combo = QComboBox(self)
        self._study_filter_combo.addItem("All Studies", "")
        self._study_filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self._study_filter_combo)
        
        # Series filter
        filter_layout.addWidget(QLabel("Series:", self))
        self._series_filter_combo = QComboBox(self)
        self._series_filter_combo.addItem("All Series", "")
        self._series_filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self._series_filter_combo)
        
        filter_layout.addStretch(1)
        layout.addLayout(filter_layout)
    
    def _create_export_controls(self, layout):
        """Create export/import controls."""
        export_layout = QHBoxLayout()
        export_layout.setContentsMargins(0, 0, 0, 0)
        export_layout.setSpacing(8)
        
        # CSV export
        self._export_csv_button = QPushButton("Export CSV", self)
        self._export_csv_button.setToolTip("Export measurements to CSV file")
        self._export_csv_button.clicked.connect(self.export_to_csv)
        export_layout.addWidget(self._export_csv_button)
        
        # JSON export
        self._export_json_button = QPushButton("Export JSON", self)
        self._export_json_button.setToolTip("Export measurements to JSON file")
        self._export_json_button.clicked.connect(self.export_to_json)
        export_layout.addWidget(self._export_json_button)
        
        # JSON import
        self._import_json_button = QPushButton("Import JSON", self)
        self._import_json_button.setToolTip("Import measurements from JSON file")
        self._import_json_button.clicked.connect(self.import_from_json)
        export_layout.addWidget(self._import_json_button)
        
        export_layout.addStretch(1)
        layout.addLayout(export_layout)
    
    def _apply_styling(self):
        """Apply dark mode styling to the table."""
        self._table.setStyleSheet("""
            QTableWidget {
                background-color: #2b2b2b;
                color: #e0e0e0;
                gridline-color: #444;
                selection-background-color: #0078d7;
                selection-color: #ffffff;
                border: 1px solid #444;
            }
            QHeaderView::section {
                background-color: #3c3c3c;
                color: #e0e0e0;
                padding: 4px;
                border: 1px solid #444;
            }
            QTableWidget::item:selected {
                background-color: #0078d7;
                color: #ffffff;
            }
            QTableWidget::item {
                padding: 2px 4px;
            }
        """)
    
    def _connect_signals(self):
        """Connect internal signals."""
        self._table.cellChanged.connect(self._on_cell_changed)
        self._table.cellClicked.connect(self._on_cell_clicked)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
    
    @property
    def measurement_service(self) -> Optional['MeasurementService']:
        """Get the measurement service."""
        return self._measurement_service
    
    @measurement_service.setter
    def measurement_service(self, service: 'MeasurementService'):
        """Set the measurement service."""
        self._measurement_service = service
        if service:
            self._update_from_service()
    
    @property
    def measurements(self) -> List['Measurement']:
        """Get all measurements."""
        return self._measurements.copy()
    
    @measurements.setter
    def measurements(self, measurements: List['Measurement']):
        """Set measurements and update display."""
        self._measurements = measurements.copy()
        self._apply_filters()
        self._update_table()
        self._update_filter_combos()
        self._update_info_label()
    
    def _update_from_service(self):
        """Update measurements from the measurement service."""
        if self._measurement_service:
            self.measurements = self._measurement_service.measurements
    
    def _apply_filters(self):
        """Apply current filters to the measurements list."""
        filtered = self._measurements
        
        # Apply study filter
        if self._current_study_filter:
            filtered = [m for m in filtered if m.study_uid == self._current_study_filter]
        
        # Apply series filter
        if self._current_series_filter:
            filtered = [m for m in filtered if m.series_uid == self._current_series_filter]
        
        self._filtered_measurements = filtered
    
    def _update_filter_combos(self):
        """Update the study and series filter combos."""
        self._study_filter_combo.blockSignals(True)
        self._series_filter_combo.blockSignals(True)
        
        try:
            # Get unique study UIDs
            study_uids = set(m.study_uid for m in self._measurements if m.study_uid)
            self._study_filter_combo.clear()
            self._study_filter_combo.addItem("All Studies", "")
            for study_uid in sorted(study_uids):
                # Try to find a more descriptive name
                study_names = [m.metadata.get('StudyDescription', m.study_uid) 
                              for m in self._measurements 
                              if m.study_uid == study_uid and m.metadata.get('StudyDescription')]
                if study_names:
                    self._study_filter_combo.addItem(f"{study_names[0]} ({study_uid})", study_uid)
                else:
                    self._study_filter_combo.addItem(study_uid, study_uid)
            
            # Get unique series UIDs
            series_uids = set(m.series_uid for m in self._measurements if m.series_uid)
            self._series_filter_combo.clear()
            self._series_filter_combo.addItem("All Series", "")
            for series_uid in sorted(series_uids):
                # Try to find a more descriptive name
                series_names = [m.metadata.get('SeriesDescription', m.series_uid) 
                               for m in self._measurements 
                               if m.series_uid == series_uid and m.metadata.get('SeriesDescription')]
                if series_names:
                    self._series_filter_combo.addItem(f"{series_names[0]} ({series_uid})", series_uid)
                else:
                    self._series_filter_combo.addItem(series_uid, series_uid)
        
        finally:
            self._study_filter_combo.blockSignals(False)
            self._series_filter_combo.blockSignals(False)
    
    def _on_filter_changed(self, index: int):
        """Handle filter combo box changes."""
        sender = self.sender()
        
        if sender == self._study_filter_combo:
            self._current_study_filter = self._study_filter_combo.currentData()
        elif sender == self._series_filter_combo:
            self._current_series_filter = self._series_filter_combo.currentData()
        
        self._apply_filters()
        self._update_table()
        self._update_info_label()
    
    def _update_table(self):
        """Update the table with current measurements."""
        self._table.blockSignals(True)
        
        try:
            # Clear existing rows
            self._table.setRowCount(0)
            
            # Add rows for filtered measurements
            for i, measurement in enumerate(self._filtered_measurements):
                self._add_measurement_row(i, measurement)
            
            # Resize columns to contents
            for col in range(self._table.columnCount):
                if col != 18:  # Skip delete column
                    self._table.resizeColumnToContents(col)
        
        finally:
            self._table.blockSignals(False)
    
    def _add_measurement_row(self, row_index: int, measurement: 'Measurement'):
        """Add a measurement as a row in the table."""
        self._table.insertRow(row_index)
        
        # Column 0: # (index)
        item = QTableWidgetItem(str(row_index + 1))
        item.setTextAlignment(Qt.AlignCenter)
        self._table.setItem(row_index, 0, item)
        
        # Column 1: Study
        study_text = measurement.metadata.get('StudyDescription', measurement.study_uid[:8] + '...' if len(measurement.study_uid) > 8 else measurement.study_uid)
        study_item = QTableWidgetItem(str(study_text))
        study_item.setToolTip(f"Study: {measurement.study_uid}")
        self._table.setItem(row_index, 1, study_item)
        
        # Column 2: Image Name
        image_name = measurement.name or measurement.metadata.get('image_name', '')
        name_item = QTableWidgetItem(str(image_name))
        name_item.setToolTip(f"Measurement: {measurement.measurement_id}")
        self._table.setItem(row_index, 2, name_item)
        
        # Column 3: Z (position)
        z_item = QTableWidgetItem(f"{measurement.z_position:.2f}")
        z_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._table.setItem(row_index, 3, z_item)
        
        # Column 4: X (cursor position)
        x_item = QTableWidgetItem(str(measurement.x))
        x_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._table.setItem(row_index, 4, x_item)
        
        # Column 5: Y (cursor position)
        y_item = QTableWidgetItem(str(measurement.y))
        y_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._table.setItem(row_index, 5, y_item)
        
        # Column 6: Size (cursor size)
        size_item = QTableWidgetItem(str(measurement.roi_size))
        size_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._table.setItem(row_index, 6, size_item)
        
        # Column 7: Form (circle/rectangle/cross)
        form_item = QTableWidgetItem(str(measurement.roi_form or ''))
        form_item.setTextAlignment(Qt.AlignCenter)
        self._table.setItem(row_index, 7, form_item)
        
        # Column 8: Raw Mean
        raw_mean_item = QTableWidgetItem(f"{measurement.raw_mean:.2f}")
        raw_mean_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._table.setItem(row_index, 8, raw_mean_item)
        
        # Column 9: Raw Std
        raw_std_item = QTableWidgetItem(f"{measurement.raw_std:.2f}")
        raw_std_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._table.setItem(row_index, 9, raw_std_item)
        
        # Column 10: Raw Min
        raw_min_item = QTableWidgetItem(f"{measurement.raw_min:.2f}")
        raw_min_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._table.setItem(row_index, 10, raw_min_item)
        
        # Column 11: Raw Max
        raw_max_item = QTableWidgetItem(f"{measurement.raw_max:.2f}")
        raw_max_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._table.setItem(row_index, 11, raw_max_item)
        
        # Column 12: HU Mean
        hu_mean_item = QTableWidgetItem(f"{measurement.hu_mean:.2f}")
        hu_mean_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._table.setItem(row_index, 12, hu_mean_item)
        
        # Column 13: HU Std
        hu_std_item = QTableWidgetItem(f"{measurement.hu_std:.2f}")
        hu_std_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._table.setItem(row_index, 13, hu_std_item)
        
        # Column 14: HU Min
        hu_min_item = QTableWidgetItem(f"{measurement.hu_min:.2f}")
        hu_min_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._table.setItem(row_index, 14, hu_min_item)
        
        # Column 15: HU Max
        hu_max_item = QTableWidgetItem(f"{measurement.hu_max:.2f}")
        hu_max_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._table.setItem(row_index, 15, hu_max_item)
        
        # Column 16: mm/px
        mm_px_item = QTableWidgetItem(f"{measurement.mm_per_pixel:.4f}")
        mm_px_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._table.setItem(row_index, 16, mm_px_item)
        
        # Column 17: Note (editable)
        note_item = QTableWidgetItem(str(measurement.notes))
        note_item.setFlags(note_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self._table.setItem(row_index, 17, note_item)
        
        # Column 18: Delete button
        delete_button = QPushButton("X", self)
        delete_button.setStyleSheet("color: #ff5555; background: #2b2b2b; border: 1px solid #ff5555;")
        delete_button.setMaximumWidth(40)
        delete_button.setProperty("row", row_index)
        delete_button.setProperty("measurement_id", measurement.measurement_id)
        delete_button.clicked.connect(self._on_delete_clicked)
        self._table.setCellWidget(row_index, 18, delete_button)
    
    def _update_info_label(self):
        """Update the info label with current measurement count."""
        total_count = len(self._measurements)
        filtered_count = len(self._filtered_measurements)
        
        info_parts = []
        if self._current_study_filter:
            info_parts.append(f"Study: {self._current_study_filter[:8]}...")
        if self._current_series_filter:
            info_parts.append(f"Series: {self._current_series_filter[:8]}...")
        
        filter_info = " | ".join(info_parts) + " | " if info_parts else ""
        self._info_label.setText(f"{filter_info}{filtered_count}/{total_count} measurements")
    
    def _on_cell_changed(self, row: int, column: int):
        """Handle cell content changes (for editable cells)."""
        if 0 <= row < len(self._filtered_measurements):
            measurement = self._filtered_measurements[row]
            item = self._table.item(row, column)
            
            if item and column == 17:  # Note column
                new_notes = item.text()
                if new_notes != measurement.notes:
                    measurement.notes = new_notes
                    if self._measurement_service:
                        self._measurement_service.update_measurement_notes(
                            measurement.measurement_id, new_notes)
            
            elif item and column == 2:  # Name column
                new_name = item.text()
                if new_name != measurement.name:
                    measurement.name = new_name
                    if self._measurement_service:
                        self._measurement_service.update_measurement_name(
                            measurement.measurement_id, new_name)
    
    def _on_cell_clicked(self, row: int, column: int):
        """Handle cell clicks."""
        if 0 <= row < len(self._filtered_measurements):
            measurement = self._filtered_measurements[row]
            
            # Emit measurement selected signal (except for delete column)
            if column != 18:
                self.measurement_selected.emit(measurement.measurement_id)
    
    def _on_selection_changed(self):
        """Handle row selection changes."""
        selected_rows = self._table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            if 0 <= row < len(self._filtered_measurements):
                measurement = self._filtered_measurements[row]
                self.measurement_selected.emit(measurement.measurement_id)
    
    def _on_delete_clicked(self):
        """Handle delete button clicks."""
        button = self.sender()
        if button and hasattr(button, 'measurement_id'):
            measurement_id = button.measurement_id
            
            # Confirm deletion
            reply = QMessageBox.question(
                self, 
                "Delete Measurement", 
                "Are you sure you want to delete this measurement?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Remove from our list
                self._measurements = [m for m in self._measurements 
                                    if m.measurement_id != measurement_id]
                
                # Remove via service if available
                if self._measurement_service:
                    self._measurement_service.remove_measurement(measurement_id)
                
                # Update display
                self._apply_filters()
                self._update_table()
                self._update_info_label()
                
                # Emit signal
                self.measurement_deleted.emit(measurement_id)
    
    def add_measurement(self, measurement: 'Measurement'):
        """Add a measurement to the table."""
        self._measurements.append(measurement)
        self._apply_filters()
        self._update_table()
        self._update_filter_combos()
        self._update_info_label()
    
    def remove_measurement(self, measurement_id: str) -> bool:
        """Remove a measurement by ID."""
        initial_count = len(self._measurements)
        self._measurements = [m for m in self._measurements 
                            if m.measurement_id != measurement_id]
        
        if len(self._measurements) < initial_count:
            self._apply_filters()
            self._update_table()
            self._update_info_label()
            return True
        return False
    
    def clear_measurements(self):
        """Clear all measurements from the table."""
        self._measurements.clear()
        self._filtered_measurements.clear()
        self._current_study_filter = None
        self._current_series_filter = None
        self._update_table()
        self._update_filter_combos()
        self._update_info_label()
    
    def refresh(self):
        """Refresh the table display."""
        self._update_from_service()
    
    def export_to_csv(self):
        """Export measurements to CSV file."""
        if not self._filtered_measurements:
            QMessageBox.information(self, "Export CSV", "No measurements to export.")
            return
        
        # Get file path from user
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Export Measurements to CSV", 
            "", 
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if file_path:
            try:
                file_path = Path(file_path)
                if not file_path.suffix:
                    file_path = file_path.with_suffix('.csv')
                
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    
                    # Write header
                    writer.writerow(self.COLUMN_NAMES)
                    
                    # Write data rows
                    for measurement in self._filtered_measurements:
                        row = self._measurement_to_csv_row(measurement)
                        writer.writerow(row)
                
                self.measurements_exported.emit(str(file_path))
                QMessageBox.information(self, "Export Successful", f"Exported {len(self._filtered_measurements)} measurements to:\n{file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export CSV: {str(e)}")
    
    def export_to_json(self):
        """Export measurements to JSON file."""
        if not self._filtered_measurements:
            QMessageBox.information(self, "Export JSON", "No measurements to export.")
            return
        
        # Get file path from user
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Export Measurements to JSON", 
            "", 
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            try:
                file_path = Path(file_path)
                if not file_path.suffix:
                    file_path = file_path.with_suffix('.json')
                
                data = [m.to_dict() for m in self._filtered_measurements]
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                self.measurements_exported.emit(str(file_path))
                QMessageBox.information(self, "Export Successful", f"Exported {len(self._filtered_measurements)} measurements to:\n{file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export JSON: {str(e)}")
    
    def import_from_json(self):
        """Import measurements from JSON file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Import Measurements from JSON", 
            "", 
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            try:
                file_path = Path(file_path)
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                imported_count = 0
                if isinstance(data, list):
                    for item in data:
                        measurement = Measurement.from_dict(item)
                        if measurement:
                            if self._measurement_service:
                                # Import via service to ensure proper handling
                                self._measurement_service.import_measurements_from_json([item])
                            else:
                                self._measurements.append(measurement)
                            imported_count += 1
                elif isinstance(data, dict):
                    measurement = Measurement.from_dict(data)
                    if measurement:
                        if self._measurement_service:
                            self._measurement_service.import_measurements_from_json(data)
                        else:
                            self._measurements.append(measurement)
                        imported_count += 1
                
                # Update display
                self._apply_filters()
                self._update_table()
                self._update_filter_combos()
                self._update_info_label()
                
                self.measurements_imported.emit(str(file_path))
                QMessageBox.information(self, "Import Successful", f"Imported {imported_count} measurements from:\n{file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Failed to import JSON: {str(e)}")
    
    def _measurement_to_csv_row(self, measurement: 'Measurement') -> List[str]:
        """Convert a measurement to CSV row format."""
        return [
            str(self._filtered_measurements.index(measurement) + 1),  # #
            measurement.metadata.get('StudyDescription', measurement.study_uid),  # Study
            measurement.name,  # Image Name
            f"{measurement.z_position:.2f}",  # Z
            str(measurement.x),  # X
            str(measurement.y),  # Y
            str(measurement.roi_size),  # Size
            str(measurement.roi_form or ''),  # Form
            f"{measurement.raw_mean:.2f}",  # Raw Mean
            f"{measurement.raw_std:.2f}",  # Raw Std
            f"{measurement.raw_min:.2f}",  # Raw Min
            f"{measurement.raw_max:.2f}",  # Raw Max
            f"{measurement.hu_mean:.2f}",  # HU Mean
            f"{measurement.hu_std:.2f}",  # HU Std
            f"{measurement.hu_min:.2f}",  # HU Min
            f"{measurement.hu_max:.2f}",  # HU Max
            f"{measurement.mm_per_pixel:.4f}",  # mm/px
            measurement.notes,  # Note
            ""  # Delete column (empty in CSV)
        ]
    
    def get_selected_measurement(self) -> Optional['Measurement']:
        """Get the currently selected measurement."""
        selected_rows = self._table.selectionModel().selectedRows()
        if selected_rows and len(selected_rows) > 0:
            row = selected_rows[0].row()
            if 0 <= row < len(self._filtered_measurements):
                return self._filtered_measurements[row]
        return None
    
    def get_selected_measurement_id(self) -> Optional[str]:
        """Get the ID of the currently selected measurement."""
        measurement = self.get_selected_measurement()
        if measurement:
            return measurement.measurement_id
        return None
    
    def select_measurement_by_id(self, measurement_id: str):
        """Select a measurement by its ID."""
        for i, measurement in enumerate(self._filtered_measurements):
            if measurement.measurement_id == measurement_id:
                self._table.selectRow(i)
                self._table.scrollToItem(self._table.item(i, 0))
                break