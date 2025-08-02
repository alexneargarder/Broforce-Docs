#!/usr/bin/env python3
"""
XML formatter for Broforce documentation.
This is now a simple wrapper around xml_utils which handles all formatting.

Usage as script:
    python3 format-xml.py [file_or_directory]
    
Usage in other scripts:
    from format_xml import format_xml_file
    format_xml_file('path/to/file.xml')
"""

import argparse
import sys
import os
from pathlib import Path
from typing import List

# Import from xml_utils
from xml_utils import XMLFileReader, XMLFileWriter, quiet_print as qprint

def format_xml_file(file_path: str, remove_duplicates: bool = False) -> None:
    """
    Format an XML file using Broforce documentation standards.
    
    Args:
        file_path: Path to the XML file
        remove_duplicates: If True, remove duplicate member entries
    """
    file_path = str(file_path)  # Handle Path objects
    
    try:
        # Read the XML file
        xml_data = XMLFileReader.read_xml_file(file_path)
        
        if remove_duplicates:
            # Track seen members and remove duplicates
            seen_members = set()
            duplicates_removed = 0
            
            for section_name, section_data in xml_data.get('sections', {}).items():
                # Only process subsections if present
                if 'subsections' in section_data:
                    for subsec_name, subsec_data in section_data.get('subsections', {}).items():
                        unique_members = []
                        
                        for member_lines in subsec_data.get('members', []):
                            # Get the member name from the first line
                            member_name = None
                            for line in member_lines:
                                if '<member name="' in line:
                                    start = line.find('<member name="') + 14
                                    end = line.find('"', start)
                                    if end > start:
                                        member_name = line[start:end]
                                        break
                            
                            if member_name:
                                if member_name not in seen_members:
                                    seen_members.add(member_name)
                                    unique_members.append(member_lines)
                                else:
                                    duplicates_removed += 1
                                    qprint(f"  Removing duplicate: {member_name}")
                            else:
                                # Keep members we can't identify
                                unique_members.append(member_lines)
                        
                        subsec_data['members'] = unique_members
            
            if duplicates_removed > 0:
                qprint(f"✓ Removed {duplicates_removed} duplicate entries from {file_path}")
        
        # Write it back with full formatting
        XMLFileWriter.write_xml_file(file_path, xml_data, format_content=True)
        
        qprint(f"✓ Formatted: {file_path}")
        
    except Exception as e:
        qprint(f"✗ Error formatting {file_path}: {e}")
        raise


def main():
    """Main entry point for command-line usage."""
    parser = argparse.ArgumentParser(
        description='Format XML files to match Broforce documentation standards'
    )
    parser.add_argument(
        'paths',
        nargs='*',
        help='Path(s) to XML file(s) or directory. If no path given, formats all XML documentation files in current directory'
    )
    parser.add_argument(
        '--remove-duplicates',
        action='store_true',
        help='Remove duplicate member entries from the XML files'
    )
    args = parser.parse_args()
    
    # If no paths provided, use current directory
    if not args.paths:
        args.paths = ['.']
    
    # Process each path
    files_formatted = 0
    
    for path_str in args.paths:
        path = Path(path_str)
        
        if path.is_file() and path.suffix.lower() == '.xml':
            # Format single file
            format_xml_file(str(path), remove_duplicates=args.remove_duplicates)
            files_formatted += 1
        elif path.is_dir():
            # Format all XML files in directory
            xml_files = sorted(path.glob('*.xml'))
            
            # Filter to only documentation files
            xml_files = [f for f in xml_files if '-Documentation.xml' in f.name]
            
            if not xml_files:
                qprint(f"No XML documentation files found in {path}")
                continue
            
            qprint(f"Found {len(xml_files)} XML documentation files in {path}")
            
            for xml_file in xml_files:
                format_xml_file(str(xml_file), remove_duplicates=args.remove_duplicates)
                files_formatted += 1
        else:
            qprint(f"Error: {path} is not a valid file or directory")
            continue
    
    if files_formatted == 0:
        qprint("No files were formatted")
        sys.exit(1)
    else:
        qprint(f"\nTotal files formatted: {files_formatted}")

if __name__ == '__main__':
    main()