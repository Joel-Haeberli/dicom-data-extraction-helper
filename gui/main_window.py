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
import json
import numpy as np

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QPushButton, QLabel, QSpinBox,
    QHBoxLayout, QVBoxLayout, QMessageBox, QFileDialog,
    QColorDialog, QCheckBox, QTableWidget, QTableWidgetItem,
    QApplication
)
from PySide6.QtCore import Qt, Signal, QSize, QEvent
from PySide6.QtGui import QIcon, QWheelEvent, QColor
from PySide6.QtWidgets import QSizePolicy

from gui.image_tabs import ImageTabs
from gui.curve_view import CurveView
from gui.comparison_window import ComparisonWindow
from gui.utils.dicom_loader import DICOMLoader, DICOMFile
from gui.utils.image_utils import (
    dicom_to_qimage,
    extract_overlay_array,
    overlay_to_qimage, extract_overlay_with_origin,
    get_original_size,
)


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
        self._current_study_uid: str = ''  # Current study UID for linking measurements
        self._current_series_uid: str = ''  # Current series UID for linking measurements
        self._current_curve_row: int = 0  # Current row selected for HU profile curve
        
        # Create UI
        self._create_widgets()
        self._setup_layout()

        # Enable mouse wheel on the central widget
        self._central_widget.setFocusPolicy(Qt.StrongFocus)
        
        # Connect to pixel array table's navigation signals (external window wheel events)
        self._image_tabs.pixel_array_table.next_image_requested.connect(self._on_next_button_clicked)
        self._image_tabs.pixel_array_table.prev_image_requested.connect(self._on_prev_button_clicked)
        self._image_tabs.pixel_array_table.image_index_changed.connect(self._on_image_index_changed)
        self._image_tabs.pixel_array_table.overlay_color_changed.connect(self._set_overlay_color)
        self._image_tabs.pixel_array_table.add_measurement_requested.connect(self._on_add_measurement)
        self._image_tabs.pixel_array_table.window_changed.connect(self._update_curve_from_window)
        
        # Connect curve view row changed signal
        self._curve_view.row_changed.connect(self._on_curve_row_changed)
        
        # Initial state
        self._update_current_selection()
        
        # Set up close event to close external viewer
        self.setAttribute(Qt.WA_DeleteOnClose)
    
    def closeEvent(self, event):
        """Close all windows and exit when the main window is closed."""
        self._image_window.hide()
        event.accept()
        QApplication.quit()

    def _on_show_image_window_clicked(self):
        """Show the image viewer window (re-open if hidden)."""
        self._image_window.show()
        self._image_window.raise_()
        self._image_window.activateWindow()
    
    def _create_widgets(self):
        """Create all child widgets."""
        # Central widget
        self._central_widget = QWidget(self)
        self.setCentralWidget(self._central_widget)
        
        # Top controls - Load button removed, replaced by explorer
        # Show image window button
        self._show_image_window_button = QPushButton("Show Image Window", self)
        self._show_image_window_button.setToolTip("Show the image viewer dock panel (re-open if closed)")
        self._show_image_window_button.clicked.connect(self._on_show_image_window_clicked)
        
        # DICOM Explorer widget
        from gui.explorer import DICOMExplorer
        self._explorer = DICOMExplorer(self)
        self._explorer.directory_selected.connect(self._load_dicom_directory)
        
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
        
        # Curve view (left column, replaces metadata table)
        self._curve_view = CurveView(self)
        
        # Measurements table (below metadata)
        self._measurements_table = QTableWidget(self)
        self._measurements_table.setColumnCount(19)
        self._measurements_table.setHorizontalHeaderLabels([
            "#", "Study", "Image Name", "Z", "X", "Y", "Size", "Form",
            "Raw Mean", "Raw Std", "Raw Min", "Raw Max",
            "HU Mean", "HU Std", "HU Min", "HU Max",
            "mm/px", "Note", "Delete"
        ])
        self._measurements_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed)
        self._measurements_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._measurements_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._measurements_table.horizontalHeader().setStretchLastSection(False)
        
        # Dark mode styling for measurements table
        self._measurements_table.setStyleSheet("""
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
            QTableWidget::item {
                padding: 2px;
            }
        """)
        
        # Set column widths - Note column wider, others reasonable
        self._measurements_table.setColumnWidth(0, 40)   # #
        self._measurements_table.setColumnWidth(1, 120)  # Study
        self._measurements_table.setColumnWidth(2, 150)  # Image Name
        self._measurements_table.setColumnWidth(3, 40)   # Z
        self._measurements_table.setColumnWidth(4, 40)   # X
        self._measurements_table.setColumnWidth(5, 40)   # Y
        self._measurements_table.setColumnWidth(6, 60)   # Size
        self._measurements_table.setColumnWidth(7, 80)   # Form
        self._measurements_table.setColumnWidth(8, 80)   # Raw Mean
        self._measurements_table.setColumnWidth(9, 80)   # Raw Std
        self._measurements_table.setColumnWidth(10, 80)  # Raw Min
        self._measurements_table.setColumnWidth(11, 80)  # Raw Max
        self._measurements_table.setColumnWidth(12, 80)  # HU Mean
        self._measurements_table.setColumnWidth(13, 80)  # HU Std
        self._measurements_table.setColumnWidth(14, 80)  # HU Min
        self._measurements_table.setColumnWidth(15, 80)  # HU Max
        self._measurements_table.setColumnWidth(16, 90)  # mm/px
        self._measurements_table.setColumnWidth(17, 300) # Note - wider
        self._measurements_table.setColumnWidth(18, 60)  # Delete
        
        # Export button for measurements
        self._export_measurements_button = QPushButton("Export Measurements (CSV)", self)
        self._export_measurements_button.setToolTip("Export measurements table to CSV file")
        self._export_measurements_button.clicked.connect(self._on_export_measurements)
        
        # Export button for series region statistics
        self._export_region_series_button = QPushButton("Export Series Region Stats (CSV)", self)
        self._export_region_series_button.setToolTip("Export statistics for the last measured region across all images in the series")
        self._export_region_series_button.clicked.connect(self._on_export_region_series)
        self._export_region_series_button.setEnabled(False)
        
        # Export button for current window HU data
        self._export_current_window_button = QPushButton("Export Current Window (HU)", self)
        self._export_current_window_button.setToolTip("Export Hounsfield Unit data from current table window to CSV")
        self._export_current_window_button.clicked.connect(self._on_export_current_window)
        self._export_current_window_button.setEnabled(False)
        
        # Save / Load buttons for measurements
        self._save_measurements_button = QPushButton("Save Measurements", self)
        self._save_measurements_button.setToolTip("Save all measurements to a JSON file")
        self._save_measurements_button.clicked.connect(self._on_save_measurements)

        self._load_measurements_button = QPushButton("Load Measurements", self)
        self._load_measurements_button.setToolTip("Load measurements from a JSON file (appends to current list)")
        self._load_measurements_button.clicked.connect(self._on_load_measurements)

        # Connect cell change signal to update notes
        self._measurements_table.cellChanged.connect(self._on_measurement_cell_changed)
        # Connect cell click signal for delete button
        self._measurements_table.cellClicked.connect(self._on_measurement_cell_clicked)
        
        # Image tabs (right column) - contains pixel array table
        self._image_tabs = ImageTabs(self)

        # Image viewer - standalone OS window that hides on close (preserves state)
        image_viewer_widget = self._image_tabs.create_image_viewer()
        self._image_window = QWidget(None, Qt.Window)
        self._image_window.setWindowTitle("Image Viewer")
        window_layout = QVBoxLayout(self._image_window)
        window_layout.setContentsMargins(0, 0, 0, 0)
        window_layout.addWidget(image_viewer_widget)
        self._image_window.closeEvent = lambda e: (e.ignore(), self._image_window.hide())
        self._image_window.resize(800, 700)

        # Connect profile-view "load different image" signal
        pv = self._image_tabs.pixel_array_table._profile_view
        if pv is not None:
            pv.load_file_requested.connect(self._on_profile_load_file)

    def _setup_layout(self):
        """Setup the main layout."""
        # Main layout for central widget
        main_layout = QVBoxLayout(self._central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)
        
        # Top row: Show Image Window button + current selection (Load button removed)
        top_layout = QHBoxLayout()
        top_layout.addWidget(self._show_image_window_button, 0)
        top_layout.addWidget(self._current_selection_label, 1)
        top_layout.addStretch(1)
        
        # Main columns area
        columns_layout = QHBoxLayout()
        columns_layout.setContentsMargins(0, 0, 0, 0)
        columns_layout.setSpacing(8)
        
        # Left column: Explorer + Metadata (split vertically, 1/3 width)
        left_column = QWidget()
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        
        # DICOM Explorer (top of left column, minimal height)
        left_layout.addWidget(self._explorer, 0)
        
        # Curve view (bottom of left column, takes remaining space)
        left_layout.addWidget(self._curve_view, 1)
        
        columns_layout.addWidget(left_column, 1)
        
        # Right column: Image tabs with image viewer and pixel array table (2/3 width)
        columns_layout.addWidget(self._image_tabs, 2)
        
        # Measurements table spans full width below columns
        measurements_layout = QVBoxLayout()
        measurements_layout.addWidget(self._measurements_table, 1)
        
        # Export buttons layout
        export_layout = QHBoxLayout()
        export_layout.addWidget(self._export_measurements_button, 0)
        export_layout.addWidget(self._export_current_window_button, 0)
        export_layout.addWidget(self._export_region_series_button, 0)
        
        # Compare Measurement Curves button
        self._compare_curves_button = QPushButton("Compare Measurement Curves", self)
        self._compare_curves_button.setToolTip("Open comparison window to view multiple measurement curves")
        self._compare_curves_button.clicked.connect(self._on_compare_curves)
        self._compare_curves_button.setEnabled(False)
        export_layout.addWidget(self._compare_curves_button, 0)
        
        export_layout.addStretch(1)

        # Save / Load buttons row
        session_layout = QHBoxLayout()
        session_layout.addWidget(self._save_measurements_button, 0)
        session_layout.addWidget(self._load_measurements_button, 0)
        session_layout.addStretch(1)

        measurements_layout.addLayout(export_layout, 0)
        measurements_layout.addLayout(session_layout, 0)
        
        # Combine layouts
        main_layout.addLayout(top_layout, 0)
        main_layout.addLayout(columns_layout, 1)
        main_layout.addLayout(measurements_layout, 0)

        # Show image viewer window on startup
        self._image_window.show()
    
    def _load_dicom_directory(self, directory: Path):
        """
        Load DICOM files from the specified directory.
        
        Args:
            directory: Path to directory containing DICOM files
        """
        try:
            # Clear previous state (but NOT measurements - they are preserved)
            self._curve_view.clear()
            self._image_tabs.clear()
            self._export_current_window_button.setEnabled(False)
            self._export_region_series_button.setEnabled(False)
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
                # Clear study UIDs since no images loaded
                self._current_study_uid = ''
                self._current_series_uid = ''
                return
            
            # Store current study/series UIDs for linking new measurements
            if self._image_files[0].dataset:
                ds = self._image_files[0].dataset
                self._current_study_uid = getattr(ds, 'StudyInstanceUID', 'Unknown')
                self._current_series_uid = getattr(ds, 'SeriesInstanceUID', 'Unknown')
            else:
                self._current_study_uid = 'Unknown'
                self._current_series_uid = 'Unknown'
            
            # Update measurements table to reflect current study
            self._update_measurements_table()
            
            # Build 3D volume in the new tab
            self._image_tabs.set_series(self._image_files)

            # Display the first image
            self._display_dicom_file(self._image_files[0])
            
            # Update navigation UI
            self._update_navigation_ui()
            self._update_current_selection(self._image_files[0].filepath.name)
            
            # Enable series region export and compare curves if we have measurements
            if self._measurements:
                self._export_region_series_button.setEnabled(True)
                self._compare_curves_button.setEnabled(True)
            
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

        # Display image and pixel data
        if dicom_file.dataset and dicom_file.is_image:
            # Set dataset on image tabs (handles both image and lazy pixel data loading)
            self._image_tabs.set_dataset(dicom_file.dataset)

            # Sync 3D view slice
            self._image_tabs.set_current_slice(self._current_image_index)

            # Tell the profile view which file is now active
            pv = self._image_tabs.pixel_array_table._profile_view
            if pv is not None:
                pv.set_image_path(str(dicom_file.filepath))

            # Try to find and display overlay
            self._load_overlay_for_current_file()

            # Update curve view with first row of default window
            self._update_curve_from_window()
    
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
    

    def _on_profile_load_file(self, path: str):
        """Load a specific DICOM file by path (requested from profile-view measurement click)."""
        target = Path(path)

        def _try_navigate() -> bool:
            for match_fn in (lambda f: f.filepath == target,
                             lambda f: f.filepath.name == target.name):
                for i, img_file in enumerate(self._image_files):
                    if match_fn(img_file):
                        if i != self._current_image_index:
                            self._current_image_index = i
                            self._display_dicom_file(img_file)
                            self._update_navigation_ui()
                            self._update_current_selection(img_file.filepath.name)
                        return True
            return False

        if _try_navigate():
            return

        # Not in the current series — if the file exists, load its directory first.
        if target.exists() and target.parent.is_dir():
            self._load_dicom_directory(target.parent)
            if _try_navigate():
                return

        QMessageBox.warning(
            self, "Image Not Found",
            f"The measurement's image was not found:\n{target.name}\n\n"
            f"Please load the DICOM directory that contains this file."
        )

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

            # Update navigation UI in image viewer
            viewer = pixel_table._image_viewer
            if viewer is not None:
                viewer.set_navigation(current, total)
                viewer._prev_button.setEnabled(self._current_image_index > 0)
                viewer._next_button.setEnabled(self._current_image_index < total - 1)

            # Update navigation spinbox in profile view
            if pixel_table._profile_view is not None:
                pixel_table._profile_view.set_navigation(current, total)
    
    def _on_add_measurement(self, measurement: dict):
        """Handler for adding a new measurement.
        
        Args:
            measurement: Dictionary containing measurement data
        """
        # Add image filename to measurement based on physical Z coordinate
        z_physical = measurement.get('z', 0.0)
        # Find the image file with matching Z coordinate
        for img_file in self._image_files:
            img_z = img_file.image_coordinates.get('z', 0.0)
            if abs(img_z - z_physical) < 0.001:  # Floating point comparison with tolerance
                measurement['image_name'] = img_file.filepath.name
                break
        else:
            measurement['image_name'] = ''
        
        # Add study/series linking information
        if self._current_dicom_file and self._current_dicom_file.dataset:
            ds = self._current_dicom_file.dataset
            measurement['study_uid'] = getattr(ds, 'StudyInstanceUID', 'Unknown')
            measurement['series_uid'] = getattr(ds, 'SeriesInstanceUID', 'Unknown')
            measurement['study_description'] = getattr(ds, 'StudyDescription', '') or getattr(ds, 'StudyID', '')
        else:
            # Fallback to current study UIDs if available
            measurement['study_uid'] = self._current_study_uid if self._current_study_uid else 'Unknown'
            measurement['series_uid'] = self._current_series_uid if self._current_series_uid else 'Unknown'
            measurement['study_description'] = ''
        
        # Add row for curve comparison (use current curve row)
        measurement['row'] = self._current_curve_row if hasattr(self, '_current_curve_row') else 0
        
        # Add to measurements list
        self._measurements.append(measurement)
        
        # Update measurements table
        self._update_measurements_table()
        
        # Enable export buttons if we have measurements
        if self._measurements:
            self._export_region_series_button.setEnabled(True)
            self._compare_curves_button.setEnabled(True)
        # Current window export is enabled when we have pixel data
        if hasattr(self._image_tabs.pixel_array_table, '_pixel_array') and self._image_tabs.pixel_array_table._pixel_array is not None:
            self._export_current_window_button.setEnabled(True)
    
    def _on_measurement_cell_changed(self, row: int, column: int):
        """Handler for cell changes in measurements table.
        Updates the note field in the measurement dictionary when edited.
        
        Args:
            row: Row index of the changed cell
            column: Column index of the changed cell
        """
        # Only handle changes in the Note column (column 17)
        if column == 17 and 0 <= row < len(self._measurements):
            item = self._measurements_table.item(row, column)
            if item is not None:
                # Update the note in the measurement dictionary
                self._measurements[row]['note'] = item.text()
    
    def _on_measurement_cell_clicked(self, row: int, column: int):
        """Handler for cell clicks in measurements table.
        Deletes measurement when Delete button is clicked.
        Resets window to measurement when any other cell is clicked.
        
        Args:
            row: Row index of the clicked cell
            column: Column index of the clicked cell
        """
        if 0 <= row < len(self._measurements):
            # Handle Delete column
            if column == 18:
                # Remove the measurement from the list
                self._measurements.pop(row)
                # Update the table
                self._update_measurements_table()
                # Update export button states
                if not self._measurements:
                    self._export_region_series_button.setEnabled(False)
                    self._compare_curves_button.setEnabled(False)
            else:
                # For any other column: reset measurement window to this measurement
                measurement = self._measurements[row]
                self._reset_window_to_measurement(measurement)
    
    def _reset_window_to_measurement(self, measurement: dict):
        """Reset the pixel array table window to match a measurement.
        
        The measurement's x,y are the CENTER of the window.
        This converts them to top-left corner coordinates and sets the window.
        Only applies if the measurement belongs to the current study.
        
        Args:
            measurement: Measurement dictionary with x, y, cursor_size, is_circle, study_uid
        """
        if not hasattr(self, '_image_tabs') or self._image_tabs is None:
            return
        
        # Skip if measurement is from a different study
        measurement_study_uid = measurement.get('study_uid', '')
        if measurement_study_uid and measurement_study_uid != self._current_study_uid:
            # Measurement belongs to a different study - do not apply
            return
        
        pixel_table = self._image_tabs.pixel_array_table
        if pixel_table is None or pixel_table._pixel_array is None:
            return
        
        # Get measurement parameters
        center_x = measurement.get('x', 0)
        center_y = measurement.get('y', 0)
        cursor_size = measurement.get('cursor_size', 7)
        is_circle = measurement.get('is_circle', False)
        
        # Get array dimensions
        arr = pixel_table._pixel_array[0] if pixel_table._pixel_array.ndim == 3 else pixel_table._pixel_array
        rows = arr.shape[0]
        cols = arr.shape[1]
        
        # Ensure cursor_size is odd for proper centering
        actual_cursor_size = max(1, cursor_size)
        if actual_cursor_size % 2 == 0:
            actual_cursor_size += 1
        half_size = actual_cursor_size // 2
        
        # Calculate top-left of window from center
        win_x = max(0, min(center_x - half_size, cols - actual_cursor_size)) if cols >= actual_cursor_size else 0
        win_y = max(0, min(center_y - half_size, rows - actual_cursor_size)) if rows >= actual_cursor_size else 0
        win_w = min(actual_cursor_size, cols)
        win_h = min(actual_cursor_size, rows)
        
        # Set the window in the pixel array table
        pixel_table._window_x = win_x
        pixel_table._window_y = win_y
        pixel_table._window_width = win_w
        pixel_table._window_height = win_h

        # Keep cursor_window_size in sync so next cursor movement doesn't revert the window
        pixel_table._cursor_window_size = actual_cursor_size
        if pixel_table._cursor_size_spin is not None:
            pixel_table._cursor_size_spin.blockSignals(True)
            pixel_table._cursor_size_spin.setValue(actual_cursor_size)
            pixel_table._cursor_size_spin.blockSignals(False)

        # Update spin boxes
        pixel_table._win_x_spin.setValue(win_x)
        pixel_table._win_y_spin.setValue(win_y)
        pixel_table._win_width_spin.setValue(win_w)
        pixel_table._win_height_spin.setValue(win_h)
        
        # Update cursor mode in viewer
        if pixel_table._image_viewer is not None:
            pixel_table._image_viewer.set_cursor_mode_circle(is_circle)
        
        # Update highlight region and models
        pixel_table._update_highlight_region()
        pixel_table._update_models()
        
        # Update cursor rectangle on viewer
        if pixel_table._image_viewer is not None:
            pixel_table._image_viewer.set_cursor_rect(win_x, win_y, win_w, win_h)
        
        # Emit window changed signal to update curve
        pixel_table.window_changed.emit()
    
    def _on_curve_row_changed(self, row: int):
        """Handler for curve view row selector changes.
        
        Args:
            row: The newly selected row index (relative to window)
        """
        self._current_curve_row = row
        # Trigger curve update with the new row
        self._update_curve_from_window()
    
    def _update_curve_from_window(self):
        """Update curve view with the selected row of current window (or zoomed table)."""
        if not hasattr(self, '_curve_view') or self._curve_view is None:
            return
        
        pixel_table = self._image_tabs.pixel_array_table
        if pixel_table is None:
            self._curve_view.clear()
            return
        
        # Get the selected row (relative to window, defaults to 0)
        selected_row = self._current_curve_row if hasattr(self, '_current_curve_row') else 0
        
        # Use zoomed table if available and zoom > 1
        if pixel_table._zoom_factor > 1 and pixel_table._zoomed_table is not None:
            zoomed = pixel_table._zoomed_table

            # Clamp selected row to valid range
            if selected_row < 0:
                selected_row = 0
            if selected_row >= len(zoomed):
                selected_row = max(0, len(zoomed) - 1)

            row_data = zoomed[selected_row]

            # X values are indices relative to window start (0-based)
            x_values = [i for i in range(len(row_data))]

            hu_values = list(row_data)

            # Set row in title - use absolute Y position (window start + selected row)
            absolute_row = pixel_table._window_y + selected_row * pixel_table._zoom_factor
            self._curve_view.set_row_range(0, len(zoomed) - 1)
            self._curve_view.set_row(selected_row, absolute_row)
            
            self._curve_view.set_data(x_values, hu_values)
            
        else:
            # Original logic for factor = 1 (no zoom)
            if pixel_table._pixel_array is None:
                self._curve_view.clear()
                return
            
            arr = pixel_table._pixel_array[0] if pixel_table._pixel_array.ndim == 3 else pixel_table._pixel_array
            
            win_x = pixel_table._window_x
            win_y = pixel_table._window_y
            win_w = pixel_table._window_width
            win_h = pixel_table._window_height
            
            # Clamp window to array bounds
            rows = arr.shape[0]
            cols = arr.shape[1]
            win_x = max(0, min(win_x, cols - 1))
            win_y = max(0, min(win_y, rows - 1))
            win_w = max(1, min(win_w, cols - win_x))
            win_h = max(1, min(win_h, rows - win_y))
            
            # Extract the selected row from the window
            region = arr[win_y:win_y + win_h, win_x:win_x + win_w]
            if region.size == 0:
                self._curve_view.clear()
                return
            
            # Clamp selected row to valid range
            if selected_row < 0:
                selected_row = 0
            if selected_row >= region.shape[0]:
                selected_row = max(0, region.shape[0] - 1)
            
            row_data = region[selected_row]
            
            # Get HU conversion parameters
            slope = getattr(pixel_table._dataset, 'RescaleSlope', 1.0) if pixel_table._dataset else 1.0
            intercept = getattr(pixel_table._dataset, 'RescaleIntercept', 0.0) if pixel_table._dataset else 0.0
            
            # Convert to HU
            hu_values = [float(v) * slope + intercept for v in row_data]
            
            # X values (relative to window start, 0-based)
            x_values = [i for i in range(len(row_data))]
            
            # Set row in title - use absolute Y position
            absolute_row = win_y + selected_row
            self._curve_view.set_row_range(0, max(0, region.shape[0] - 1))
            self._curve_view.set_row(selected_row, absolute_row)
            
            self._curve_view.set_data(x_values, hu_values)
    
    @staticmethod
    def _measurement_json_default(obj):
        """JSON serialization fallback for non-standard types in measurement dicts."""
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, tuple):
            return list(obj)
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    def _on_save_measurements(self):
        """Save all measurements to a JSON file."""
        if not self._measurements:
            QMessageBox.information(self, "No Measurements", "No measurements to save.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Measurements", "", "JSON Files (*.json);;All Files (*)"
        )
        if not file_path:
            return
        if not file_path.lower().endswith('.json'):
            file_path += '.json'

        try:
            payload = {
                "version": 1,
                "measurements": self._measurements,
            }
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2, default=self._measurement_json_default)
            QMessageBox.information(
                self, "Saved",
                f"Saved {len(self._measurements)} measurement(s) to:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", f"Failed to save measurements:\n{str(e)}")

    def _on_load_measurements(self):
        """Load measurements from a JSON file and append to the current list."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Measurements", "", "JSON Files (*.json);;All Files (*)"
        )
        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                payload = json.load(f)

            if not isinstance(payload, dict) or 'measurements' not in payload:
                QMessageBox.warning(
                    self, "Invalid File",
                    "The selected file does not contain valid measurement data."
                )
                return

            loaded: list = payload['measurements']
            if not isinstance(loaded, list):
                QMessageBox.warning(self, "Invalid File", "Measurements entry is not a list.")
                return

            # Restore pixel_spacing as a tuple (JSON serializes tuples as arrays)
            for m in loaded:
                ps = m.get('pixel_spacing')
                if isinstance(ps, list) and len(ps) == 2:
                    m['pixel_spacing'] = tuple(ps)
                elif ps is not None and not isinstance(ps, tuple):
                    m['pixel_spacing'] = None  # discard unrecognised format

            count = len(loaded)
            self._measurements.extend(loaded)
            self._update_measurements_table()

            if self._measurements:
                self._export_region_series_button.setEnabled(True)
                self._compare_curves_button.setEnabled(True)

            QMessageBox.information(
                self, "Loaded",
                f"Loaded {count} measurement(s) from:\n{file_path}\n\n"
                f"Total measurements: {len(self._measurements)}"
            )
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "Load Failed", f"File is not valid JSON:\n{str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "Load Failed", f"Failed to load measurements:\n{str(e)}")

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
                    study_desc = m.get('study_description', '')
                    study_uid = m.get('study_uid', '')
                    study_text = study_desc if study_desc else study_uid[:8] if study_uid else 'Unknown'
                    ps = m.get('pixel_spacing', None)
                    if ps is not None:
                        row_mm, col_mm = ps
                        ps_csv = f"{row_mm:.6f}" if abs(row_mm - col_mm) < 1e-6 else f"{row_mm:.6f}/{col_mm:.6f}"
                    else:
                        ps_csv = ""
                    row = [
                        str(i + 1),                                           # #
                        study_text,                                           # Study
                        str(m.get('image_name', '')),                        # Image Name
                        f"{m.get('z', 0.0):.2f}",                           # Z
                        str(m.get('x', '')),                                 # X
                        str(m.get('y', '')),                                 # Y
                        str(m.get('cursor_size', '')),                       # Size
                        "Circle" if m.get('is_circle', False) else "Rectangle",  # Form
                        f"{m.get('raw_mean', 0):.2f}",                      # Raw Mean
                        f"{m.get('raw_std', 0):.2f}",                       # Raw Std
                        f"{m.get('raw_min', 0):.2f}",                       # Raw Min
                        f"{m.get('raw_max', 0):.2f}",                       # Raw Max
                        f"{m.get('hu_mean', 0):.2f}",                       # HU Mean
                        f"{m.get('hu_std', 0):.2f}",                        # HU Std
                        f"{m.get('hu_min', 0):.2f}",                        # HU Min
                        f"{m.get('hu_max', 0):.2f}",                        # HU Max
                        ps_csv,                                              # mm/px
                        str(m.get('note', '')),                              # Note
                        "",                                                   # Delete (empty in CSV)
                    ]
                    writer.writerow(row)
            
            QMessageBox.information(self, "Export Successful", f"Measurements exported to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to export measurements:\n{str(e)}")
    
    def _on_compare_curves(self):
        """Open the comparison window for measurement curves."""
        if not self._measurements:
            QMessageBox.information(self, "No Measurements", "No measurements to compare.")
            return
        
        # Get the current DICOM dataset for image display
        dataset = None
        if self._current_dicom_file is not None:
            dataset = self._current_dicom_file.dataset
        
        # Open comparison window
        self._comparison_window = ComparisonWindow(
            self._measurements, dataset, self._image_files, self)
        self._comparison_window.show()
    
    def _on_export_region_series(self):
        """Export region statistics across all images in the series."""
        from gui.utils.image_utils import analyze_region_across_series, export_region_series_to_csv
        
        # Check if we have images loaded
        if not self._image_files:
            QMessageBox.information(self, "No Images", "No images loaded. Please load a DICOM directory first.")
            return
        
        # Check if we have any measurements
        if not self._measurements:
            QMessageBox.information(self, "No Measurements", "No measurements defined. Please use the measurement tool to define a region first.")
            return
        
        # Use the last measurement (most recent)
        last_measurement = self._measurements[-1]
        
        # Extract region definition from measurement
        region_def = {
            'x': last_measurement.get('x', 0),
            'y': last_measurement.get('y', 0),
            'size': last_measurement.get('cursor_size', 7),
            'is_circle': last_measurement.get('is_circle', True),
        }
        
        # Analyze region across all images
        results = analyze_region_across_series(self._image_files, region_def)
        
        if not results:
            QMessageBox.information(self, "No Results", "No results were generated. Check that all images are valid.")
            return
        
        # Get save file path
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Series Region Statistics",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        # Ensure .csv extension
        if not file_path.lower().endswith('.csv'):
            file_path += '.csv'
        
        # Export to CSV
        success = export_region_series_to_csv(results, file_path)
        
        if success:
            QMessageBox.information(
                self,
                "Export Successful",
                f"Region statistics exported for {len(results)} images to:\n{file_path}"
            )
        else:
            QMessageBox.critical(self, "Export Failed", "Failed to export region statistics to CSV.")
    
    def _on_export_current_window(self):
        """Export Hounsfield Unit (HU) data from current table window to CSV.
        
        CSV format:
        - Header row: column numbers
        - First column: row numbers  
        - Data: HU values from current window
        """
        # Get the pixel array table
        pixel_table = self._image_tabs.pixel_array_table
        
        if pixel_table._pixel_array is None or pixel_table._dataset is None:
            QMessageBox.information(self, "No Data", "No pixel data loaded to export.")
            return
        
        # Get HU conversion parameters
        slope = getattr(pixel_table._dataset, 'RescaleSlope', 1.0)
        intercept = getattr(pixel_table._dataset, 'RescaleIntercept', 0.0)
        
        # If no HU conversion available, use raw values
        has_hu = slope != 1.0 or intercept != 0.0
        
        # Get save file path
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Current Window (HU)",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        # Ensure .csv extension
        if not file_path.lower().endswith('.csv'):
            file_path += '.csv'
        
        try:
            # Get current window parameters from pixel array table
            win_x = pixel_table._window_x
            win_y = pixel_table._window_y
            win_w = pixel_table._window_width
            win_h = pixel_table._window_height
            
            # Get pixel array (use first frame for 3D)
            arr = pixel_table._pixel_array[0] if pixel_table._pixel_array.ndim == 3 else pixel_table._pixel_array
            
            # Clamp window to array bounds
            rows, cols = arr.shape
            win_x = max(0, min(win_x, cols - win_w)) if win_w > 0 else 0
            win_y = max(0, min(win_y, rows - win_h)) if win_h > 0 else 0
            win_w = min(win_w, cols - win_x)
            win_h = min(win_h, rows - win_y)
            
            if win_w <= 0 or win_h <= 0:
                QMessageBox.information(self, "Invalid Window", "Current window has invalid dimensions.")
                return
            
            # Extract the window region
            region = arr[win_y:win_y + win_h, win_x:win_x + win_w]
            
            # Check if we're in circle mode and have a viewer
            is_circle = False
            if pixel_table._image_viewer is not None and hasattr(pixel_table._image_viewer, '_cursor_mode_circle'):
                is_circle = pixel_table._image_viewer._cursor_mode_circle
            
            # For circle mode, apply mask
            is_flattened = False
            if is_circle and win_w > 0 and win_h > 0:
                center_x = win_w / 2.0
                center_y = win_h / 2.0
                diameter = min(win_w, win_h)
                radius = diameter / 2.0
                radius_sq = radius * radius
                
                yy, xx = np.ogrid[:win_h, :win_w]
                mask = (xx + 0.5 - center_x)**2 + (yy + 0.5 - center_y)**2 <= radius_sq
                region = region[mask]
                is_flattened = True
            
            # Write CSV
            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                
                if is_flattened and region.ndim == 1:
                    # Circle mode: flattened 1D array
                    # Export as single column with HU values
                    header = ['Index', 'HU Value']
                    writer.writerow(header)
                    for idx, value in enumerate(region):
                        hu_value = float(value) * slope + intercept
                        writer.writerow([str(idx), f"{hu_value:.2f}"])
                else:
                    # Standard 2D array export
                    # Header: Row + column numbers
                    header = ['Row'] + [str(j) for j in range(win_x, win_x + region.shape[1])]
                    writer.writerow(header)
                    
                    # Data rows: row number + HU values
                    for row_idx in range(region.shape[0]):
                        row_data = [str(win_y + row_idx)]
                        for col_idx in range(region.shape[1]):
                            hu_value = float(region[row_idx, col_idx]) * slope + intercept
                            row_data.append(f"{hu_value:.2f}")
                        writer.writerow(row_data)
            
            QMessageBox.information(self, "Export Successful", f"Current window exported to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to export current window:\n{str(e)}")
    
    def _update_measurements_table(self):
        """Update the measurements table with current measurements."""
        self._measurements_table.blockSignals(True)
        try:
            self._measurements_table.setRowCount(0)

            for i, m in enumerate(self._measurements):
                self._measurements_table.insertRow(i)

                # Column 0: Index
                self._measurements_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))

                # Column 1: Study (shortened display)
                study_desc = m.get('study_description', '')
                study_uid = m.get('study_uid', '')
                study_text = study_desc if study_desc else study_uid[:8] if study_uid else 'Unknown'
                self._measurements_table.setItem(i, 1, QTableWidgetItem(str(study_text)))
                self._measurements_table.item(i, 1).setToolTip(f"Study: {study_uid}\nSeries: {m.get('series_uid', '')}")

                # Column 2: Image Name
                self._measurements_table.setItem(i, 2, QTableWidgetItem(str(m.get('image_name', ''))))

                # Column 3: Z (physical coordinate)
                z_val = m.get('z', 0.0)
                self._measurements_table.setItem(i, 3, QTableWidgetItem(f"{z_val:.2f}"))

                # Column 4: X position
                self._measurements_table.setItem(i, 4, QTableWidgetItem(str(m.get('x', 0))))

                # Column 5: Y position
                self._measurements_table.setItem(i, 5, QTableWidgetItem(str(m.get('y', 0))))

                # Column 6: Cursor Size
                self._measurements_table.setItem(i, 6, QTableWidgetItem(str(m.get('cursor_size', 0))))

                # Column 7: Form (Circle/Rectangle)
                form = "Circle" if m.get('is_circle', False) else "Rectangle"
                self._measurements_table.setItem(i, 7, QTableWidgetItem(form))

                # Column 8: Raw Mean
                self._measurements_table.setItem(i, 8, QTableWidgetItem(f"{m.get('raw_mean', 0):.2f}"))

                # Column 9: Raw Std
                self._measurements_table.setItem(i, 9, QTableWidgetItem(f"{m.get('raw_std', 0):.2f}"))

                # Column 10: Raw Min
                self._measurements_table.setItem(i, 10, QTableWidgetItem(f"{m.get('raw_min', 0):.2f}"))

                # Column 11: Raw Max
                self._measurements_table.setItem(i, 11, QTableWidgetItem(f"{m.get('raw_max', 0):.2f}"))

                # Column 12: HU Mean
                self._measurements_table.setItem(i, 12, QTableWidgetItem(f"{m.get('hu_mean', 0):.2f}"))

                # Column 13: HU Std
                self._measurements_table.setItem(i, 13, QTableWidgetItem(f"{m.get('hu_std', 0):.2f}"))

                # Column 14: HU Min
                self._measurements_table.setItem(i, 14, QTableWidgetItem(f"{m.get('hu_min', 0):.2f}"))

                # Column 15: HU Max
                self._measurements_table.setItem(i, 15, QTableWidgetItem(f"{m.get('hu_max', 0):.2f}"))

                # Column 16: Pixel spacing (mm/px)
                ps = m.get('pixel_spacing', None)
                if ps is not None:
                    row_mm, col_mm = ps
                    if abs(row_mm - col_mm) < 1e-6:
                        ps_text = f"{row_mm:.4f}"
                    else:
                        ps_text = f"{row_mm:.4f}/{col_mm:.4f}"
                else:
                    ps_text = "N/A"
                ps_item = QTableWidgetItem(ps_text)
                if ps is not None:
                    ps_item.setToolTip(f"Row: {ps[0]:.6f} mm/px  Col: {ps[1]:.6f} mm/px")
                self._measurements_table.setItem(i, 16, ps_item)

                # Column 17: Note (editable)
                note_item = QTableWidgetItem(m.get('note', ''))
                note_item.setFlags(note_item.flags() | Qt.ItemFlag.ItemIsEditable)
                self._measurements_table.setItem(i, 17, note_item)

                # Column 18: Delete button
                delete_item = QTableWidgetItem("Delete")
                delete_item.setForeground(QColor(200, 0, 0))
                delete_item.setToolTip("Click to delete this measurement")
                self._measurements_table.setItem(i, 18, delete_item)
        finally:
            self._measurements_table.blockSignals(False)
    

    

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
            hasattr(self._image_tabs, 'pixel_array_table') and
            self._image_tabs.pixel_array_table is not None and
            hasattr(self._image_tabs.pixel_array_table, '_image_viewer')):
            viewer = self._image_tabs.pixel_array_table._image_viewer
            if viewer is not None and hasattr(viewer, 'set_overlay_color'):
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
