#!/usr/bin/env python3
"""
Main CLI interface for anonymization profile analysis.
"""

import argparse
from profile_parser import ProfileParser
from profile_analyzer import ProfileAnalyzer

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Anonymization Profile Analyzer')
    parser.add_argument('--file', '-f', default='anonymization_profiles.csv',
                       help='Path to CSV file containing anonymization profiles')
    args = parser.parse_args()
    
    print("Anonymization Profile Analyzer")
    print("=" * 40)
    print(f"Using data file: {args.file}")
    
    # Initialize parser and analyzer with custom file path
    profile_parser = ProfileParser(args.file)
    analyzer = ProfileAnalyzer(profile_parser)
    
    # Show available profiles
    profiles = analyzer.profile_names
    print(f"Available profiles: {', '.join(profiles)}")
    print(f"Total fields: {len(analyzer.fields)}")
    
    while True:
        print("\nMenu:")
        print("1. Show profile differences (pairwise)")
        print("2. Find profiles for specific operations")
        print("3. Find profiles excluding certain fields")
        print("4. Show profile statistics")
        print("5. Compare multiple profiles (N-way)")
        print("6. Find consensus among profiles")
        print("7. Rank profiles by requirements")
        print("8. Show profile similarity matrix")
        print("9. Cluster profiles by similarity")
        print("10. Exit")
        
        choice = input("Enter your choice (1-10): ")
        
        if choice == '1':
            # Show profile differences
            print(f"\nAvailable profiles: {', '.join(profiles)}")
            profile1 = input("Enter first profile name: ")
            profile2 = input("Enter second profile name: ")
            
            if profile1 in profiles and profile2 in profiles:
                differences = analyzer.get_profile_differences(profile1, profile2)
                print(f"\nDifferences between {profile1} and {profile2}:")
                print("Field -> ({profile1}, {profile2})")
                for field, op1, op2 in differences[:10]:  # Show first 10
                    print(f"{field} -> ({op1}, {op2})")
                if len(differences) > 10:
                    print(f"... and {len(differences) - 10} more differences")
            else:
                print("Invalid profile names.")
                
        elif choice == '2':
            # Find profiles for specific operations
            print("\nEnter field-operation pairs (e.g., 'patients name:custom')")
            print("Enter 'done' when finished")
            
            field_ops = {}
            while True:
                entry = input("Field:operation (or 'done'): ")
                if entry.lower() == 'done':
                    break
                
                if ':' in entry:
                    field, op = entry.split(':', 1)
                    field_ops[field.strip()] = op.strip()
                else:
                    print("Invalid format. Use 'field:operation'")
            
            if field_ops:
                matching = analyzer.find_profiles_for_operations(field_ops)
                print(f"\nMatching profiles: {', '.join(matching) if matching else 'None'}")
            else:
                print("No requirements specified.")
                
        elif choice == '3':
            # Find profiles excluding certain fields
            print("\nEnter fields to exclude from anonymization (operation = 'X')")
            print("Enter 'done' when finished")
            
            exclude_fields = set()
            while True:
                field = input("Field name (or 'done'): ")
                if field.lower() == 'done':
                    break
                exclude_fields.add(field.strip())
            
            if exclude_fields:
                matching = analyzer.find_profiles_excluding_fields(exclude_fields)
                print(f"\nProfiles that don't anonymize specified fields: {', '.join(matching) if matching else 'None'}")
            else:
                print("No fields specified.")
                
        elif choice == '4':
            # Show profile statistics
            stats = analyzer.get_profile_statistics()
            print("\nProfile Statistics:")
            for profile, counts in stats.items():
                print(f"\n{profile}:")
                for op, count in counts.items():
                    print(f"  {op}: {count} fields")
                    
        elif choice == '5':
            # Compare multiple profiles (N-way)
            print(f"\nAvailable profiles: {', '.join(profiles)}")
            print("Enter profile names separated by commas (e.g., 'profile 1, profile 2')")
            profile_list = [p.strip() for p in input("Enter profiles to compare: ").split(',')]
            
            if profile_list:
                differences = analyzer.get_multi_profile_differences(profile_list)
                print(f"\nFields with differences across {len(profile_list)} profiles:")
                print(f"Total differing fields: {len(differences)}")
                if differences:
                    print("All differences:")
                    for i, (field, ops) in enumerate(differences.items(), 1):
                        op_str = ', '.join(f"{p}:{op}" for p, op in ops.items())
                        print(f"  {i}. {field}: {op_str}")
                else:
                    print("  No differences found - all profiles are identical for the selected fields")
        
        elif choice == '6':
            # Find consensus among profiles
            print(f"\nAvailable profiles: {', '.join(profiles)}")
            print("Enter profile names separated by commas")
            profile_list = [p.strip() for p in input("Enter profiles for consensus: ").split(',')]
            min_agree = int(input("Minimum agreement (2-3): ") or "2")
            
            if profile_list and 2 <= min_agree <= len(profile_list):
                consensus = analyzer.find_consensus_fields(profile_list, min_agree)
                print(f"\nConsensus fields (agreement >= {min_agree}): {len(consensus)} fields")
                if consensus:
                    print("Sample consensus fields:")
                    for field, op in list(consensus.items())[:10]:
                        print(f"  {field}: {op}")
                    if len(consensus) > 10:
                        print(f"  ... and {len(consensus) - 10} more fields")
        
        elif choice == '7':
            # Rank profiles by requirements
            print("\nEnter field-operation pairs for ranking (e.g., 'patients name:custom')")
            print("Enter 'done' when finished")
            
            field_ops = {}
            while True:
                entry = input("Field:operation (or 'done'): ")
                if entry.lower() == 'done':
                    break
                
                if ':' in entry:
                    field, op = entry.split(':', 1)
                    field_ops[field.strip()] = op.strip()
                else:
                    print("Invalid format. Use 'field:operation'")
            
            if field_ops:
                ranked = analyzer.rank_profiles_by_requirements(field_ops)
                print(f"\nProfile rankings for your requirements:")
                for profile, score in ranked:
                    print(f"  {profile}: {score*100:.1f}% match")
        
        elif choice == '8':
            # Show profile similarity matrix
            similarity = analyzer.get_profile_similarity_matrix()
            print("\nProfile Similarity Matrix (Jaccard similarity):")
            print(" ".join([f"{p:20}" for p in profiles]))
            for profile1 in profiles:
                row = [profile1]
                for profile2 in profiles:
                    row.append(f"{similarity[profile1][profile2]:.3f}")
                print(" ".join([f"{item:20}" for item in row]))
        
        elif choice == '9':
            # Cluster profiles by similarity
            threshold = float(input("\nEnter similarity threshold (0.0-1.0, default 0.8): ") or "0.8")
            clusters = analyzer.cluster_profiles(threshold)
            print(f"\nProfile clusters (similarity >= {threshold}):")
            for i, cluster in enumerate(clusters):
                print(f"  Cluster {i+1}: {', '.join(cluster)}")
        
        elif choice == '10':
            print("Goodbye!")
            break
            
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()