#!/usr/bin/env python3
"""
DICOM Explorer Widget for GUI Application

Provides a file system browser that recognizes DICOM directories.
"""

from pathlib import Path

from PySide6.QtWidgets import QWidget, QTreeView, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal, QDir
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFileSystemModel

try:
    from dicom_header_extractor import find_dicom_files
    HAS_DICOM_UTILS = True
except ImportError:
    HAS_DICOM_UTILS = False
    print("Warning: dicom_header_extractor not available, DICOM detection disabled")


class DICOMExplorer(QWidget):
    """File explorer widget that recognizes and allows selection of DICOM directories.
    
    Emits directory_selected signal when a directory containing DICOM files is double-clicked.
    """
    
    directory_selected = Signal(Path)  # Emitted when user selects a DICOM directory
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the explorer widget UI."""
        # Tree view for file system navigation
        self._tree = QTreeView(self)
        self._tree.setHeaderHidden(True)  # Hide header for cleaner look
        self._tree.setSelectionMode(QTreeView.SingleSelection)
        
        # File system model
        self._model = QFileSystemModel(self)
        self._model.setRootPath(str(Path.home()))
        self._model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot)
        self._tree.setModel(self._model)
        
        # Start at user's home directory
        self._tree.setRootIndex(self._model.index(str(Path.home())))
        
        # Hide unnecessary columns (show only name)
        for col in range(1, self._model.columnCount()):
            self._tree.setColumnHidden(col, True)
        
        # Connect double-click/activate signal
        self._tree.activated.connect(self._on_item_activated)
        
        # Info label
        self._info_label = QLabel("Double-click a folder containing DICOM files to load", self)
        self._info_label.setStyleSheet("color: #888; font-size: 12px; padding: 4px;")
        
        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(QLabel("DICOM Explorer", self), 0)
        layout.addWidget(self._tree, 1)
        layout.addWidget(self._info_label, 0)
    
    def _on_item_activated(self, index):
        """Handle activation (double-click or Enter) on tree item."""
        path = Path(self._model.filePath(index))
        if path.is_dir() and self._is_dicom_directory(path):
            self.directory_selected.emit(path)
            self._info_label.setText(f"Loaded: {path.name}")
        else:
            self._info_label.setText("Directory does not contain DICOM files")
    
    def _is_dicom_directory(self, path: Path) -> bool:
        """Check if directory contains DICOM files.
        
        Args:
            path: Path to directory to check
            
        Returns:
            True if directory contains at least one DICOM file
        """
        if not path.exists() or not path.is_dir():
            return False
        
        if HAS_DICOM_UTILS:
            dicom_files = find_dicom_files(path)  # Pass Path object, not string
            return len(dicom_files) > 0
        else:
            # Fallback: check for files with .dcm extension
            for f in path.rglob('*'):
                if f.is_file() and f.suffix.lower() in ['.dcm', '.dicom']:
                    return True
                # Also check common DICOM file patterns (no extension)
                if f.is_file() and f.stat().st_size > 100:  # DICOM files are typically >100 bytes
                    # Quick check for DICOM magic bytes (prefix "DICM")
                    try:
                        with open(f, 'rb') as file:
                            header = file.read(128)
                            if header[:4] == b'DICM':
                                return True
                    except:
                        pass
            return False
    
    def refresh(self):
        """Refresh the file system view."""
        self._model.setRootPath(str(Path.home()))
        self._tree.setRootIndex(self._model.index(str(Path.home())))
    
    def set_root_path(self, path: Path):
        """Set the root path for the explorer.
        
        Args:
            path: Path to set as root
        """
        self._model.setRootPath(str(path))
        self._tree.setRootIndex(self._model.index(str(path)))
