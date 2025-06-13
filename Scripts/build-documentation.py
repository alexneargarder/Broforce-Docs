#!/usr/bin/env python3
"""
Broforce Documentation Build Script

Combines individual class XML documentation files into a single Assembly-CSharp.xml
file that's compatible with .NET tooling (Visual Studio, IntelliSense, etc.).

Usage: python build-documentation.py
"""

import os
import glob
from xml.etree.ElementTree import Element, SubElement, tostring, parse, ParseError
from xml.dom import minidom
import sys
import html

def escape_xml_text(text):
    """Escape special XML characters in text content."""
    if text is None:
        return ""
    # Replace XML special characters with their entities
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text

def create_master_xml():
    """Create the master XML structure with assembly information."""
    root = Element("doc")
    
    # Add assembly information
    assembly = SubElement(root, "assembly")
    name = SubElement(assembly, "name")
    name.text = "Assembly-CSharp"
    
    # Add members container
    members = SubElement(root, "members")
    
    return root, members

def find_class_xml_files():
    """Find all class documentation XML files."""
    pattern = "../Classes/*-Documentation.xml"
    files = glob.glob(pattern)
    files.sort()  # Ensure consistent ordering
    return files

def extract_members_from_file(filepath):
    """Extract member elements from a class documentation file."""
    try:
        tree = parse(filepath)
        root = tree.getroot()
        
        # Find the members section
        members_section = root.find("members")
        if members_section is None:
            print(f"Warning: No <members> section found in {filepath}")
            return []
        
        return list(members_section)
    
    except ParseError as e:
        print(f"Error parsing {filepath}: {e}")
        return []
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return []

def format_xml_clean(root):
    """Format XML with clean, minimal whitespace like the original."""
    lines = ['<doc>']
    lines.append('    <assembly>')
    lines.append('        <name>Assembly-CSharp</name>')
    lines.append('    </assembly>')
    lines.append('    <members>')
    
    # Process each member element
    members = root.find('members')
    for member in members:
        # Add member opening tag
        name_attr = member.get('name')
        lines.append(f'        <member name="{name_attr}">')
        
        # Process child elements (summary, param, returns, value, etc.)
        for child in member:
            if child.tag == 'summary':
                lines.append('            <summary>')
                if child.text and child.text.strip():
                    # Handle multi-line summaries
                    summary_text = child.text.strip()
                    summary_lines = summary_text.split('\n')
                    for summary_line in summary_lines:
                        if summary_line.strip():
                            escaped_line = escape_xml_text(summary_line.strip())
                            lines.append(f'            {escaped_line}')
                lines.append('            </summary>')
            
            elif child.tag == 'param':
                param_name = child.get('name')
                param_text = escape_xml_text(child.text.strip() if child.text else "")
                lines.append(f'            <param name="{param_name}">{param_text}</param>')
            
            elif child.tag == 'returns':
                returns_text = escape_xml_text(child.text.strip() if child.text else "")
                lines.append(f'            <returns>{returns_text}</returns>')
            
            elif child.tag == 'value':
                value_text = escape_xml_text(child.text.strip() if child.text else "")
                lines.append(f'            <value>{value_text}</value>')
        
        lines.append('        </member>')
        lines.append('')  # Single blank line between members
    
    lines.append('    </members>')
    lines.append('</doc>')
    
    return '\n'.join(lines)

def build_combined_xml():
    """Main function to build the combined XML file."""
    print("Building Assembly-CSharp.xml from individual class documentation files...")
    
    # Create master XML structure
    root, members_container = create_master_xml()
    
    # Find all class documentation files
    class_files = find_class_xml_files()
    
    if not class_files:
        print("No class documentation files found (../Classes/*-Documentation.xml)")
        return False
    
    print(f"Found {len(class_files)} class documentation files:")
    
    total_members = 0
    
    # Process each class file
    for filepath in class_files:
        print(f"  Processing {filepath}...")
        
        # Extract members from this file
        members = extract_members_from_file(filepath)
        
        if members:
            # Add a comment separator for this class
            class_name = os.path.basename(filepath).replace('-Documentation.xml', '')
            comment_text = f" {class_name} Members "
            comment = f"<!-- {comment_text} -->"
            
            # Add comment and members to the master document
            # Note: We'll add comments manually in the final formatting
            for member in members:
                members_container.append(member)
            
            total_members += len(members)
            print(f"    Added {len(members)} members from {class_name}")
        else:
            print(f"    Warning: No members found in {filepath}")
    
    # Write the combined XML file
    output_file = "../Assembly-CSharp.xml"
    
    # Format and write
    try:
        formatted_xml = format_xml_clean(root)
        
        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0"?>\n')
            f.write(formatted_xml)
        
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
    
    # Change to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    success = build_combined_xml()
    
    if success:
        print("\nBuild completed successfully!")
        sys.exit(0)
    else:
        print("\nBuild failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()