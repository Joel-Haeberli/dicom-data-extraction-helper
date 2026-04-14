#!/usr/bin/env python3
"""
CSV parser for anonymization profiles.
Parses the CSV data into a structured matrix format for computational analysis.
"""

import csv
import os
from typing import Dict, List, Set, Tuple

class ProfileParser:
    def __init__(self, csv_file: str = 'anonymization_profiles.csv'):
        self.csv_file = csv_file
        self._validate_file()
        self.profiles = {}
        self.fields = []
        self.profile_names = []
        
    def _validate_file(self):
        """Validate that the CSV file exists and has correct extension."""
        if not os.path.exists(self.csv_file):
            raise FileNotFoundError(f"CSV file not found: {self.csv_file}")
        if not self.csv_file.endswith('.csv'):
            raise ValueError("File must have .csv extension")
        
    def parse_csv(self) -> Dict[str, Dict[str, str]]:
        """
        Parse CSV file into a structured dictionary format.
        Returns: {fieldname: {profile_name: operation, ...}, ...}
        """
        with open(self.csv_file, 'r') as f:
            reader = csv.reader(f)
            headers = next(reader)  # Get header row
            
            # Store profile names (skip first column 'fieldname') and clean them
            self.profile_names = [name.strip() for name in headers[1:]]
            
            # Parse each row
            for row in reader:
                if len(row) >= 4:  # Ensure row has all columns
                    fieldname = row[0].strip()
                    self.fields.append(fieldname)
                    
                    # Store operations for each profile
                    field_data = {}
                    for i, profile_name in enumerate(self.profile_names):
                        operation = row[i+1].strip() if i+1 < len(row) else ''
                        # Handle empty values by treating as 'X' (not considered)
                        operation = operation if operation else 'X'
                        field_data[profile_name] = operation
                    
                    self.profiles[fieldname] = field_data
        
        return self.profiles
    
    def get_matrix(self) -> Dict[str, Dict[str, str]]:
        """Return the parsed profile matrix."""
        if not self.profiles:
            self.parse_csv()
        return self.profiles
    
    def get_fields(self) -> List[str]:
        """Return list of all field names."""
        if not self.fields:
            self.parse_csv()
        return self.fields
    
    def get_profile_names(self) -> List[str]:
        """Return list of profile names."""
        if not self.profile_names:
            self.parse_csv()
        return self.profile_names