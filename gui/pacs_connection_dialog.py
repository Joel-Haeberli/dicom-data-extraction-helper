#!/usr/bin/env python3
"""
PACS Connection Dialog for DICOM Data Extraction Helper

Provides UI for configuring and testing PACS connection.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QSpinBox, QCheckBox,
    QMessageBox, QFrame
)
from PySide6.QtGui import QIcon

from gui.utils.pacs_client import PACSClient, PACSConfig, ConnectionStatus


class PACSConnectionDialog(QDialog):
    """
    Dialog for configuring and testing PACS connection.
    
    Allows users to:
    - Enter PACS connection parameters (IP, port, AE titles)
    - Test the connection using C-ECHO
    - Save successful configurations
    """
    
    connection_successful = Signal(PACSConfig)
    
    def __init__(self, client: PACSClient, parent=None):
        """
        Initialize the connection dialog.
        
        Args:
            client: PACSClient instance to use for connection testing
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("PACS Connection")
        self.setMinimumWidth(400)
        
        self._client = client
        self._config = PACSConfig()
        
        # Copy current client config if available
        if client.config:
            self._config = PACSConfig(
                ae_title=client.config.ae_title,
                ip=client.config.ip,
                port=client.config.port,
                called_ae_title=client.config.called_ae_title,
                timeout=client.config.timeout,
                use_tls=client.config.use_tls
            )
        
        self._setup_ui()
        self._connect_signals()
        self._update_status("Ready")
    
    def _setup_ui(self):
        """Set up the user interface."""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Title
        title_label = QLabel("DICOM PACS Connection")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        main_layout.addWidget(title_label)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(separator)
        
        # Connection form
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight)
        form_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        
        # Local AE Title
        self._local_ae_input = QLineEdit(self._config.ae_title)
        self._local_ae_input.setPlaceholderText("e.g., DICOM_HELPER")
        self._local_ae_input.setToolTip("Local Application Entity Title")
        form_layout.addRow("Local AE Title:", self._local_ae_input)
        
        # PACS IP
        self._ip_input = QLineEdit(self._config.ip)
        self._ip_input.setPlaceholderText("e.g., 192.168.1.100")
        self._ip_input.setToolTip("PACS server IP address")
        form_layout.addRow("PACS IP:", self._ip_input)
        
        # PACS Port
        self._port_input = QSpinBox()
        self._port_input.setRange(1, 65535)
        self._port_input.setValue(self._config.port)
        self._port_input.setToolTip("PACS server port (default: 104)")
        form_layout.addRow("PACS Port:", self._port_input)
        
        # Called AE Title
        self._called_ae_input = QLineEdit(self._config.called_ae_title)
        self._called_ae_input.setPlaceholderText("e.g., PACS")
        self._called_ae_input.setToolTip("PACS Application Entity Title")
        form_layout.addRow("PACS AE Title:", self._called_ae_input)
        
        # Timeout
        self._timeout_input = QSpinBox()
        self._timeout_input.setRange(5, 300)
        self._timeout_input.setValue(self._config.timeout)
        self._timeout_input.setSuffix(" seconds")
        self._timeout_input.setToolTip("Connection timeout in seconds")
        form_layout.addRow("Timeout:", self._timeout_input)
        
        # TLS/SSL
        self._tls_check = QCheckBox("Use TLS/SSL")
        self._tls_check.setChecked(self._config.use_tls)
        self._tls_check.setToolTip("Enable DICOM TLS for encrypted connection")
        form_layout.addRow("", self._tls_check)
        
        main_layout.addLayout(form_layout)
        
        # Status area
        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet("color: #666;")
        main_layout.addWidget(self._status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self._test_button = QPushButton("Test Connection")
        self._test_button.setIcon(QIcon.fromTheme("network-server"))
        self._test_button.setDefault(True)
        
        self._connect_button = QPushButton("Connect")
        self._connect_button.setIcon(QIcon.fromTheme("network-connect"))
        
        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.setIcon(QIcon.fromTheme("dialog-cancel"))
        
        button_layout.addWidget(self._test_button)
        button_layout.addWidget(self._connect_button)
        button_layout.addWidget(self._cancel_button)
        button_layout.addStretch()
        
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
    
    def _connect_signals(self):
        """Connect UI signals to slots."""
        self._test_button.clicked.connect(self._test_connection)
        self._connect_button.clicked.connect(self._accept_connection)
        self._cancel_button.clicked.connect(self.reject)
        
        # Enable/disable Connect button based on input
        for widget in [self._local_ae_input, self._ip_input, self._port_input, 
                       self._called_ae_input]:
            widget.textChanged.connect(self._validate_inputs)
        
        self._validate_inputs()
    
    def _validate_inputs(self):
        """Validate that required fields are filled."""
        has_ip = bool(self._ip_input.text().strip())
        has_local_ae = bool(self._local_ae_input.text().strip())
        has_called_ae = bool(self._called_ae_input.text().strip())
        
        self._connect_button.setEnabled(has_ip and has_local_ae and has_called_ae)
        self._test_button.setEnabled(has_ip and has_local_ae and has_called_ae)
    
    def _update_status(self, message: str, is_error: bool = False):
        """Update the status label."""
        if is_error:
            self._status_label.setText(f"❌ {message}")
            self._status_label.setStyleSheet("color: #d32f2f; font-weight: bold;")
        else:
            self._status_label.setText(f"✓ {message}")
            self._status_label.setStyleSheet("color: #388e3c; font-weight: bold;")
    
    def _get_current_config(self) -> PACSConfig:
        """Get the current configuration from UI inputs."""
        return PACSConfig(
            ae_title=self._local_ae_input.text().strip(),
            ip=self._ip_input.text().strip(),
            port=self._port_input.value(),
            called_ae_title=self._called_ae_input.text().strip(),
            timeout=self._timeout_input.value(),
            use_tls=self._tls_check.isChecked()
        )
    
    def _test_connection(self):
        """Test the PACS connection using C-ECHO."""
        config = self._get_current_config()
        
        # Update client config temporarily
        old_config = self._client.config
        self._client.config = config
        
        try:
            self._update_status("Testing connection...", is_error=False)
            self._test_button.setEnabled(False)
            self._connect_button.setEnabled(False)
            
            # Test connection (this will update client status)
            success, message = self._client.test_connection()
            
            if success:
                self._update_status("Connection successful!", is_error=False)
                QMessageBox.information(
                    self,
                    "Connection Test",
                    "PACS connection test successful!\n\n" + message
                )
            else:
                self._update_status(f"Connection failed: {message}", is_error=True)
                QMessageBox.warning(
                    self,
                    "Connection Test",
                    f"PACS connection test failed:\n\n{message}"
                )
                
        except Exception as e:
            self._update_status(f"Error: {str(e)}", is_error=True)
            QMessageBox.critical(
                self,
                "Connection Error",
                f"An error occurred while testing the connection:\n\n{str(e)}"
            )
        finally:
            self._client.config = old_config
            self._test_button.setEnabled(True)
            self._connect_button.setEnabled(True)
    
    def _accept_connection(self):
        """Accept the connection and emit the configuration."""
        config = self._get_current_config()
        
        # Validate
        if not config.ip:
            QMessageBox.warning(self, "Validation Error", "Please enter a PACS IP address.")
            return
        
        if not config.ae_title:
            QMessageBox.warning(self, "Validation Error", "Please enter a local AE title.")
            return
        
        if not config.called_ae_title:
            QMessageBox.warning(self, "Validation Error", "Please enter a PACS AE title.")
            return
        
        # Update client config
        self._client.config = config
        
        # Emit signal
        self.connection_successful.emit(config)
        
        # Accept dialog
        self.accept()
    
    def get_config(self) -> PACSConfig:
        """Get the final configuration."""
        return self._get_current_config()
    
    def set_config(self, config: PACSConfig):
        """Set the configuration from an existing PACSConfig."""
        self._config = config
        self._local_ae_input.setText(config.ae_title)
        self._ip_input.setText(config.ip)
        self._port_input.setValue(config.port)
        self._called_ae_input.setText(config.called_ae_title)
        self._timeout_input.setValue(config.timeout)
        self._tls_check.setChecked(config.use_tls)
