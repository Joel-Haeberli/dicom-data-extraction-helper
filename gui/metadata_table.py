#!/usr/bin/env python3
"""
Metadata Table Widget for GUI Application

Displays DICOM metadata in a QTableWidget with two columns (Tag, Value).
Reuses TAG_CATEGORIES from dicom_header_extractor.py for consistent ordering.
"""

from typing import Any, Dict

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
from PySide6.QtCore import Qt, Signal, QEnum
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView

try:
    from dicom_header_extractor import TAG_CATEGORIES, format_value
except ImportError:
    TAG_CATEGORIES = {}
    def format_value(value):
        return str(value) if value is not None else ""


def tag_id_to_hex(tag_id: int) -> str:
    """Convert a DICOM tag ID (int) to hex format (gggg,eeee)."""
    group = (tag_id >> 16) & 0xFFFF
    element = tag_id & 0xFFFF
    return f"({group:04X},{element:04X})"


def get_tag_hex(tag_name: str) -> str:
    """Get the hex representation for a tag name by searching TAG_CATEGORIES."""
    for category, tags in TAG_CATEGORIES.items():
        for tn, tag_id in tags:
            if tn == tag_name:
                return tag_id_to_hex(tag_id)
    return ""


class MetadataTable(QTableWidget):
    """
    Table widget for displaying DICOM metadata.
    
    Features:
    - Two-column layout (Tag, Value)
    - Sortable headers
    - Read-only cells
    - Consistent tag ordering using TAG_CATEGORIES from existing project
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Configure table
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["Tag (Name - Hex)", "Value"])
        
        # Header configuration
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        
        # Table behavior
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)  # Read-only
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        
        # Sorting
        self.setSortingEnabled(True)
        self.sortByColumn(0, Qt.AscendingOrder)
        
        # Vertical header
        self.verticalHeader().setVisible(False)
        
        # Style
        self.setStyleSheet("""
            QTableWidget {
                font-family: Arial, sans-serif;
                font-size: 11px;
            }
        """)
    
    def set_metadata(self, metadata: Dict[str, Dict[str, Any]]):
        """
        Populate the table with metadata.
        
        Args:
            metadata: Nested dict {category: {tag_name: value}}
        """
        self.setRowCount(0)  # Clear existing rows
        
        # Flatten metadata to a list of (tag, value) pairs
        # Use TAG_CATEGORIES order for consistency, then additional metadata
        items = []
        
        # First, add tags from TAG_CATEGORIES (in defined order)
        for category, tags in TAG_CATEGORIES.items():
            category_metadata = metadata.get(category, {})
            for tag_name, _ in tags:
                value = category_metadata.get(tag_name)
                if value is not None:
                    formatted_value = format_value(value)
                    items.append((tag_name, formatted_value if formatted_value else ""))
        
        # Then, add additional metadata tags (sorted alphabetically)
        additional_tags = metadata.get("Additional Metadata", {})
        for tag_name in sorted(additional_tags.keys()):
            value = additional_tags.get(tag_name)
            if value is not None:
                formatted_value = format_value(value)
                items.append((tag_name, formatted_value if formatted_value else ""))
        
        # Insert rows
        self.setRowCount(len(items))
        
        for row, (tag, value) in enumerate(items):
            # Get hex representation for this tag
            hex_tag = get_tag_hex(tag)
            
            # Tag column: show both name and hex
            if hex_tag:
                tag_display = f"{tag} - {hex_tag}"
            else:
                tag_display = tag
            
            tag_item = QTableWidgetItem(tag_display)
            tag_item.setFlags(tag_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            tag_item.setToolTip(f"{tag}\n{hex_tag}" if hex_tag else tag)
            self.setItem(row, 0, tag_item)
            
            # Value column
            value_item = QTableWidgetItem(value)
            value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            value_item.setToolTip(value)
            self.setItem(row, 1, value_item)
        
        # Resize columns to fit content
        self.resizeColumnsToContents()
    
    def clear(self):
        """Clear all metadata from the table."""
        self.setRowCount(0)
    
    def contextMenuEvent(self, event):
        """
        Override to add custom context menu (copy to clipboard).
        """
        # For now, just use default behavior
        # Can be extended to add copy functionality
        super().contextMenuEvent(event)
