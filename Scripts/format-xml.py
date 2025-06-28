#!/usr/bin/env python3
"""
XML formatter for Broforce documentation that preserves the exact formatting style.
Can be used both as a standalone script and imported by other Python scripts.

This is the refactored version using xml_utils.

Usage as script:
    python3 format-xml.py [file_or_directory]
    
Usage in other scripts:
    from format_xml import format_xml_file
    format_xml_file('path/to/file.xml')
"""

import re
import argparse
import sys
import os
from pathlib import Path
from typing import List, Optional

# Import from xml_utils
from xml_utils import XMLPatterns, XMLFormatter

class BroforceXMLFormatter:
    """Formatter that matches the exact Broforce documentation XML style."""
    
    def __init__(self):
        self.indent = '    '  # 4 spaces per level
        self.target_line_length = 100  # Target total line length including indentation
        self.formatter = XMLFormatter()  # Use XMLFormatter for utilities
        
    def format_content(self, content: str) -> str:
        """
        Format XML content string and return formatted string.
        This is the main entry point for programmatic use.
        """
        # Normalize line endings
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        
        lines = []
        
        # XML declaration
        lines.append('<?xml version="1.0" encoding="utf-8"?>')
        
        # Extract main structure using patterns from xml_utils
        doc_match = XMLPatterns.DOC.search(content)
        if not doc_match:
            raise ValueError("Invalid XML: No <doc> element found")
        
        lines.append('<doc>')
        doc_content = doc_match.group(1)
        
        # Process assembly
        assembly_match = XMLPatterns.ASSEMBLY.search(doc_content)
        if assembly_match:
            lines.append(f'{self.indent}<assembly>')
            lines.append(f'{self.indent * 2}<name>Assembly-CSharp</name>')
            lines.append(f'{self.indent}</assembly>')
        
        # Process members
        members_match = XMLPatterns.MEMBERS.search(doc_content)
        if members_match:
            lines.append(f'{self.indent}<members>')
            
            members_content = members_match.group(1)
            
            # Split into comments and members while preserving order
            pattern = r'(<!--[^>]*-->)|(<member[^>]*>(?:(?!</member>).)*</member>)'
            matches = re.finditer(pattern, members_content, re.DOTALL)
            
            for match in matches:
                if match.group(1):  # Comment
                    comment = match.group(1)
                    comment_match = XMLPatterns.COMMENT.search(comment)
                    if comment_match:
                        comment_text = comment_match.group(1)
                        lines.append(f'{self.indent * 2}<!-- {comment_text} -->')
                elif match.group(2):  # Member
                    member_xml = match.group(2)
                    self._format_member(member_xml, lines)
            
            lines.append(f'{self.indent}</members>')
        
        lines.append('</doc>')
        
        # Join with newlines but no trailing newline
        return '\n'.join(lines)
    
    def format_file(self, file_path: str) -> None:
        """
        Format a single XML file in place.
        
        Args:
            file_path: Path to the XML file to format
        """
        file_path = str(file_path)  # Handle Path objects
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            formatted = self.format_content(content)
            
            # Write without trailing newline
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                f.write(formatted)
                
            print(f"✓ Formatted: {file_path}")
            
        except Exception as e:
            print(f"✗ Error formatting {file_path}: {e}")
            raise
    
    def _format_member(self, member_xml: str, lines: List[str]) -> None:
        """Format a single member element."""
        # Extract member name using pattern from xml_utils
        name_match = XMLPatterns.MEMBER_NAME.search(member_xml)
        if not name_match:
            return
        
        member_name = name_match.group(1)
        
        # Always keep member tag on one line for Visual Studio IntelliSense compatibility
        indent2 = self.indent * 2
        member_line = f'{indent2}<member name="{member_name}">'
        lines.append(member_line)
        
        # Extract and format child elements
        self._format_summary(member_xml, lines)
        self._format_params(member_xml, lines)
        self._format_returns(member_xml, lines)
        self._format_remarks(member_xml, lines)
        
        lines.append(f'{indent2}</member>')
    
    def _format_summary(self, member_xml: str, lines: List[str]) -> None:
        """Format summary element with proper text wrapping."""
        summary_match = XMLPatterns.SUMMARY.search(member_xml)
        if not summary_match:
            return
        
        summary_text = summary_match.group(1).strip()
        summary_text = ' '.join(summary_text.split())  # Normalize whitespace
        
        if not summary_text:
            return
        
        indent3 = self.indent * 3
        indent4 = self.indent * 4
        lines.append(f'{indent3}<summary>')
        
        # Wrap text considering the indentation
        wrapped = self._wrap_text(summary_text, indent4)
        for line in wrapped:
            lines.append(f'{indent4}{line}')
        
        lines.append(f'{indent3}</summary>')
    
    def _format_params(self, member_xml: str, lines: List[str]) -> None:
        """Format param elements - always on one line."""
        params = XMLPatterns.PARAM.findall(member_xml)
        
        indent3 = self.indent * 3
        for param_name, param_desc in params:
            param_desc = ' '.join(param_desc.strip().split())
            lines.append(f'{indent3}<param name="{param_name}">{param_desc}</param>')
    
    def _format_returns(self, member_xml: str, lines: List[str]) -> None:
        """Format returns element - always on one line."""
        returns_match = XMLPatterns.RETURNS.search(member_xml)
        if returns_match:
            returns_text = ' '.join(returns_match.group(1).strip().split())
            indent3 = self.indent * 3
            lines.append(f'{indent3}<returns>{returns_text}</returns>')
    
    def _format_remarks(self, member_xml: str, lines: List[str]) -> None:
        """Format remarks element - uses same multi-line format as summary."""
        remarks_match = XMLPatterns.REMARKS.search(member_xml)
        if remarks_match:
            remarks_text = ' '.join(remarks_match.group(1).strip().split())
            
            if not remarks_text:
                return
                
            indent3 = self.indent * 3
            indent4 = self.indent * 4
            lines.append(f'{indent3}<remarks>')
            
            wrapped = self._wrap_text(remarks_text, indent4)
            for line in wrapped:
                lines.append(f'{indent4}{line}')
            
            lines.append(f'{indent3}</remarks>')
    
    def _wrap_text(self, text: str, indent: str) -> List[str]:
        """
        Wrap text to match the exact pattern observed in formatted files.
        Total line length (including indent) aims for ~96 characters.
        """
        words = text.split()
        lines = []
        current_line = []
        
        # Calculate available width for text
        available_width = self.target_line_length - len(indent)
        
        for word in words:
            # Calculate current line length if we add this word
            if current_line:
                test_length = len(' '.join(current_line + [word]))
            else:
                test_length = len(word)
            
            # Check if adding this word would exceed the limit
            if test_length > available_width and current_line:
                # Finish current line
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                current_line.append(word)
        
        # Add remaining words
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines


# Convenience functions for use by other scripts
_formatter = BroforceXMLFormatter()

def format_xml_file(file_path: str) -> None:
    """
    Format an XML file using Broforce documentation standards.
    
    Args:
        file_path: Path to the XML file
    """
    _formatter.format_file(file_path)

def format_xml_content(content: str) -> str:
    """
    Format XML content string and return the formatted result.
    
    Args:
        content: XML content as a string
        
    Returns:
        Formatted XML content
    """
    return _formatter.format_content(content)


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
    
    formatter = BroforceXMLFormatter()
    
    # If no paths provided, use current directory
    if not args.paths:
        args.paths = ['.']
    
    # Process each path
    files_formatted = 0
    
    for path_str in args.paths:
        path = Path(path_str)
        
        if path.is_file() and path.suffix.lower() == '.xml':
            # Format single file
            formatter.format_file(str(path))
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
                formatter.format_file(str(xml_file))
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