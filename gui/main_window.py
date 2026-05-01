#!/usr/bin/env python3
"""
Main Window for DICOM Data Extraction Helper GUI

The main application window with two-column layout:
- Left: Metadata table
- Right: Image viewer
- Top: Load button and current selection info
"""

from pathlib import Path
from typing import Optional, List
import csv

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QPushButton, QLabel, QSpinBox,
    QHBoxLayout, QVBoxLayout, QFileDialog, QMessageBox,
    QColorDialog, QCheckBox, QTableWidget, QTableWidgetItem,
    QStackedWidget, QDockWidget, QDialog
)
from PySide6.QtCore import Qt, Signal, QSize, QEvent
from PySide6.QtGui import QIcon, QWheelEvent, QColor
from PySide6.QtWidgets import QSizePolicy

from gui.metadata_table import MetadataTable
from gui.image_tabs import ImageTabs
from gui.utils.dicom_loader import DICOMLoader, DICOMFile
from gui.utils.image_utils import (
    dicom_to_qimage,
    extract_overlay_array,
    overlay_to_qimage, extract_overlay_with_origin,
    get_original_size,
)
from gui.utils.pacs_client import PACSClient, PACSConfig, ConnectionStatus
from gui.pacs_connection_dialog import PACSConnectionDialog
from gui.pacs_browser import PACSBrowser


class MainWindow(QMainWindow):
    """
    Main application window for DICOM viewing.
    
    Layout:
    +-----------------------------------------------------+
    | [Load] [←] [spin] [Z:] [/N] [→] [Color] [Current]    |
    +-----------------------------------------------------+
    | METADATA TABLE (1/3) | IMAGE TABS (2/3)              |
    |                      +-----------------------------+
    |                      | Image | Pixel Data |        |
    +---------------------+------------------------------+
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Window setup
        self.setWindowTitle("DICOM Data Extraction Helper")
        self.setMinimumSize(800, 600)
        
        # State
        self._dicom_loader = DICOMLoader()
        self._current_dicom_file: Optional[DICOMFile] = None
        self._current_directory: Optional[Path] = None
        self._current_image_index: int = 0
        self._image_files: List[DICOMFile] = []
        self._overlay_color = (255, 0, 0)  # Default: red
        self._measurements: List[dict] = []  # List of measurement entries
        self._image_viewer_window = None  # Reference to external image viewer window
        
        # PACS state
        self._pacs_client = PACSClient()
        self._pacs_browser: Optional[PACSBrowser] = None
        self._pacs_dock: Optional[QDockWidget] = None
        
        # Create UI
        self._create_widgets()
        self._setup_layout()
        self._connect_signals()
        
        # Enable mouse wheel on the central widget
        self._central_widget.setFocusPolicy(Qt.StrongFocus)
        
        # Connect to pixel array table's navigation signals (external window wheel events)
        self._image_tabs.pixel_array_table.next_image_requested.connect(self._on_next_button_clicked)
        self._image_tabs.pixel_array_table.prev_image_requested.connect(self._on_prev_button_clicked)
        self._image_tabs.pixel_array_table.image_index_changed.connect(self._on_image_index_changed)
        self._image_tabs.pixel_array_table.overlay_color_changed.connect(self._set_overlay_color)
        self._image_tabs.pixel_array_table.add_measurement_requested.connect(self._on_add_measurement)
        self._image_tabs.pixel_array_table.viewer_reopened.connect(self._on_viewer_reopened)
        
        # Setup PACS client callbacks
        self._pacs_client.set_status_change_callback(self._on_pacs_status_change)
        
        # Initial state
        self._update_current_selection()
        
        # Set up close event to close external viewer
        self.setAttribute(Qt.WA_DeleteOnClose)
    
    def closeEvent(self, event):
        """Close event handler - closes external image viewer window and PACS resources."""
        # Close external image viewer if it exists
        if (hasattr(self, '_image_tabs') and self._image_tabs is not None and
            hasattr(self._image_tabs, 'pixel_array_table') and
            self._image_tabs.pixel_array_table is not None and
            hasattr(self._image_tabs.pixel_array_table, '_image_viewer_window') and
            self._image_tabs.pixel_array_table._image_viewer_window is not None):
            self._image_tabs.pixel_array_table._image_viewer_window.close()
            self._image_tabs.pixel_array_table._image_viewer_window = None
        
        # Clean up PACS resources (disconnect callbacks first to avoid issues)
        self._pacs_client._on_status_change = None
        self._pacs_client._on_query_result = None
        self._pacs_client._on_retrieval_complete = None
        
        if self._pacs_browser:
            try:
                self._pacs_browser.cleanup()
            except Exception:
                pass
            self._pacs_browser = None
        
        if self._pacs_dock:
            try:
                self._pacs_dock.deleteLater()
            except Exception:
                pass
            self._pacs_dock = None
        
        try:
            self._pacs_client.cleanup()
        except Exception:
            pass
        
        event.accept()
    
    def _on_viewer_reopened(self):
        """Handler for when the image viewer window is reopened.
        Updates navigation and reloads overlay."""
        self._update_navigation_ui()
        self._load_overlay_for_current_file()
    
    def _on_show_image_window_clicked(self):
        """Handler for Show Image Window button click.
        Reopens the external image viewer if it's closed."""
        if (hasattr(self, '_image_tabs') and self._image_tabs is not None and
            hasattr(self._image_tabs, 'pixel_array_table') and
            self._image_tabs.pixel_array_table is not None):
            
            pixel_table = self._image_tabs.pixel_array_table
            
            # Use the public method to open/reopen the viewer with current dataset
            if hasattr(pixel_table, 'open_image_viewer_window'):
                # Pass current dataset if available
                current_dataset = None
                if self._current_dicom_file is not None:
                    current_dataset = self._current_dicom_file.dataset
                pixel_table.open_image_viewer_window(current_dataset)
    
    def _create_widgets(self):
        """Create all child widgets."""
        # Central widget
        self._central_widget = QWidget(self)
        self.setCentralWidget(self._central_widget)
        
        # Top controls
        self._load_button = QPushButton("Load DICOM Directory...", self)
        self._load_button.setToolTip("Select a directory containing DICOM files")
        
        # PACS button
        self._pacs_button = QPushButton("PACS", self)
        self._pacs_button.setToolTip("Connect to PACS and query studies")
        self._pacs_button.setCheckable(True)
        
        # Show image window button
        self._show_image_window_button = QPushButton("Show Image Window", self)
        self._show_image_window_button.setToolTip("Open or reopen the image viewer window")
        self._show_image_window_button.clicked.connect(self._on_show_image_window_clicked)
        
        # Current file label
        self._current_selection_label = QLabel("No DICOM directory loaded", self)
        self._current_selection_label.setStyleSheet("font-style: italic; color: #666;")
        
        # Navigation widgets are now in the external image viewer
        self._prev_button = None
        self._next_button = None
        self._image_spinbox = None
        self._image_count_label = None
        
        # Overlay color picker is now in the external image viewer
        self._color_button = None
        
        # Overlay color state
        self._overlay_color = (255, 0, 0)  # Default: red
        
        # Metadata table (left column)
        self._metadata_table = MetadataTable(self)
        
        # Measurements table (below metadata)
        self._measurements_table = QTableWidget(self)
        self._measurements_table.setColumnCount(16)
        self._measurements_table.setHorizontalHeaderLabels([
            "#", "Z", "X", "Y", "Size", "Form", 
            "Raw Mean", "Raw Std", "Raw Min", "Raw Max",
            "HU Mean", "HU Std", "HU Min", "HU Max",
            "Note", "Delete"
        ])
        self._measurements_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed)
        self._measurements_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._measurements_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._measurements_table.horizontalHeader().setStretchLastSection(False)
        
        # Set column widths - Note column wider, others reasonable
        self._measurements_table.setColumnWidth(0, 40)  # #
        self._measurements_table.setColumnWidth(1, 40)  # Z (new)
        self._measurements_table.setColumnWidth(2, 40)  # X
        self._measurements_table.setColumnWidth(3, 40)  # Y
        self._measurements_table.setColumnWidth(4, 60)  # Size
        self._measurements_table.setColumnWidth(5, 80)  # Form
        self._measurements_table.setColumnWidth(6, 80)  # Raw Mean
        self._measurements_table.setColumnWidth(7, 80)  # Raw Std
        self._measurements_table.setColumnWidth(8, 80)  # Raw Min
        self._measurements_table.setColumnWidth(9, 80)  # Raw Max
        self._measurements_table.setColumnWidth(10, 80)  # HU Mean
        self._measurements_table.setColumnWidth(11, 80)  # HU Std
        self._measurements_table.setColumnWidth(12, 80)  # HU Min
        self._measurements_table.setColumnWidth(13, 80)  # HU Max
        self._measurements_table.setColumnWidth(14, 300)  # Note - wider
        self._measurements_table.setColumnWidth(15, 60)  # Delete
        
        # Export button for measurements
        self._export_measurements_button = QPushButton("Export Measurements (CSV)", self)
        self._export_measurements_button.setToolTip("Export measurements table to CSV file")
        self._export_measurements_button.clicked.connect(self._on_export_measurements)
        
        # Connect cell change signal to update notes
        self._measurements_table.cellChanged.connect(self._on_measurement_cell_changed)
        # Connect cell click signal for delete button
        self._measurements_table.cellClicked.connect(self._on_measurement_cell_clicked)
        
        # Image tabs (right column) - contains image viewer and pixel array table
        self._image_tabs = ImageTabs(self)
    
    def _setup_layout(self):
        """Setup the main layout."""
        # Main layout for central widget
        main_layout = QVBoxLayout(self._central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)
        
        # Top row: Load button + PACS button + Show Image Window button + current selection
        top_layout = QHBoxLayout()
        top_layout.addWidget(self._load_button, 0)
        top_layout.addWidget(self._pacs_button, 0)
        top_layout.addWidget(self._show_image_window_button, 0)
        top_layout.addWidget(self._current_selection_label, 1)
        top_layout.addStretch(1)
        
        # Main columns area
        columns_layout = QHBoxLayout()
        columns_layout.setContentsMargins(0, 0, 0, 0)
        columns_layout.setSpacing(8)
        
        # Left column: Metadata table (1/3 width)
        columns_layout.addWidget(self._metadata_table, 1)
        
        # Right column: Image tabs with image viewer and pixel array table (2/3 width)
        columns_layout.addWidget(self._image_tabs, 2)
        
        # Measurements table spans full width below columns
        measurements_layout = QVBoxLayout()
        measurements_layout.addWidget(self._measurements_table, 1)
        measurements_layout.addWidget(self._export_measurements_button, 0)
        
        # Combine layouts
        main_layout.addLayout(top_layout, 0)
        main_layout.addLayout(columns_layout, 1)
        main_layout.addLayout(measurements_layout, 0)
    
    def _connect_signals(self):
        """Connect signals between widgets."""
        self._load_button.clicked.connect(self._on_load_button_clicked)
        self._pacs_button.clicked.connect(self._on_pacs_button_clicked)
        # Navigation and overlay controls are now in external image viewer
        # Connections will be made when viewer is created
    
    def _on_pacs_button_clicked(self, checked: bool):
        """
        Handler for PACS button click.
        Shows the PACS connection dialog if not connected, or hides the PACS browser if connected.
        """
        if checked:
            # Show connection dialog
            self._show_pacs_connection_dialog()
        else:
            # Hide PACS browser
            self._hide_pacs_browser()
    
    def _on_pacs_status_change(self, status: ConnectionStatus, message: str):
        """
        Handler for PACS client status changes.
        Updates UI to reflect connection status.
        """
        if status == ConnectionStatus.CONNECTED:
            self._pacs_button.setChecked(True)
            self._pacs_button.setText("PACS (Connected)")
            self._pacs_button.setStyleSheet("background-color: #c8e6c9;")
        elif status == ConnectionStatus.CONNECTING:
            self._pacs_button.setText("PACS (Connecting...)")
            self._pacs_button.setStyleSheet("background-color: #bbdefb;")
        elif status == ConnectionStatus.ERROR:
            self._pacs_button.setChecked(False)
            self._pacs_button.setText("PACS (Error)")
            self._pacs_button.setStyleSheet("background-color: #ffcdd2;")
        else:
            self._pacs_button.setChecked(False)
            self._pacs_button.setText("PACS")
            self._pacs_button.setStyleSheet("")
    
    def _show_pacs_connection_dialog(self):
        """Show the PACS connection dialog."""
        dialog = PACSConnectionDialog(self._pacs_client, self)
        dialog.connection_successful.connect(self._on_pacs_connected)
        
        if dialog.exec() == QDialog.Accepted:
            # Connection was successful
            self._on_pacs_connected(dialog.get_config())
        else:
            # User cancelled, uncheck the button
            self._pacs_button.setChecked(False)
    
    def _on_pacs_connected(self, config: PACSConfig):
        """
        Handler for successful PACS connection.
        Shows the PACS browser dock widget.
        """
        self._pacs_button.setChecked(True)
        self._show_pacs_browser()
    
    def _show_pacs_browser(self):
        """Show the PACS browser as a dock widget."""
        if self._pacs_browser is None:
            # Create PACS browser
            self._pacs_browser = PACSBrowser(self._pacs_client, self)
            self._pacs_browser.files_retrieved.connect(self._on_pacs_files_retrieved)
            
            # Create dock widget
            self._pacs_dock = QDockWidget("PACS Browser", self)
            self._pacs_dock.setWidget(self._pacs_browser)
            self._pacs_dock.setFeatures(
                QDockWidget.DockWidgetFeature.DockWidgetMovable |
                QDockWidget.DockWidgetFeature.DockWidgetFloatable
            )
            
            # Add to main window
            self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._pacs_dock)
            
            # Connect dock visibility to button state
            self._pacs_dock.visibilityChanged.connect(self._on_pacs_dock_visibility_changed)
        
        self._pacs_dock.show()
        self._pacs_dock.raise_()
    
    def _hide_pacs_browser(self):
        """Hide the PACS browser dock widget."""
        if self._pacs_dock:
            self._pacs_dock.hide()
        self._pacs_button.setChecked(False)
        self._pacs_button.setText("PACS")
        self._pacs_button.setStyleSheet("")
    
    def _on_pacs_dock_visibility_changed(self, visible: bool):
        """Handler for PACS dock visibility changes."""
        if not visible:
            self._pacs_button.setChecked(False)
    
    def _on_pacs_files_retrieved(self, file_paths: List[Path]):
        """
        Handler for files retrieved from PACS.
        Loads the retrieved files into the application.
        """
        if file_paths:
            # Use the directory of the first file
            directory = file_paths[0].parent
            self._load_dicom_directory(directory)
            
            # Show success message
            QMessageBox.information(
                self,
                "Files Loaded",
                f"Loaded {len(file_paths)} DICOM files from PACS.\n\nDirectory: {directory}"
            )
    
    def _on_load_button_clicked(self):
        """
        Handler for Load DICOM Directory button click.
        Opens file dialog to select directory and loads DICOM files.
        """
        # Open directory selection dialog
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.ShowDirsOnly, True)
        dialog.setWindowTitle("Select DICOM Directory")
        
        if dialog.exec() == QFileDialog.Accepted:
            directory = Path(dialog.selectedFiles()[0])
            self._load_dicom_directory(directory)
    
    def _load_dicom_directory(self, directory: Path):
        """
        Load DICOM files from the specified directory.
        
        Args:
            directory: Path to directory containing DICOM files
        """
        try:
            # Clear previous state
            self._metadata_table.clear()
            self._image_tabs.clear()
            self._measurements = []
            self._update_measurements_table()
            self._current_directory = directory
            self._current_image_index = 0
            
            # Load DICOM files
            self._dicom_loader.load_directory(directory)
            
            # Get all image files and sort by Z coordinate (descending: highest Z first)
            self._image_files = [f for f in self._dicom_loader.dicom_files if f.is_image]
            self._image_files.sort(key=lambda x: x.image_coordinates.get('z', float('inf')), reverse=True)
            
            if not self._image_files:
                QMessageBox.information(
                    self,
                    "No Images Found",
                    f"No image files found in:\n{directory}"
                )
                self._current_selection_label.setText(f"No images in: {directory.name}")
                return
            
            # Display the first image
            self._display_dicom_file(self._image_files[0])
            
            # Update navigation UI
            self._update_navigation_ui()
            self._update_current_selection(self._image_files[0].filepath.name)
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Loading DICOM",
                f"Failed to load DICOM directory:\n{str(e)}"
            )
    
    def _load_overlay_for_current_file(self):
        """Load and set overlay for the current DICOM file."""
        if (self._current_dicom_file is not None and 
            self._current_dicom_file.dataset is not None and 
            self._current_dicom_file.is_image):
            base_qimage = dicom_to_qimage(self._current_dicom_file.dataset)
            if base_qimage is not None:
                overlay_qimage = None
                overlay_file = self._dicom_loader.get_overlay_for_image(self._current_dicom_file)
                if overlay_file and overlay_file.dataset:
                    overlay_data = extract_overlay_with_origin(overlay_file.dataset)
                    if overlay_data is not None:
                        overlay_array, origin_x, origin_y = overlay_data
                        overlay_qimage = overlay_to_qimage(
                            overlay_array,
                            base_qimage.width(),
                            base_qimage.height(),
                            color=self._overlay_color,
                            opacity=0.7,
                            origin_x=origin_x,
                            origin_y=origin_y
                        )
                self._image_tabs.set_overlay(overlay_qimage)
    
    def _display_dicom_file(self, dicom_file: DICOMFile):
        """
        Display a DICOM file's metadata and image.
        
        Args:
            dicom_file: DICOMFile to display
        """
        self._current_dicom_file = dicom_file
        
        # Display metadata
        self._metadata_table.set_metadata(dicom_file.metadata)
        
        # Display image and pixel data
        if dicom_file.dataset and dicom_file.is_image:
            # Set dataset on image tabs (handles both image and lazy pixel data loading)
            self._image_tabs.set_dataset(dicom_file.dataset)
            
            # Try to find and display overlay
            self._load_overlay_for_current_file()
    
    def _on_prev_button_clicked(self):
        """Handler for Previous button click."""
        if self._image_files and self._current_image_index > 0:
            self._current_image_index -= 1
            self._display_dicom_file(self._image_files[self._current_image_index])
            self._update_navigation_ui()
            self._update_current_selection(self._image_files[self._current_image_index].filepath.name)
    
    def _on_next_button_clicked(self):
        """Handler for Next button click."""
        if self._image_files and self._current_image_index < len(self._image_files) - 1:
            self._current_image_index += 1
            self._display_dicom_file(self._image_files[self._current_image_index])
            self._update_navigation_ui()
            self._update_current_selection(self._image_files[self._current_image_index].filepath.name)

    def _on_image_index_changed(self, index: int):
        """Handler for image index changed from external viewer spinbox.
        
        Args:
            index: 0-based image index
        """
        if 0 <= index < len(self._image_files) and index != self._current_image_index:
            self._current_image_index = index
            self._display_dicom_file(self._image_files[self._current_image_index])
            self._update_navigation_ui()
            self._update_current_selection(self._image_files[self._current_image_index].filepath.name)
    

    def eventFilter(self, obj, event: QEvent):
        """
        Event filter for handling wheel events on child widgets.
        Only navigates between images when mouse is over the image viewer area (right column).
        
        Args:
            obj: The watched object
            event: The event
            
        Returns:
            True if event was handled, False otherwise
        """
        if event.type() == QEvent.Type.Wheel:
            # Wheel events are now handled by the external image viewer's signals
            # which are connected to next/prev button handlers
            return False
        return False
    
    def wheelEvent(self, event: QWheelEvent):
        """
        Handle mouse wheel for image navigation (fallback for main window).
        Navigation is now primarily handled by the external viewer's wheel events.
        
        Args:
            event: Wheel event
        """
        # Wheel events are now handled by the external image viewer
        # This fallback is kept for cases where focus is on the main window
        if self._image_files and len(self._image_files) > 1:
            if event.angleDelta().y() > 0:
                self._on_next_button_clicked()
            else:
                self._on_prev_button_clicked()
            event.accept()
        else:
            event.ignore()
    
    def _update_navigation_ui(self):
        """Update navigation in external image viewer."""
        total = len(self._image_files)
        current = self._current_image_index + 1
        
        # Update external viewer's navigation and Z index if it exists
        pixel_table = None
        if (hasattr(self, '_image_tabs') and self._image_tabs is not None and
            hasattr(self._image_tabs, 'pixel_array_table')):
            pixel_table = self._image_tabs.pixel_array_table
        
        if pixel_table is not None:
            # Update Z index in viewer
            pixel_table.set_viewer_z_index(self._current_image_index)
            
            # Update navigation UI in viewer
            viewer = pixel_table._image_viewer
            if viewer is not None:
                viewer.set_navigation(current, total)
                viewer._prev_button.setEnabled(self._current_image_index > 0)
                viewer._next_button.setEnabled(self._current_image_index < total - 1)
    
    def _on_add_measurement(self, measurement: dict):
        """Handler for adding a new measurement.
        
        Args:
            measurement: Dictionary containing measurement data
        """
        # Add to measurements list
        self._measurements.append(measurement)
        
        # Update measurements table
        self._update_measurements_table()
    
    def _on_measurement_cell_changed(self, row: int, column: int):
        """Handler for cell changes in measurements table.
        Updates the note field in the measurement dictionary when edited.
        
        Args:
            row: Row index of the changed cell
            column: Column index of the changed cell
        """
        # Only handle changes in the Note column (column 14)
        if column == 14 and 0 <= row < len(self._measurements):
            item = self._measurements_table.item(row, column)
            if item is not None:
                # Update the note in the measurement dictionary
                self._measurements[row]['note'] = item.text()
    
    def _on_measurement_cell_clicked(self, row: int, column: int):
        """Handler for cell clicks in measurements table.
        Deletes measurement when Delete button is clicked.
        
        Args:
            row: Row index of the clicked cell
            column: Column index of the clicked cell
        """
        # Only handle clicks in the Delete column (column 15)
        if column == 15 and 0 <= row < len(self._measurements):
            # Remove the measurement from the list
            self._measurements.pop(row)
            # Update the table
            self._update_measurements_table()
    
    def _on_export_measurements(self):
        """Export measurements to CSV file."""
        if not self._measurements:
            QMessageBox.information(self, "No Measurements", "No measurements to export.")
            return
        
        # Get save file path
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Measurements",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        # Ensure .csv extension
        if not file_path.lower().endswith('.csv'):
            file_path += '.csv'
        
        try:
            # Get column headers
            headers = []
            for col in range(self._measurements_table.columnCount()):
                header_item = self._measurements_table.horizontalHeaderItem(col)
                headers.append(header_item.text() if header_item else f"Column {col}")
            
            # Write CSV using csv module for proper escaping
            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                
                # Write header row
                writer.writerow(headers)
                
                # Write data rows
                for i, m in enumerate(self._measurements):
                    row = [
                        str(i + 1),  # Index
                        str(m.get('z', '')),  # Z index
                        str(m.get('x', '')),
                        str(m.get('y', '')),
                        str(m.get('cursor_size', '')),
                        "Circle" if m.get('is_circle', False) else "Rectangle",
                        f"{m.get('raw_mean', 0):.2f}",
                        f"{m.get('raw_std', 0):.2f}",
                        f"{m.get('raw_min', 0):.2f}",
                        f"{m.get('raw_max', 0):.2f}",
                        f"{m.get('hu_mean', 0):.2f}",
                        f"{m.get('hu_std', 0):.2f}",
                        f"{m.get('hu_min', 0):.2f}",
                        f"{m.get('hu_max', 0):.2f}",
                        str(m.get('note', '')),  # csv.writer will handle quoting
                        ""  # Delete column is empty in CSV
                    ]
                    writer.writerow(row)
            
            QMessageBox.information(self, "Export Successful", f"Measurements exported to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to export measurements:\n{str(e)}")
    
    def _update_measurements_table(self):
        """Update the measurements table with current measurements."""
        # Clear existing rows
        self._measurements_table.setRowCount(0)
        
        # Add rows for each measurement
        for i, m in enumerate(self._measurements):
            self._measurements_table.insertRow(i)
            
            # Column 0: Index
            self._measurements_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            
            # Column 1: Z index
            self._measurements_table.setItem(i, 1, QTableWidgetItem(str(m.get('z', 0))))
            
            # Column 2: X position
            self._measurements_table.setItem(i, 2, QTableWidgetItem(str(m.get('x', 0))))
            
            # Column 3: Y position
            self._measurements_table.setItem(i, 3, QTableWidgetItem(str(m.get('y', 0))))
            
            # Column 4: Cursor Size
            self._measurements_table.setItem(i, 4, QTableWidgetItem(str(m.get('cursor_size', 0))))
            
            # Column 5: Form (Circle/Rectangle)
            form = "Circle" if m.get('is_circle', False) else "Rectangle"
            self._measurements_table.setItem(i, 5, QTableWidgetItem(form))
            
            # Column 6: Raw Mean
            self._measurements_table.setItem(i, 6, QTableWidgetItem(f"{m.get('raw_mean', 0):.2f}"))
            
            # Column 7: Raw Std
            self._measurements_table.setItem(i, 7, QTableWidgetItem(f"{m.get('raw_std', 0):.2f}"))
            
            # Column 8: Raw Min
            self._measurements_table.setItem(i, 8, QTableWidgetItem(f"{m.get('raw_min', 0):.2f}"))
            
            # Column 9: Raw Max
            self._measurements_table.setItem(i, 9, QTableWidgetItem(f"{m.get('raw_max', 0):.2f}"))
            
            # Column 10: HU Mean
            self._measurements_table.setItem(i, 10, QTableWidgetItem(f"{m.get('hu_mean', 0):.2f}"))
            
            # Column 11: HU Std
            self._measurements_table.setItem(i, 11, QTableWidgetItem(f"{m.get('hu_std', 0):.2f}"))
            
            # Column 12: HU Min
            self._measurements_table.setItem(i, 12, QTableWidgetItem(f"{m.get('hu_min', 0):.2f}"))
            
            # Column 13: HU Max
            self._measurements_table.setItem(i, 13, QTableWidgetItem(f"{m.get('hu_max', 0):.2f}"))
            
            # Column 14: Note (editable)
            note_item = QTableWidgetItem(m.get('note', ''))
            note_item.setFlags(note_item.flags() | Qt.ItemFlag.ItemIsEditable)
            self._measurements_table.setItem(i, 14, note_item)
            
            # Column 15: Delete button
            delete_item = QTableWidgetItem("Delete")
            delete_item.setForeground(QColor(200, 0, 0))
            delete_item.setToolTip("Click to delete this measurement")
            self._measurements_table.setItem(i, 15, delete_item)
    

    

    def _on_overlay_toggled(self, show: bool):
        """
        Handler for overlay toggle signal.
        
        Args:
            show: Whether overlay is now visible
        """
        # Could log this or trigger other UI updates
        pass
    
    def _set_overlay_color(self, color: tuple):
        """Set the overlay color and re-render.
        
        Args:
            color: RGB tuple (r, g, b)
        """
        self._overlay_color = color
        # Update external viewer's color button style
        if (hasattr(self, '_image_tabs') and self._image_tabs is not None and
            hasattr(self._image_tabs, '_pixel_array_table') and
            self._image_tabs._pixel_array_table is not None and
            hasattr(self._image_tabs._pixel_array_table, '_image_viewer')):
            viewer = self._image_tabs._pixel_array_table._image_viewer
            viewer.set_overlay_color(color)
        # Re-render the current image with new color
        if self._current_dicom_file:
            self._display_dicom_file(self._current_dicom_file)
    
    def _update_current_selection(self, filename: Optional[str] = None):
        """
        Update the current selection label.
        
        Args:
            filename: Current file name, or None for default
        """
        if filename:
            # Show image number + filename
            current = self._current_image_index + 1
            total = len(self._image_files)
            self._current_selection_label.setText(f"Image {current}/{total}: {filename}")
            self._current_selection_label.setStyleSheet("")
        else:
            self._current_selection_label.setText("No DICOM directory loaded")
            self._current_selection_label.setStyleSheet("font-style: italic; color: #666;")
