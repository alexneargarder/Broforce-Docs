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
from xml_utils import XMLFileReader, XMLFileWriter

def format_xml_file(file_path: str) -> None:
    """
    Format an XML file using Broforce documentation standards.
    
    Args:
        file_path: Path to the XML file
    """
    file_path = str(file_path)  # Handle Path objects
    
    try:
        # Read the XML file
        xml_data = XMLFileReader.read_xml_file(file_path)
        
        # Write it back with full formatting
        XMLFileWriter.write_xml_file(file_path, xml_data, format_content=True)
        
        print(f"✓ Formatted: {file_path}")
        
    except Exception as e:
        print(f"✗ Error formatting {file_path}: {e}")
        raise

def format_xml_content(content: str) -> str:
    """
    Format XML content string and return the formatted result.
    This function is provided for backward compatibility but is no longer recommended.
    
    Args:
        content: XML content as a string
        
    Returns:
        Formatted XML content
    """
    # This would require parsing content to data structure and back
    # For now, just raise NotImplementedError
    raise NotImplementedError(
        "format_xml_content is deprecated. Use XMLFileReader and XMLFileWriter directly."
    )

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
            format_xml_file(str(path))
            files_formatted += 1
        elif path.is_dir():
            # Format all XML files in directory
            xml_files = sorted(path.glob('*.xml'))
            
            # Filter to only documentation files
            xml_files = [f for f in xml_files if '-Documentation.xml' in f.name]
            
            if not xml_files:
                print(f"No XML documentation files found in {path}")
                continue
            
            print(f"Found {len(xml_files)} XML documentation files in {path}")
            
            for xml_file in xml_files:
                format_xml_file(str(xml_file))
                files_formatted += 1
        else:
            print(f"Error: {path} is not a valid file or directory")
            continue
    
    if files_formatted == 0:
        print("No files were formatted")
        sys.exit(1)
    else:
        print(f"\nTotal files formatted: {files_formatted}")

if __name__ == '__main__':
    main()