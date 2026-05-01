#!/usr/bin/env python3
"""
PACS Client for DICOM Data Extraction Helper

Provides PACS connectivity using pynetdicom for C-FIND, C-MOVE, and C-ECHO operations.
Allows querying studies/series/images from PACS and retrieving them to local storage.
"""

import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from pydicom.dataset import Dataset
from pydicom.uid import generate_uid

# pynetdicom imports
from pynetdicom import AE, StoragePresentationContexts, evt
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelMove,
    StudyRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelMove,
    PatientStudyOnlyQueryRetrieveInformationModelFind,
    Verification,
)


class QueryLevel(Enum):
    """DICOM Query/Retrieve levels."""
    PATIENT = "PATIENT"
    STUDY = "STUDY"
    SERIES = "SERIES"
    IMAGE = "IMAGE"


class ConnectionStatus(Enum):
    """PACS connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class PACSConfig:
    """Configuration for PACS connection."""
    ae_title: str = "DICOM_HELPER"
    ip: str = ""
    port: int = 104
    called_ae_title: str = "PACS"
    timeout: int = 30
    use_tls: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'ae_title': self.ae_title,
            'ip': self.ip,
            'port': self.port,
            'called_ae_title': self.called_ae_title,
            'timeout': self.timeout,
            'use_tls': self.use_tls,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PACSConfig':
        """Create from dictionary."""
        return cls(
            ae_title=data.get('ae_title', 'DICOM_HELPER'),
            ip=data.get('ip', ''),
            port=data.get('port', 104),
            called_ae_title=data.get('called_ae_title', 'PACS'),
            timeout=data.get('timeout', 30),
            use_tls=data.get('use_tls', False),
        )


@dataclass
class DICOMQueryResult:
    """Result from a DICOM query."""
    level: QueryLevel
    dataset: Dataset
    raw_response: Dataset
    
    @property
    def patient_id(self) -> str:
        return str(getattr(self.dataset, 'PatientID', ''))
    
    @property
    def patient_name(self) -> str:
        return str(getattr(self.dataset, 'PatientName', ''))
    
    @property
    def study_uid(self) -> str:
        return str(getattr(self.dataset, 'StudyInstanceUID', ''))
    
    @property
    def study_date(self) -> str:
        date = getattr(self.dataset, 'StudyDate', '')
        if date:
            try:
                # Format: YYYYMMDD
                return f"{date[:4]}-{date[4:6]}-{date[6:8]}"
            except (IndexError, ValueError):
                pass
        return str(date)
    
    @property
    def study_description(self) -> str:
        return str(getattr(self.dataset, 'StudyDescription', ''))
    
    @property
    def series_uid(self) -> str:
        return str(getattr(self.dataset, 'SeriesInstanceUID', ''))
    
    @property
    def series_number(self) -> str:
        return str(getattr(self.dataset, 'SeriesNumber', ''))
    
    @property
    def series_description(self) -> str:
        return str(getattr(self.dataset, 'SeriesDescription', ''))
    
    @property
    def modality(self) -> str:
        return str(getattr(self.dataset, 'Modality', ''))
    
    @property
    def sop_uid(self) -> str:
        return str(getattr(self.dataset, 'SOPInstanceUID', ''))
    
    @property
    def sop_class_uid(self) -> str:
        return str(getattr(self.dataset, 'SOPClassUID', ''))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'level': self.level.value,
            'patient_id': self.patient_id,
            'patient_name': self.patient_name,
            'study_uid': self.study_uid,
            'study_date': self.study_date,
            'study_description': self.study_description,
            'series_uid': self.series_uid,
            'series_number': self.series_number,
            'series_description': self.series_description,
            'modality': self.modality,
            'sop_uid': self.sop_uid,
            'sop_class_uid': self.sop_class_uid,
        }


@dataclass
class RetrievalResult:
    """Result from a C-MOVE retrieval operation."""
    success: bool
    file_paths: List[Path] = field(default_factory=list)
    error_message: str = ""
    study_uid: str = ""
    series_uid: str = ""


class PACSClient:
    """
    Client for connecting to and querying DICOM PACS.
    
    Supports:
    - C-ECHO: Test connection
    - C-FIND: Query patients, studies, series, images
    - C-MOVE: Retrieve studies/series to local storage
    
    Uses pynetdicom for DICOM networking.
    """
    
    def __init__(self):
        self.config = PACSConfig()
        self._temp_dir: Optional[Path] = None
        self._received_files: List[Path] = []
        self._status = ConnectionStatus.DISCONNECTED
        self._status_message = ""
        self._storage_scp: Optional[AE] = None
        self._storage_server_thread: Optional[threading.Thread] = None
        self._storage_port = 11113  # Default local storage port
        
        # Callbacks
        self._on_status_change: Optional[Callable[[ConnectionStatus, str], None]] = None
        self._on_query_result: Optional[Callable[[List[DICOMQueryResult]], None]] = None
        self._on_retrieval_complete: Optional[Callable[[RetrievalResult], None]] = None
        
        # Lock for thread safety
        self._lock = threading.Lock()
    
    @property
    def status(self) -> ConnectionStatus:
        return self._status
    
    @property
    def status_message(self) -> str:
        return self._status_message
    
    @property
    def temp_dir(self) -> Path:
        """Get or create temporary directory for received files."""
        if self._temp_dir is None:
            self._temp_dir = Path(tempfile.mkdtemp(prefix="dicom_pacs_"))
        return self._temp_dir
    
    @property
    def received_files(self) -> List[Path]:
        """List of files received from PACS."""
        return self._received_files.copy()
    
    def set_status_change_callback(self, callback: Callable[[ConnectionStatus, str], None]):
        """Set callback for status changes."""
        self._on_status_change = callback
    
    def set_query_result_callback(self, callback: Callable[[List[DICOMQueryResult]], None]):
        """Set callback for query results."""
        self._on_query_result = callback
    
    def set_retrieval_complete_callback(self, callback: Callable[[RetrievalResult], None]):
        """Set callback for retrieval completion."""
        self._on_retrieval_complete = callback
    
    def _update_status(self, status: ConnectionStatus, message: str = ""):
        """Update connection status and notify callback."""
        self._status = status
        self._status_message = message
        if self._on_status_change:
            self._on_status_change(status, message)
    
    def _create_query_dataset(self, level: QueryLevel, **kwargs) -> Dataset:
        """Create a query dataset for the specified level."""
        ds = Dataset()
        ds.QueryRetrieveLevel = level.value
        
        # Add common query attributes based on level
        if level == QueryLevel.PATIENT:
            if 'patient_name' in kwargs:
                ds.PatientName = kwargs['patient_name']
            if 'patient_id' in kwargs:
                ds.PatientID = kwargs['patient_id']
            if 'patient_birth_date' in kwargs:
                ds.PatientBirthDate = kwargs['patient_birth_date']
            if 'patient_sex' in kwargs:
                ds.PatientSex = kwargs['patient_sex']
                
        elif level == QueryLevel.STUDY:
            if 'patient_id' in kwargs:
                ds.PatientID = kwargs['patient_id']
            if 'study_uid' in kwargs:
                ds.StudyInstanceUID = kwargs['study_uid']
            if 'study_date' in kwargs:
                ds.StudyDate = kwargs['study_date']
            if 'study_time' in kwargs:
                ds.StudyTime = kwargs['study_time']
            if 'accession_number' in kwargs:
                ds.AccessionNumber = kwargs['accession_number']
            if 'study_description' in kwargs:
                ds.StudyDescription = kwargs['study_description']
            if 'modality' in kwargs:
                ds.ModalitiesInStudy = kwargs['modality']
                
        elif level == QueryLevel.SERIES:
            if 'study_uid' in kwargs:
                ds.StudyInstanceUID = kwargs['study_uid']
            if 'series_uid' in kwargs:
                ds.SeriesInstanceUID = kwargs['series_uid']
            if 'modality' in kwargs:
                ds.Modality = kwargs['modality']
            if 'series_number' in kwargs:
                ds.SeriesNumber = kwargs['series_number']
            if 'series_description' in kwargs:
                ds.SeriesDescription = kwargs['series_description']
                
        elif level == QueryLevel.IMAGE:
            if 'series_uid' in kwargs:
                ds.SeriesInstanceUID = kwargs['series_uid']
            if 'sop_uid' in kwargs:
                ds.SOPInstanceUID = kwargs['sop_uid']
            if 'sop_class_uid' in kwargs:
                ds.SOPClassUID = kwargs['sop_class_uid']
            if 'instance_number' in kwargs:
                ds.InstanceNumber = kwargs['instance_number']
        
        return ds
    
    def _get_sop_class(self, level: QueryLevel) -> type:
        """Get the appropriate SOP class for the query level."""
        # Use Patient Root by default (most compatible)
        # Note: pynetdicom doesn't have SeriesRoot, so we use PatientRoot for all levels
        # The QueryRetrieveLevel in the dataset determines the actual query level
        return PatientRootQueryRetrieveInformationModelFind
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test PACS connection using C-ECHO (Verification).
        
        Returns:
            Tuple of (success, message)
        """
        self._update_status(ConnectionStatus.CONNECTING, "Testing connection...")
        
        try:
            ae = AE(ae_title=self.config.ae_title.encode())
            ae.add_requested_context(Verification)
            
            assoc = ae.associate(
                self.config.ip, 
                self.config.port,
                ae_title=self.config.called_ae_title.encode()
            )
            
            if assoc.is_established:
                # Send C-ECHO
                status = assoc.send_c_echo()
                assoc.release()
                
                if status.Status == 0x0000:  # Success
                    self._update_status(ConnectionStatus.CONNECTED, "Connection successful")
                    return True, "Connection successful"
                else:
                    msg = f"C-ECHO failed: 0x{status.Status:04X}"
                    self._update_status(ConnectionStatus.ERROR, msg)
                    return False, msg
            else:
                msg = "Association not established"
                self._update_status(ConnectionStatus.ERROR, msg)
                return False, msg
                
        except Exception as e:
            msg = f"Connection error: {str(e)}"
            self._update_status(ConnectionStatus.ERROR, msg)
            return False, msg
    
    def query(self, level: QueryLevel, **kwargs) -> List[DICOMQueryResult]:
        """
        Query PACS at the specified level.
        
        Args:
            level: Query level (PATIENT, STUDY, SERIES, IMAGE)
            **kwargs: Query parameters (see _create_query_dataset)
            
        Returns:
            List of DICOMQueryResult objects
        """
        self._update_status(ConnectionStatus.CONNECTING, f"Querying {level.value}...")
        
        results = []
        sop_class = self._get_sop_class(level)
        
        try:
            ae = AE(ae_title=self.config.ae_title.encode())
            ae.add_requested_context(sop_class)
            
            assoc = ae.associate(
                self.config.ip,
                self.config.port,
                ae_title=self.config.called_ae_title.encode()
            )
            
            if assoc.is_established:
                ds = self._create_query_dataset(level, **kwargs)
                
                # Send C-FIND
                responses = assoc.send_c_find(ds, sop_class)
                
                for status, identifier in responses:
                    if status and hasattr(status, 'Status'):
                        if status.Status == 0x0000:  # Success
                            # Pending status - more results may follow
                            if identifier:
                                result = DICOMQueryResult(
                                    level=level,
                                    dataset=identifier,
                                    raw_response=identifier
                                )
                                results.append(result)
                        elif status.Status == 0xA700:  # Pending
                            # Intermediate result
                            if identifier:
                                result = DICOMQueryResult(
                                    level=level,
                                    dataset=identifier,
                                    raw_response=identifier
                                )
                                results.append(result)
                        elif status.Status == 0xA900:  # Cancel
                            break
                        elif status.Status != 0x0000:  # Error
                            print(f"Query warning: 0x{status.Status:04X}")
                
                assoc.release()
                self._update_status(ConnectionStatus.CONNECTED, f"Found {len(results)} {level.value} results")
                
            else:
                self._update_status(ConnectionStatus.ERROR, "Association not established")
                
        except Exception as e:
            self._update_status(ConnectionStatus.ERROR, f"Query error: {str(e)}")
            print(f"Query error: {e}")
        
        # Notify callback
        if self._on_query_result:
            self._on_query_result(results)
        
        return results
    
    def query_patients(self, patient_name: str = "", patient_id: str = "") -> List[DICOMQueryResult]:
        """Query for patients."""
        return self.query(
            QueryLevel.PATIENT,
            patient_name=patient_name,
            patient_id=patient_id
        )
    
    def query_studies(self, patient_id: str = "", study_date: str = "", modality: str = "") -> List[DICOMQueryResult]:
        """Query for studies."""
        return self.query(
            QueryLevel.STUDY,
            patient_id=patient_id,
            study_date=study_date,
            modality=modality
        )
    
    def query_series(self, study_uid: str = "", modality: str = "") -> List[DICOMQueryResult]:
        """Query for series within a study."""
        return self.query(
            QueryLevel.SERIES,
            study_uid=study_uid,
            modality=modality
        )
    
    def query_images(self, series_uid: str = "") -> List[DICOMQueryResult]:
        """Query for images within a series."""
        return self.query(
            QueryLevel.IMAGE,
            series_uid=series_uid
        )
    
    def _handle_store(self, event: evt.EVT_C_STORE) -> int:
        """
        Handle incoming C-STORE request (for C-MOVE retrieval).
        
        This is called when the PACS sends DICOM files to our Storage SCP.
        """
        try:
            # Get the dataset
            ds = event.dataset
            
            # Generate a unique filename
            sop_uid = str(getattr(ds, 'SOPInstanceUID', generate_uid()))
            filename = f"{sop_uid}.dcm"
            filepath = self.temp_dir / filename
            
            # Save the file
            ds.save_as(filepath, write_like_original=True)
            
            # Track received file
            with self._lock:
                self._received_files.append(filepath)
            
            print(f"Received DICOM file: {filepath}")
            return 0x0000  # Success
            
        except Exception as e:
            print(f"Error storing DICOM file: {e}")
            return 0xC000  # Unable to process
    
    def _start_storage_scp(self) -> bool:
        """Start local Storage SCP to receive C-MOVE files."""
        try:
            # Create AE for storage
            self._storage_scp = AE(ae_title=self.config.ae_title.encode())
            self._storage_scp.supported_contexts = StoragePresentationContexts
            self._storage_scp.on_c_store = self._handle_store
            
            # Start server in a thread
            def run_server():
                self._storage_scp.start_server(
                    ('', self._storage_port),
                    block=True
                )
            
            self._storage_server_thread = threading.Thread(
                target=run_server,
                daemon=True
            )
            self._storage_server_thread.start()
            
            # Wait a moment for server to start
            time.sleep(0.5)
            return True
            
        except Exception as e:
            print(f"Failed to start Storage SCP: {e}")
            return False
    
    def _stop_storage_scp(self):
        """Stop the local Storage SCP."""
        if self._storage_scp:
            try:
                self._storage_scp.shutdown()
            except Exception:
                pass
            self._storage_scp = None
        
        if self._storage_server_thread:
            self._storage_server_thread.join(timeout=1.0)
            self._storage_server_thread = None
    
    def retrieve_series(self, series_uid: str, study_uid: str = "") -> RetrievalResult:
        """
        Retrieve a series from PACS using C-MOVE.
        
        Args:
            series_uid: Series Instance UID to retrieve
            study_uid: Study Instance UID (optional, for context)
            
        Returns:
            RetrievalResult with success status and file paths
        """
        self._update_status(ConnectionStatus.CONNECTING, "Starting retrieval...")
        
        # Clear previous received files
        with self._lock:
            self._received_files = []
        
        # Start local Storage SCP
        if not self._start_storage_scp():
            return RetrievalResult(
                success=False,
                error_message="Failed to start Storage SCP"
            )
        
        try:
            # Create C-MOVE request
            ae = AE(ae_title=self.config.ae_title.encode())
            ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
            
            assoc = ae.associate(
                self.config.ip,
                self.config.port,
                ae_title=self.config.called_ae_title.encode()
            )
            
            if assoc.is_established:
                ds = Dataset()
                ds.QueryRetrieveLevel = "SERIES"
                ds.SeriesInstanceUID = series_uid
                if study_uid:
                    ds.StudyInstanceUID = study_uid
                
                # Send C-MOVE to our local Storage SCP
                responses = assoc.send_c_move(
                    ds,
                    self.config.ae_title.encode(),  # Destination AE title
                    PatientRootQueryRetrieveInformationModelMove
                )
                
                # Process responses
                for status, identifier in responses:
                    if status and hasattr(status, 'Status'):
                        if status.Status != 0x0000:
                            print(f"C-MOVE warning: 0x{status.Status:04X}")
                
                assoc.release()
                
                # Wait for files to be received
                # Give it some time (up to config.timeout seconds)
                start_time = time.time()
                while time.time() - start_time < self.config.timeout:
                    with self._lock:
                        if self._received_files:
                            break
                    time.sleep(0.1)
                
                self._update_status(
                    ConnectionStatus.CONNECTED,
                    f"Retrieved {len(self._received_files)} files"
                )
                
                return RetrievalResult(
                    success=True,
                    file_paths=self._received_files.copy(),
                    study_uid=study_uid,
                    series_uid=series_uid
                )
            else:
                return RetrievalResult(
                    success=False,
                    error_message="Association not established"
                )
                
        except Exception as e:
            self._update_status(ConnectionStatus.ERROR, f"Retrieval error: {str(e)}")
            return RetrievalResult(
                success=False,
                error_message=str(e)
            )
        finally:
            self._stop_storage_scp()
    
    def retrieve_study(self, study_uid: str) -> RetrievalResult:
        """
        Retrieve all series from a study.
        
        Args:
            study_uid: Study Instance UID to retrieve
            
        Returns:
            RetrievalResult with success status and file paths
        """
        # First query for all series in the study
        series_results = self.query_series(study_uid=study_uid)
        
        all_files = []
        for series_result in series_results:
            result = self.retrieve_series(
                series_uid=series_result.series_uid,
                study_uid=study_uid
            )
            if result.success:
                all_files.extend(result.file_paths)
        
        return RetrievalResult(
            success=True,
            file_paths=all_files,
            study_uid=study_uid
        )
    
    def cleanup(self):
        """Clean up temporary files and stop servers."""
        self._stop_storage_scp()
        
        # Clean up temp directory
        if self._temp_dir and self._temp_dir.exists():
            import shutil
            try:
                shutil.rmtree(self._temp_dir)
            except Exception as e:
                print(f"Warning: Could not cleanup temp dir: {e}")
            self._temp_dir = None
        
        self._received_files = []
        # Don't call _update_status here as it may trigger callbacks after UI is destroyed
        self._status = ConnectionStatus.DISCONNECTED
        self._status_message = "Cleaned up"
    
    def __del__(self):
        """Destructor - ensure cleanup."""
        try:
            self.cleanup()
        except Exception:
            # Ignore errors during cleanup (e.g., UI already destroyed)
            pass
