#!/usr/bin/env python3
"""
PACS Browser for DICOM Data Extraction Helper

Provides UI for browsing and querying PACS studies, series, and images.
"""

import threading
from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt, Signal, QSize, QThread
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QLineEdit, QPushButton, QLabel, QComboBox, QProgressBar,
    QMessageBox, QFrame, QSplitter
)
from PySide6.QtGui import QIcon

from gui.utils.pacs_client import (
    PACSClient, PACSConfig, DICOMQueryResult, 
    QueryLevel, ConnectionStatus, RetrievalResult
)
from gui.utils.dicom_loader import DICOMLoader, DICOMFile
from pathlib import Path


class PACSQueryThread(QThread):
    """Thread for running PACS queries without blocking the UI."""
    
    query_complete = Signal(List[DICOMQueryResult])
    error_occurred = Signal(str)
    
    def __init__(self, client: PACSClient, level: QueryLevel, **kwargs):
        super().__init__()
        self._client = client
        self._level = level
        self._kwargs = kwargs
    
    def run(self):
        try:
            results = self._client.query(self._level, **self._kwargs)
            self.query_complete.emit(results)
        except Exception as e:
            self.error_occurred.emit(str(e))


class PACSRetrievalThread(QThread):
    """Thread for retrieving DICOM files from PACS."""
    
    retrieval_complete = Signal(RetrievalResult)
    progress_updated = Signal(int, int)  # current, total
    
    def __init__(self, client: PACSClient, series_uid: str, study_uid: str = ""):
        super().__init__()
        self._client = client
        self._series_uid = series_uid
        self._study_uid = study_uid
    
    def run(self):
        result = self._client.retrieve_series(
            series_uid=self._series_uid,
            study_uid=self._study_uid
        )
        self.retrieval_complete.emit(result)


class PACSBrowser(QWidget):
    """
    Widget for browsing PACS studies, series, and images.
    
    Provides:
    - Search functionality for patients/studies
    - Hierarchical view of PACS data
    - Series retrieval to local storage
    - Integration with existing DICOMLoader
    """
    
    files_retrieved = Signal(List[Path])
    
    def __init__(self, client: PACSClient, parent=None):
        """
        Initialize the PACS browser.
        
        Args:
            client: PACSClient instance for PACS operations
            parent: Parent widget
        """
        super().__init__(parent)
        self._client = client
        self._dicom_loader = DICOMLoader()
        
        # State
        self._current_patients: List[DICOMQueryResult] = []
        self._current_studies: Dict[str, List[DICOMQueryResult]] = {}  # patient_id -> studies
        self._current_series: Dict[str, List[DICOMQueryResult]] = {}  # study_uid -> series
        self._current_images: Dict[str, List[DICOMQueryResult]] = {}  # series_uid -> images
        
        # UI
        self._setup_ui()
        self._connect_signals()
        
        # Setup client callbacks
        self._client.set_status_change_callback(self._on_status_change)
        self._client.set_query_result_callback(self._on_query_result)
    
    def _setup_ui(self):
        """Set up the user interface."""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)
        
        # Search bar
        search_widget = self._create_search_widget()
        main_layout.addWidget(search_widget)
        
        # Status bar
        self._status_bar = self._create_status_bar()
        main_layout.addWidget(self._status_bar)
        
        # Results tree
        self._results_tree = QTreeWidget()
        self._results_tree.setHeaderLabels(["Name", "ID/UID", "Date", "Modality", "Type"])
        self._results_tree.setColumnCount(5)
        self._results_tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        self._results_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._results_tree.setIconSize(QSize(16, 16))
        
        # Configure column widths
        self._results_tree.setColumnWidth(0, 250)  # Name
        self._results_tree.setColumnWidth(1, 200)  # ID/UID
        self._results_tree.setColumnWidth(2, 100)  # Date
        self._results_tree.setColumnWidth(3, 80)   # Modality
        self._results_tree.setColumnWidth(4, 80)   # Type
        
        main_layout.addWidget(self._results_tree)
        
        # Action buttons
        action_widget = self._create_action_widget()
        main_layout.addWidget(action_widget)
        
        self.setLayout(main_layout)
    
    def _create_search_widget(self) -> QWidget:
        """Create the search widget."""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Search type selector
        self._search_type_combo = QComboBox()
        self._search_type_combo.addItems([
            "Patients",
            "Studies",
            "Series",
            "Images"
        ])
        self._search_type_combo.setCurrentIndex(0)
        self._search_type_combo.setMaximumWidth(120)
        
        # Search input
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Enter search term (e.g., patient name, ID, or leave blank for all)")
        
        # Search button
        self._search_button = QPushButton("Search")
        self._search_button.setIcon(QIcon.fromTheme("edit-find"))
        
        # Advanced options button
        self._advanced_button = QPushButton("Advanced...")
        self._advanced_button.setIcon(QIcon.fromTheme("configure"))
        
        layout.addWidget(QLabel("Search:"))
        layout.addWidget(self._search_type_combo)
        layout.addWidget(self._search_input)
        layout.addWidget(self._search_button)
        layout.addWidget(self._advanced_button)
        layout.addStretch()
        
        widget.setLayout(layout)
        return widget
    
    def _create_status_bar(self) -> QWidget:
        """Create the status bar widget."""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)
        
        # Connection status
        self._connection_status_label = QLabel("Disconnected")
        self._connection_status_label.setStyleSheet("color: #666;")
        
        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setMaximumHeight(20)
        
        # Status message
        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet("color: #666;")
        
        layout.addWidget(self._connection_status_label)
        layout.addWidget(self._progress_bar)
        layout.addWidget(self._status_label)
        layout.addStretch()
        
        widget.setLayout(layout)
        return widget
    
    def _create_action_widget(self) -> QWidget:
        """Create the action buttons widget."""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Load selected button
        self._load_button = QPushButton("Load Selected")
        self._load_button.setIcon(QIcon.fromTheme("document-open"))
        self._load_button.setEnabled(False)
        
        # Load all button
        self._load_all_button = QPushButton("Load All")
        self._load_all_button.setIcon(QIcon.fromTheme("folder-open"))
        self._load_all_button.setEnabled(False)
        
        # Refresh button
        self._refresh_button = QPushButton("Refresh")
        self._refresh_button.setIcon(QIcon.fromTheme("view-refresh"))
        
        layout.addWidget(self._load_button)
        layout.addWidget(self._load_all_button)
        layout.addWidget(self._refresh_button)
        layout.addStretch()
        
        widget.setLayout(layout)
        return widget
    
    def _connect_signals(self):
        """Connect UI signals to slots."""
        self._search_button.clicked.connect(self._perform_search)
        self._search_input.returnPressed.connect(self._perform_search)
        self._refresh_button.clicked.connect(self._perform_search)
        self._load_button.clicked.connect(self._load_selected)
        self._load_all_button.clicked.connect(self._load_all)
        self._results_tree.itemSelectionChanged.connect(self._on_selection_changed)
    
    def _on_status_change(self, status: ConnectionStatus, message: str):
        """Handle status changes from the PACS client."""
        if status == ConnectionStatus.CONNECTED:
            self._connection_status_label.setText("Connected")
            self._connection_status_label.setStyleSheet("color: #388e3c; font-weight: bold;")
        elif status == ConnectionStatus.CONNECTING:
            self._connection_status_label.setText("Connecting...")
            self._connection_status_label.setStyleSheet("color: #1976d2;")
        elif status == ConnectionStatus.ERROR:
            self._connection_status_label.setText("Error")
            self._connection_status_label.setStyleSheet("color: #d32f2f; font-weight: bold;")
        else:
            self._connection_status_label.setText("Disconnected")
            self._connection_status_label.setStyleSheet("color: #666;")
        
        self._status_label.setText(message)
    
    def _on_query_result(self, results: List[DICOMQueryResult]):
        """Handle query results from the PACS client."""
        # This is called from the client's callback
        # We'll update the tree in the main thread via the thread's signal
        pass
    
    def _perform_search(self):
        """Perform a search based on current UI inputs."""
        search_text = self._search_input.text().strip()
        search_type = self._search_type_combo.currentText()
        
        # Clear previous results
        self._results_tree.clear()
        self._current_patients = []
        self._current_studies = {}
        self._current_series = {}
        self._current_images = {}
        
        # Show progress
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._status_label.setText("Searching...")
        
        # Determine query level and parameters
        if search_type == "Patients":
            # Search for patients
            thread = PACSQueryThread(
                self._client,
                QueryLevel.PATIENT,
                patient_name=search_text if search_text else "*"
            )
        elif search_type == "Studies":
            # Search for studies (need patient context or wildcard)
            thread = PACSQueryThread(
                self._client,
                QueryLevel.STUDY,
                patient_id=search_text if search_text else "*"
            )
        elif search_type == "Series":
            # Search for series
            thread = PACSQueryThread(
                self._client,
                QueryLevel.SERIES,
                study_uid=search_text if search_text else ""
            )
        else:  # Images
            # Search for images
            thread = PACSQueryThread(
                self._client,
                QueryLevel.IMAGE,
                series_uid=search_text if search_text else ""
            )
        
        thread.query_complete.connect(self._handle_query_results)
        thread.error_occurred.connect(self._handle_query_error)
        thread.start()
        
        self._status_label.setText("Querying PACS...")
    
    def _handle_query_results(self, results: List[DICOMQueryResult]):
        """Handle query results from the thread."""
        self._progress_bar.setVisible(False)
        
        if not results:
            self._status_label.setText("No results found")
            return
        
        # Group results by level
        search_type = self._search_type_combo.currentText()
        
        if search_type == "Patients":
            self._display_patients(results)
        elif search_type == "Studies":
            self._display_studies(results)
        elif search_type == "Series":
            self._display_series(results)
        else:  # Images
            self._display_images(results)
        
        self._status_label.setText(f"Found {len(results)} results")
        self._load_button.setEnabled(True)
        self._load_all_button.setEnabled(True)
    
    def _handle_query_error(self, error: str):
        """Handle query errors."""
        self._progress_bar.setVisible(False)
        self._status_label.setText(f"Error: {error}")
        QMessageBox.warning(self, "Query Error", f"An error occurred:\n\n{error}")
    
    def _display_patients(self, results: List[DICOMQueryResult]):
        """Display patient results in the tree."""
        self._current_patients = results
        
        for result in results:
            item = QTreeWidgetItem()
            item.setText(0, result.patient_name or "Unknown")
            item.setText(1, result.patient_id or "")
            item.setText(2, "")
            item.setText(3, "")
            item.setText(4, "Patient")
            item.setData(0, Qt.UserRole, result)
            item.setIcon(0, QIcon.fromTheme("user"))
            
            self._results_tree.addTopLevelItem(item)
    
    def _display_studies(self, results: List[DICOMQueryResult]):
        """Display study results in the tree."""
        self._current_studies = {}
        
        for result in results:
            patient_id = result.patient_id or "Unknown"
            if patient_id not in self._current_studies:
                self._current_studies[patient_id] = []
            self._current_studies[patient_id].append(result)
        
        # Display grouped by patient
        for patient_id, studies in self._current_studies.items():
            patient_item = QTreeWidgetItem()
            patient_item.setText(0, f"Patient: {patient_id}")
            patient_item.setText(1, patient_id)
            patient_item.setText(2, "")
            patient_item.setText(3, "")
            patient_item.setText(4, "Patient")
            patient_item.setIcon(0, QIcon.fromTheme("user"))
            
            for study in studies:
                study_item = QTreeWidgetItem()
                study_item.setText(0, study.study_description or "Unnamed Study")
                study_item.setText(1, study.study_uid)
                study_item.setText(2, study.study_date)
                study_item.setText(3, "")
                study_item.setText(4, "Study")
                study_item.setData(0, Qt.UserRole, study)
                study_item.setIcon(0, QIcon.fromTheme("folder"))
                
                patient_item.addChild(study_item)
            
            self._results_tree.addTopLevelItem(patient_item)
            patient_item.setExpanded(True)
    
    def _display_series(self, results: List[DICOMQueryResult]):
        """Display series results in the tree."""
        self._current_series = {}
        
        for result in results:
            study_uid = result.study_uid or "Unknown"
            if study_uid not in self._current_series:
                self._current_series[study_uid] = []
            self._current_series[study_uid].append(result)
        
        # Display grouped by study
        for study_uid, series_list in self._current_series.items():
            study_item = QTreeWidgetItem()
            study_item.setText(0, f"Study: {study_uid[:20]}...")
            study_item.setText(1, study_uid)
            study_item.setText(2, "")
            study_item.setText(3, "")
            study_item.setText(4, "Study")
            study_item.setIcon(0, QIcon.fromTheme("folder"))
            
            for series in series_list:
                series_item = QTreeWidgetItem()
                series_item.setText(0, series.series_description or f"Series {series.series_number}")
                series_item.setText(1, series.series_uid)
                series_item.setText(2, "")
                series_item.setText(3, series.modality)
                series_item.setText(4, "Series")
                series_item.setData(0, Qt.UserRole, series)
                series_item.setIcon(0, QIcon.fromTheme("folder-open"))
                
                study_item.addChild(series_item)
            
            self._results_tree.addTopLevelItem(study_item)
            study_item.setExpanded(True)
    
    def _display_images(self, results: List[DICOMQueryResult]):
        """Display image results in the tree."""
        self._current_images = {}
        
        for result in results:
            series_uid = result.series_uid or "Unknown"
            if series_uid not in self._current_images:
                self._current_images[series_uid] = []
            self._current_images[series_uid].append(result)
        
        # Display grouped by series
        for series_uid, images in self._current_images.items():
            series_item = QTreeWidgetItem()
            series_item.setText(0, f"Series: {series_uid[:20]}...")
            series_item.setText(1, series_uid)
            series_item.setText(2, "")
            series_item.setText(3, "")
            series_item.setText(4, "Series")
            series_item.setIcon(0, QIcon.fromTheme("folder-open"))
            
            for image in images:
                image_item = QTreeWidgetItem()
                image_item.setText(0, f"Image {image.sop_uid[:15]}...")
                image_item.setText(1, image.sop_uid)
                image_item.setText(2, "")
                image_item.setText(3, image.modality)
                image_item.setText(4, "Image")
                image_item.setData(0, Qt.UserRole, image)
                image_item.setIcon(0, QIcon.fromTheme("image"))
                
                series_item.addChild(image_item)
            
            self._results_tree.addTopLevelItem(series_item)
            series_item.setExpanded(True)
    
    def _on_selection_changed(self):
        """Handle selection changes in the tree."""
        selected = self._results_tree.selectedItems()
        self._load_button.setEnabled(len(selected) > 0)
    
    def _load_selected(self):
        """Load the selected items."""
        selected = self._results_tree.selectedItems()
        if not selected:
            return
        
        # Get all series UIDs from selected items
        series_uids = []
        study_uids = []
        
        for item in selected:
            result: DICOMQueryResult = item.data(0, Qt.UserRole)
            if result:
                if result.series_uid:
                    series_uids.append(result.series_uid)
                if result.study_uid:
                    study_uids.append(result.study_uid)
        
        if not series_uids:
            QMessageBox.information(self, "No Series Selected", "Please select series to load.")
            return
        
        # Retrieve each selected series
        self._status_label.setText(f"Retrieving {len(series_uids)} series...")
        self._progress_bar.setVisible(True)
        self._progress_bar.setMaximum(len(series_uids))
        self._progress_bar.setValue(0)
        
        # For now, just retrieve the first series
        # In a real implementation, we'd retrieve all in parallel or sequentially
        series_uid = series_uids[0]
        study_uid = study_uids[0] if study_uids else ""
        
        thread = PACSRetrievalThread(self._client, series_uid, study_uid)
        thread.retrieval_complete.connect(self._handle_retrieval_complete)
        thread.start()
    
    def _load_all(self):
        """Load all items from the current query."""
        # Get all series from current results
        series_uids = []
        
        # Collect all series UIDs from the tree
        def collect_series(item: QTreeWidgetItem):
            result: DICOMQueryResult = item.data(0, Qt.UserRole)
            if result and result.series_uid:
                series_uids.append(result.series_uid)
            for i in range(item.childCount()):
                collect_series(item.child(i))
        
        for i in range(self._results_tree.topLevelItemCount()):
            collect_series(self._results_tree.topLevelItem(i))
        
        if not series_uids:
            QMessageBox.information(self, "No Series Found", "No series found in current results.")
            return
        
        self._status_label.setText(f"Retrieving {len(series_uids)} series...")
        self._progress_bar.setVisible(True)
        self._progress_bar.setMaximum(len(series_uids))
        self._progress_bar.setValue(0)
        
        # Retrieve all series
        for series_uid in series_uids:
            # Find study UID for this series
            study_uid = ""
            for result in self._current_series.get("", []):
                if result.series_uid == series_uid:
                    study_uid = result.study_uid
                    break
            
            thread = PACSRetrievalThread(self._client, series_uid, study_uid)
            thread.retrieval_complete.connect(self._handle_retrieval_complete)
            thread.start()
    
    def _handle_retrieval_complete(self, result: RetrievalResult):
        """Handle retrieval completion."""
        self._progress_bar.setVisible(False)
        
        if result.success:
            self._status_label.setText(f"Retrieved {len(result.file_paths)} files")
            
            # Load the files into the DICOM loader
            if result.file_paths:
                # Use the first file's parent directory
                dir_path = result.file_paths[0].parent
                self._dicom_loader.load_directory(dir_path)
                
                # Emit signal with retrieved files
                self.files_retrieved.emit(result.file_paths)
                
                QMessageBox.information(
                    self,
                    "Retrieval Complete",
                    f"Successfully retrieved {len(result.file_paths)} DICOM files.\n\n"
                    f"Files saved to: {dir_path}"
                )
        else:
            self._status_label.setText(f"Retrieval failed: {result.error_message}")
            QMessageBox.warning(
                self,
                "Retrieval Failed",
                f"Failed to retrieve files:\n\n{result.error_message}"
            )
    
    def refresh(self):
        """Refresh the current view."""
        self._perform_search()
    
    def cleanup(self):
        """Clean up resources."""
        self._client.cleanup()
        self._dicom_loader.clear()
    
    def __del__(self):
        """Destructor."""
        self.cleanup()
