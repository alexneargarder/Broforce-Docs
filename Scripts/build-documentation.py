#!/usr/bin/env python3
"""
Broforce Documentation Build Script

Combines individual class XML documentation files into a single Assembly-CSharp.xml
file that's compatible with .NET tooling (Visual Studio, IntelliSense, etc.).

This is the refactored version using xml_utils.

Usage: python build-documentation.py
"""

import os
import glob
import sys
from pathlib import Path

# Import from xml_utils
from xml_utils import XMLFileReader, XMLFileWriter, XMLFormatter, XMLPatterns

# Import format_xml_file with proper path handling
import importlib.util
spec = importlib.util.spec_from_file_location("format_xml", Path(__file__).parent / "format-xml.py")
format_xml = importlib.util.module_from_spec(spec)
spec.loader.exec_module(format_xml)
format_xml_file = format_xml.format_xml_file

def find_class_xml_files(classes_dir=None):
    """Find all class documentation XML files."""
    if classes_dir is None:
        classes_dir = "../Classes"
    pattern = os.path.join(classes_dir, "*-Documentation.xml")
    files = glob.glob(pattern)
    files.sort()  # Ensure consistent ordering
    return files

def extract_members_lines_from_file(filepath):
    """Extract member element lines from a class documentation file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        
        # Find members section boundaries
        members_start = -1
        members_end = -1
        
        for i, line in enumerate(lines):
            if '<members>' in line:
                members_start = i
            elif '</members>' in line:
                members_end = i
                break
        
        if members_start == -1 or members_end == -1:
            print(f"Warning: No <members> section found in {filepath}")
            return []
        
        # Extract member lines including comments
        member_lines = []
        i = members_start + 1
        
        while i < members_end:
            line = lines[i]
            
            # Include comments
            if '<!--' in line:
                member_lines.append(line)
            # Include member elements
            elif '<member' in line:
                # Start of member element
                member_element_lines = [line]
                i += 1
                
                # Collect all lines until </member>
                while i < members_end and '</member>' not in lines[i - 1]:
                    if i < len(lines):
                        member_element_lines.append(lines[i])
                    i += 1
                
                # Add all member lines
                member_lines.extend(member_element_lines)
                continue
                
            i += 1
            
        return member_lines
        
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return []

def build_combined_xml(classes_dir=None, output_dir=None):
    """Main function to build the combined XML file."""
    print("Building Assembly-CSharp.xml from individual class documentation files...")
    
    # Find all class documentation files
    class_files = find_class_xml_files(classes_dir)
    
    if not class_files:
        print(f"No class documentation files found ({os.path.join(classes_dir or '../Classes', '*-Documentation.xml')})")
        return False
    
    print(f"Found {len(class_files)} class documentation files:")
    
    # Start building output
    output_lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<doc>',
        '    <assembly>',
        '        <name>Assembly-CSharp</name>',
        '    </assembly>',
        '    <members>'
    ]
    
    total_members = 0
    
    # Process each class file
    for filepath in class_files:
        print(f"  Processing {filepath}...")
        
        # Extract member lines from this file
        member_lines = extract_members_lines_from_file(filepath)
        
        if member_lines:
            # Count actual members (not comments)
            member_count = sum(1 for line in member_lines if '<member' in line)
            
            # Add member lines to output
            output_lines.extend(member_lines)
            
            class_name = os.path.basename(filepath).replace('-Documentation.xml', '')
            total_members += member_count
            print(f"    Added {member_count} members from {class_name}")
        else:
            print(f"    Warning: No members found in {filepath}")
    
    # Close XML structure
    output_lines.extend([
        '    </members>',
        '</doc>'
    ])
    
    # Write the combined XML file
    if output_dir is None:
        output_file = "../Assembly-CSharp.xml"
    else:
        output_file = os.path.join(output_dir, "Assembly-CSharp.xml")
    
    try:
        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(output_lines))
        
        # Format the XML file using format-xml.py
        try:
            format_xml_file(output_file)
        except Exception as e:
            print(f"❌ ERROR: Failed to format XML file: {e}")
            return False
        
        print(f"\nSuccessfully built {output_file}")
        print(f"Total members documented: {total_members}")
        print(f"Classes processed: {len(class_files)}")
        
        return True
        
    except Exception as e:
        print(f"Error writing {output_file}: {e}")
        return False

def main():
    """Main entry point."""
    print("Broforce Documentation Build Script")
    print("=" * 40)
    
    # Parse command line arguments
    classes_dir = None
    output_dir = None
    
    if len(sys.argv) > 1:
        # Check for environment variable or argument for test mode
        if sys.argv[1] == '--test' or os.environ.get('BUILD_DOC_TEST_MODE'):
            # Don't change directory in test mode
            classes_dir = os.environ.get('BUILD_DOC_CLASSES_DIR', '../Classes')
            output_dir = os.environ.get('BUILD_DOC_OUTPUT_DIR', '..')
        else:
            classes_dir = sys.argv[1]
            if len(sys.argv) > 2:
                output_dir = sys.argv[2]
    else:
        # Change to script directory for normal operation
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
    
    success = build_combined_xml(classes_dir, output_dir)
    
    if success:
        print("\nBuild completed successfully!")
        sys.exit(0)
    else:
        print("\nBuild failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()