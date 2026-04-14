# Mathematical Foundations for Anonymization Profile Analysis

I generated this document primarly for me to understand/review the underyling mathematical principles. Maybe somebody else is also interested in them :)

This document describes the mathematical principles underlying the anonymization profile analysis system, including set theory operations, similarity measures, and clustering algorithms.

## Table of Contents

1. [Set Theory Operations](#set-theory-operations)
2. [Jaccard Similarity](#jaccard-similarity)
3. [Mode and Frequency Analysis](#mode-and-frequency-analysis)
4. [Hierarchical Clustering](#hierarchical-clustering)
5. [Application to Anonymization Profiles](#application-to-anonymization-profiles)

## Set Theory Operations

### Basic Set Operations

```
A = {fields with operation in profile1}
B = {fields with operation in profile2}
```

#### 1. Set Difference (A - B)
**Purpose**: Find fields that differ between two profiles
**Formula**: A - B = {x ∈ A | x ∉ B}
**Application**: Profile comparison, difference detection

```
Example:
A = {study_date:remove, patient_name:custom}
B = {study_date:modify, patient_name:custom}
A - B = {study_date}  (different operations)
```

**Venn Diagram**:
```
        _______________
       |               |
       |       A       |
       |   ________    |
       |  |        |   |
       |  | A ∩ B  |   |
       |  |________|   |
       |               |
       |_______________|
           |        |
           | A - B  |
           |________|
```

#### 2. Set Intersection (A ∩ B)
**Purpose**: Find fields that match criteria across profiles
**Formula**: A ∩ B = {x | x ∈ A ∧ x ∈ B}
**Application**: Profile selection, requirement matching

```
Example:
Find profiles where patient_name = 'custom'
A = {profile1, profile2, profile3}  (all profiles)
B = {profile1, profile2}       (profiles with patient_name='custom')
A ∩ B = {profile1, profile2}   (matching profiles)
```

**Venn Diagram**:
```
        _______________
       |               |
       |       A       |
       |   ________    |
       |  |        |   |
       |  | A ∩ B  |   |
       |  |________|   |
       |               |
       |_______________|
           B
```

#### 3. Set Complement (Universal - A)
**Purpose**: Find fields not in a set (exclusion)
**Formula**: A' = U - A where U is universal set
**Application**: Field exclusion, finding profiles that don't anonymize certain fields

```
Example:
U = {all_profiles}
A = {profiles where study_date='X'}
A' = {profiles where study_date≠'X'}  (profiles that anonymize study_date)
```

**Venn Diagram**:
```
        _______________
       |               |
       |       A       |
       |_______________|
           Universal Set
```

### N-Way Set Operations

For multiple profiles (N > 2), we extend set operations:

#### Multi-profile Difference Detection
```python
# For field f across profiles P1, P2, ..., Pn
operations = {op1, op2, ..., opn}
if |operations| > 1:
    field_has_differences = True
```

#### Consensus Finding (Generalized Intersection)
```python
# Find fields where ≥ k profiles agree
for each field:
    count_operations(op) for all profiles
    if max_count ≥ k:
        consensus_operation = op_with_max_count
```

## Jaccard Similarity

### Definition
**Purpose**: Measure similarity between two profiles
**Formula**: J(A, B) = |A ∩ B| / |A ∪ B|
**Range**: 0.0 (completely different) to 1.0 (identical)

### Properties
- **Symmetric**: J(A, B) = J(B, A)
- **Reflexive**: J(A, A) = 1.0
- **Range**: 0 ≤ J(A, B) ≤ 1
- **Normalized**: Accounts for both overlap and total size

### Application to Profiles
```python
# Convert profile to set of (field, operation) tuples
profile_set = {(field1, op1), (field2, op2), ...}

# Calculate similarity between two profiles
intersection_size = |profile_set_A ∩ profile_set_B|
union_size = |profile_set_A ∪ profile_set_B|
similarity = intersection_size / union_size
```

### Example
```
Profile A: {study_date:remove, patient_name:custom, birth_date:remove}
Profile B: {study_date:modify, patient_name:custom, birth_date:remove}

A ∩ B = {(patient_name, custom), (birth_date, remove)}  # size = 2
A ∪ B = {(study_date, remove), (study_date, modify), (patient_name, custom), (birth_date, remove)}  # size = 4

J(A, B) = 2/4 = 0.5
```

**Venn Diagram for Jaccard Similarity**:
```
        _______________
       |               |
       |       A       |
       |   ________    |
       |  |        |   |
       |  | A ∩ B  |   |
       |  |________|   |
       |               |
       |_______________|
           _______________
          |               |
          |       B       |
          |_______________|

Jaccard = |A ∩ B| / |A ∪ B|
```

## Mode and Frequency Analysis

### Definitions
- **Mode**: Most frequent value in a dataset
- **Frequency**: Count of occurrences of a value
- **Relative Frequency**: frequency / total_count

### Application to Consensus Finding
```python
# For a given field across multiple profiles:
operations = ['remove', 'modify', 'remove', 'X']
frequency = {'remove': 2, 'modify': 1, 'X': 1}
mode = 'remove'  # most frequent
max_frequency = 2
relative_frequency = 2/4 = 0.5  # 50% agreement
```

### Consensus Algorithm
```python
def find_consensus(field, profiles, min_agreement):
    op_counts = {}
    for profile in profiles:
        op = profile[field]
        op_counts[op] = op_counts.get(op, 0) + 1
    
    if op_counts:
        max_count = max(op_counts.values())
        if max_count >= min_agreement:
            best_op = argmax(op_counts)
            return best_op
    return None
```

### Example
```
Field: study_date
Profiles: [profile 1:X, profile 2:modify, product:remove]

Operation counts: {'X':1, 'modify':1, 'remove':1}
Max count: 1
If min_agreement=2: No consensus
If min_agreement=1: Consensus not meaningful
```

## Hierarchical Clustering

### Algorithm
1. **Calculate similarity matrix** (using Jaccard similarity)
2. **Start with each profile as its own cluster**
3. **Merge clusters** based on similarity threshold
4. **Repeat** until no more merges possible

### Types of Linkage
- **Single linkage**: Minimum distance between clusters
- **Complete linkage**: Maximum distance between clusters  
- **Average linkage**: Average distance between clusters

### Our Implementation (Single Linkage)
```python
def cluster_profiles(similarity_matrix, threshold):
    clusters = []
    used_profiles = set()
    
    for profile in profiles:
        if profile in used_profiles:
            continue
            
        cluster = [profile]
        for other_profile in profiles:
            if other_profile != profile and other_profile not in used_profiles:
                if similarity_matrix[profile][other_profile] >= threshold:
                    cluster.append(other_profile)
                    used_profiles.add(other_profile)
        
        used_profiles.add(profile)
        clusters.append(cluster)
    
    return clusters
```

### Example
```
Profiles: [A, B, C]
Similarity: J(A,B)=0.95, J(A,C)=0.85, J(B,C)=0.88

Threshold = 0.9:
- Cluster 1: [A, B]  (J=0.95 ≥ 0.9)
- Cluster 2: [C]     (J=0.85 < 0.9, J=0.88 < 0.9)

Threshold = 0.8:
- Cluster 1: [A, B, C]  (all similarities ≥ 0.8)
```

**Dendrogram Representation**:
```
        ___________________
       |                   |
    ___|___             ___|___
   |       |           |       |
   A       B           C       (Threshold 0.9)
   
        ___________________
       |                   |
       |       ____________|____
       |      |            |    |
       A      B            C    (Threshold 0.8)
```

## Application to Anonymization Profiles

### Problem Mapping
```
Profiles → Sets of (field, operation) pairs
Fields → Dimensions in feature space
Operations → Categorical values (remove, modify, custom, X)
Profile comparison → Set similarity measurement
```

### How Mathematical Foundations Achieve Goals

#### 1. Comparison (Set Difference)
**Goal**: Find differences between profiles
**Math**: A - B = fields where operations differ
**Benefit**: Quick identification of policy variations

#### 2. Difference Detection (N-way Set Operations)
**Goal**: Find fields with variations across N profiles  
**Math**: |unique_operations| > 1 for each field
**Benefit**: Comprehensive multi-profile analysis

#### 3. Consensus Finding (Mode Analysis)
**Goal**: Find fields where profiles agree
**Math**: Mode operation with frequency threshold
**Benefit**: Identify standard practices and common ground

#### 4. Grouping (Hierarchical Clustering)
**Goal**: Group similar profiles together
**Math**: Jaccard similarity + threshold-based clustering
**Benefit**: Profile categorization and similarity discovery

### Mathematical Properties That Enable Analysis

1. **Set Operations are Efficient**:
   - Difference: O(n) per field
   - Intersection: O(min(|A|,|B|))
   - Union: O(|A| + |B|)

2. **Jaccard Similarity is Robust**:
   - Handles different profile sizes
   - Normalized (0-1 range)
   - Intuitive interpretation

3. **Mode Analysis is Deterministic**:
   - Always finds most common operation
   - Frequency threshold controls consensus strength
   - Handles ties gracefully

4. **Clustering is Flexible**:
   - Threshold parameter controls granularity
   - Hierarchical approach preserves relationships
   - Visualizable via dendrograms

## Complexity Analysis

### Time Complexity
```
Operation                          Complexity          Notes
-------------------------          ------------        -----
Set Difference                     O(F)                F = fields
Set Intersection                   O(F)                F = fields  
Set Complement                     O(F)                F = fields
Multi-profile differences          O(N*F)              N = profiles, F = fields
Jaccard Similarity Matrix          O(P²*F)             P = profiles, F = fields
Consensus Finding                   O(N*F)              N = profiles, F = fields
Profile Ranking                    O(P*R)              P = profiles, R = requirements
Hierarchical Clustering            O(P²)               P = profiles
```

### Space Complexity
```
Data Structure                     Complexity          Notes
-------------------------          ------------        -----
Profile Matrix                     O(P*F)              P = profiles, F = fields
Similarity Matrix                  O(P²)               P = profiles
Consensus Results                  O(F)                F = fields
Clustering Results                 O(P)                P = profiles
```

## Summary

The mathematical foundations provide a robust framework for anonymization profile analysis:

- **Set Theory** enables efficient comparison and difference detection
- **Jaccard Similarity** provides meaningful profile similarity measurement
- **Mode Analysis** facilitates consensus finding across multiple profiles
- **Hierarchical Clustering** allows profile grouping and categorization

These mathematical tools work together to solve the core problems:
- **Comparison**: "What are the differences between profiles?"
- **Selection**: "Which profile matches my requirements?"
- **Consensus**: "Where do profiles agree?"
- **Grouping**: "Which profiles are similar?"

The implementation leverages these mathematical principles to provide comprehensive, efficient, and intuitive analysis of anonymization profiles.