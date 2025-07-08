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


def find_class_xml_files(classes_dir=None):
    """Find all class documentation XML files."""
    if classes_dir is None:
        classes_dir = "../Classes"
    pattern = os.path.join(classes_dir, "*-Documentation.xml")
    files = glob.glob(pattern)
    files.sort()  # Ensure consistent ordering
    return files

def extract_sections_from_file(filepath):
    """Returns the sections dict from XMLFileReader.read_xml_file()"""
    try:
        xml_data = XMLFileReader.read_xml_file(filepath)
        return xml_data['sections']
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        raise  # Re-raise the exception to make it fatal

def build_combined_xml(classes_dir=None, output_dir=None):
    """Main function to build the combined XML file."""
    print("Building Assembly-CSharp.xml from individual class documentation files...")
    
    # Find all class documentation files
    class_files = find_class_xml_files(classes_dir)
    
    if not class_files:
        print(f"No class documentation files found ({os.path.join(classes_dir or '../Classes', '*-Documentation.xml')})")
        return False
    
    print(f"Found {len(class_files)} class documentation files:")
    
    # Build the proper data structure for XMLFileWriter
    output_data = {
        'header_lines': [
            '<?xml version="1.0" encoding="utf-8"?>',
            '<doc>',
            '    <assembly>',
            '        <name>Assembly-CSharp</name>',
            '    </assembly>',
            '    <members>'
        ],
        'footer_lines': ['    </members>', '</doc>'],
        'sections': {}
    }
    
    total_members = 0
    
    # Process each class file
    for filepath in class_files:
        print(f"  Processing {filepath}...")
        
        # Extract sections from this file
        file_sections = extract_sections_from_file(filepath)
        
        if file_sections:
            # Count members in this file
            member_count = 0
            for section_data in file_sections.values():
                # Count from subsections if they exist, otherwise from main members list
                if section_data.get('subsections'):
                    for subsec_data in section_data['subsections'].values():
                        member_count += len(subsec_data['members'])
                else:
                    member_count += len(section_data['members'])
            
            class_name = os.path.basename(filepath).replace('-Documentation.xml', '')
            
            # Add sections from this file with class name prefix to avoid merging
            for section_name, section_data in file_sections.items():
                # Create unique section name with class prefix
                prefixed_section_name = f"{class_name} - {section_name}"
                
                # Create a copy of section_data to avoid modifying the original
                prefixed_section_data = {
                    'comments': [],
                    'members': section_data['members'][:],  # Copy the members list
                    'subsections': {}
                }
                
                # Update comments to include class name
                for comment in section_data['comments']:
                    # Extract comment content and add class prefix
                    if '<!--' in comment and '-->' in comment:
                        # Find the comment content between <!-- and -->
                        start = comment.find('<!--') + 4
                        end = comment.find('-->')
                        comment_content = comment[start:end].strip()
                        # Reconstruct comment with class prefix
                        prefixed_comment = f"<!-- {class_name} - {comment_content} -->"
                        prefixed_section_data['comments'].append(prefixed_comment)
                    else:
                        prefixed_section_data['comments'].append(comment)
                
                # Handle subsections if they exist
                if section_data.get('subsections'):
                    for subsec_type, subsec_data in section_data['subsections'].items():
                        # Update subsection comment to include class name
                        subsec_comment = subsec_data['comment']
                        if '<!--' in subsec_comment and '-->' in subsec_comment:
                            start = subsec_comment.find('<!--') + 4
                            end = subsec_comment.find('-->')
                            comment_content = subsec_comment[start:end].strip()
                            prefixed_comment = f"<!-- {class_name} - {comment_content} -->"
                        else:
                            prefixed_comment = subsec_comment
                        
                        prefixed_section_data['subsections'][subsec_type] = {
                            'comment': prefixed_comment,
                            'members': subsec_data['members'][:]  # Copy members list
                        }
                
                # Add to output data
                output_data['sections'][prefixed_section_name] = prefixed_section_data
            
            total_members += member_count
            print(f"    Added {member_count} members from {class_name}")
        else:
            print(f"    Warning: No sections found in {filepath}")
    
    # Write the combined XML file
    if output_dir is None:
        output_file = "../Assembly-CSharp.xml"
    else:
        output_file = os.path.join(output_dir, "Assembly-CSharp.xml")
    
    try:
        # Use XMLFileWriter to write the file with proper subsection handling
        XMLFileWriter.write_xml_file(output_file, output_data)
        
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