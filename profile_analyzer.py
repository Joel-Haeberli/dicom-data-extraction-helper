#!/usr/bin/env python3
"""
Anonymization profile analyzer.
Implements mathematical operations for comparing profiles and finding optimal profiles.
"""

from typing import Dict, List, Set, Tuple, Optional
from profile_parser import ProfileParser

class ProfileAnalyzer:
    def __init__(self, parser: Optional[ProfileParser] = None, csv_file: str = 'anonymization_profiles.csv'):
        if parser is None:
            parser = ProfileParser(csv_file)
        self.parser = parser
        self.matrix = self.parser.get_matrix()
        self.fields = self.parser.get_fields()
        self.profile_names = self.parser.get_profile_names()
    
    def get_profile_differences(self, profile1: str, profile2: str) -> List[Tuple[str, str, str]]:
        """
        Find differences between two profiles.
        Returns list of (field, profile1_operation, profile2_operation) tuples.
        """
        differences = []
        for field in self.fields:
            op1 = self.matrix[field].get(profile1, 'X')
            op2 = self.matrix[field].get(profile2, 'X')
            if op1 != op2:
                differences.append((field, op1, op2))
        return differences
    
    def find_profiles_for_operations(self, field_operations: Dict[str, str]) -> List[str]:
        """
        Find profiles that match specified operations for given fields.
        Args:
            field_operations: {fieldname: desired_operation, ...}
        Returns:
            List of profile names that satisfy all requirements
        """
        matching_profiles = set(self.profile_names)
        
        for field, desired_op in field_operations.items():
            if field not in self.matrix:
                continue  # Skip unknown fields
                
            # Find profiles that match this field's requirement
            field_matches = set()
            for profile in self.profile_names:
                actual_op = self.matrix[field].get(profile, 'X')
                if actual_op == desired_op:
                    field_matches.add(profile)
            
            # Intersect with current matching profiles
            matching_profiles = matching_profiles & field_matches
            
            # Early exit if no profiles left
            if not matching_profiles:
                break
        
        return list(matching_profiles)
    
    def find_profiles_excluding_fields(self, exclude_fields: Set[str]) -> List[str]:
        """
        Find profiles that don't anonymize specified fields (operation = 'X').
        Args:
            exclude_fields: Set of field names to keep as-is (not anonymize)
        Returns:
            List of profile names where specified fields have operation 'X'
        """
        matching_profiles = set(self.profile_names)
        
        for field in exclude_fields:
            if field not in self.matrix:
                continue  # Skip unknown fields
                
            # Find profiles where this field is not considered (X)
            field_matches = set()
            for profile in self.profile_names:
                actual_op = self.matrix[field].get(profile, 'X')
                if actual_op == 'X':
                    field_matches.add(profile)
            
            # Intersect with current matching profiles
            matching_profiles = matching_profiles & field_matches
            
            # Early exit if no profiles left
            if not matching_profiles:
                break
        
        return list(matching_profiles)
    
    def get_profile_statistics(self) -> Dict[str, Dict[str, int]]:
        """
        Get statistics for each profile.
        Returns: {profile: {operation: count, ...}, ...}
        """
        stats = {}
        for profile in self.profile_names:
            profile_stats = {'remove': 0, 'modify': 0, 'custom': 0, 'X': 0}
            
            for field in self.fields:
                op = self.matrix[field].get(profile, 'X')
                profile_stats[op] += 1
            
            stats[profile] = profile_stats
        
        return stats
    
    def get_multi_profile_differences(self, profiles: List[str]) -> Dict[str, Dict[str, str]]:
        """
        Find differences across multiple profiles.
        Returns: {field: {profile: operation, ...} for fields with any differences}
        """
        # Validate input profiles
        valid_profiles = [p for p in profiles if p in self.profile_names]
        if not valid_profiles:
            return {}
            
        differences = {}
        
        for field in self.fields:
            # Collect operations for this field across all specified profiles
            field_ops = {}
            unique_ops = set()
            
            for profile in valid_profiles:
                op = self.matrix[field].get(profile, 'X')
                field_ops[profile] = op
                unique_ops.add(op)
            
            # If there are differences (more than one unique operation), include this field
            if len(unique_ops) > 1:
                differences[field] = field_ops
        
        return differences
    
    def get_profile_similarity_matrix(self) -> Dict[str, Dict[str, float]]:
        """
        Calculate Jaccard similarity between all profile pairs.
        Returns: {profile1: {profile2: similarity_score, ...}, ...}
        """
        similarity_matrix = {}
        
        # Convert each profile to a set of (field, operation) tuples
        profile_sets = {}
        for profile in self.profile_names:
            profile_sets[profile] = set()
            for field in self.fields:
                op = self.matrix[field].get(profile, 'X')
                profile_sets[profile].add((field, op))
        
        # Calculate pairwise similarities
        for profile1 in self.profile_names:
            similarity_matrix[profile1] = {}
            for profile2 in self.profile_names:
                if profile1 == profile2:
                    similarity_matrix[profile1][profile2] = 1.0
                else:
                    set1 = profile_sets[profile1]
                    set2 = profile_sets[profile2]
                    intersection = len(set1 & set2)
                    union = len(set1 | set2)
                    similarity = intersection / union if union > 0 else 0.0
                    similarity_matrix[profile1][profile2] = round(similarity, 3)
        
        return similarity_matrix
    
    def find_consensus_fields(self, profiles: List[str], min_agreement: int = 2) -> Dict[str, str]:
        """
        Find fields where multiple profiles agree on the operation.
        Returns: {field: operation, ...} for fields where >= min_agreement profiles agree
        """
        # Validate input profiles
        valid_profiles = [p for p in profiles if p in self.profile_names]
        if not valid_profiles or min_agreement <= 1:
            return {}
            
        consensus = {}
        
        for field in self.fields:
            # Count operation frequencies for this field
            op_counts = {}
            for profile in valid_profiles:
                op = self.matrix[field].get(profile, 'X')
                op_counts[op] = op_counts.get(op, 0) + 1
            
            # Find operation with maximum count
            if op_counts:
                max_count = max(op_counts.values())
                if max_count >= min_agreement:
                    # Get the most common operation (mode)
                    best_op = max(op_counts.items(), key=lambda x: x[1])[0]
                    consensus[field] = best_op
        
        return consensus
    
    def rank_profiles_by_requirements(self, field_operations: Dict[str, str]) -> List[Tuple[str, float]]:
        """
        Rank profiles by how well they match the specified requirements.
        Returns: [(profile, match_score), ...] sorted by best match (descending)
        """
        rankings = []
        
        for profile in self.profile_names:
            matches = 0
            total = 0
            
            for field, desired_op in field_operations.items():
                if field in self.matrix:
                    total += 1
                    actual_op = self.matrix[field].get(profile, 'X')
                    if actual_op == desired_op:
                        matches += 1
            
            # Calculate match percentage
            match_score = (matches / total) if total > 0 else 0.0
            rankings.append((profile, round(match_score, 3)))
        
        # Sort by match score (descending)
        rankings.sort(key=lambda x: x[1], reverse=True)
        return rankings
    
    def cluster_profiles(self, threshold: float = 0.8) -> List[List[str]]:
        """
        Cluster profiles by similarity.
        Returns: [[profile1, profile2], [profile3], ...] clusters with similarity > threshold
        """
        similarity_matrix = self.get_profile_similarity_matrix()
        profiles = list(self.profile_names)
        clusters = []
        used_profiles = set()
        
        # Simple hierarchical clustering
        for profile in profiles:
            if profile in used_profiles:
                continue
                
            # Find all profiles similar to this one
            cluster = [profile]
            for other_profile in profiles:
                if other_profile != profile and other_profile not in used_profiles:
                    similarity = similarity_matrix[profile][other_profile]
                    if similarity >= threshold:
                        cluster.append(other_profile)
                        used_profiles.add(other_profile)
            
            used_profiles.add(profile)
            clusters.append(cluster)
        
        return clusters