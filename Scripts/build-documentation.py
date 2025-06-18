#!/usr/bin/env python3
"""
Broforce Documentation Build Script

Combines individual class XML documentation files into a single Assembly-CSharp.xml
file that's compatible with .NET tooling (Visual Studio, IntelliSense, etc.).
Handles all XML tags including remarks while preserving special formatting for
summary, param, returns, and value tags.

Usage: python build-documentation.py
"""

import os
import glob
from xml.etree.ElementTree import Element, SubElement, tostring, parse, ParseError
import sys
from pathlib import Path

# Add Scripts directory to path for imports
import importlib.util
spec = importlib.util.spec_from_file_location("format_xml", Path(__file__).parent / "format-xml.py")
format_xml = importlib.util.module_from_spec(spec)
spec.loader.exec_module(format_xml)
format_xml_file = format_xml.format_xml_file

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

def format_element_generic(element, indent_level=0):
    """Format any XML element generically with proper indentation."""
    indent = "    " * indent_level
    lines = []
    
    # Special handling for known tags to match original formatting
    if element.tag in ['summary', 'remarks']:
        lines.append(f'{indent}<{element.tag}>')
        if element.text and element.text.strip():
            # Handle multi-line text
            text = element.text.strip()
            text_lines = text.split('\n')
            for text_line in text_lines:
                if text_line.strip():
                    escaped_line = escape_xml_text(text_line.strip())
                    lines.append(f'{indent}{escaped_line}')
        lines.append(f'{indent}</{element.tag}>')
        return lines
    
    elif element.tag == 'param':
        param_name = element.get('name')
        param_text = escape_xml_text(element.text.strip() if element.text else "")
        lines.append(f'{indent}<param name="{param_name}">{param_text}</param>')
        return lines
    
    elif element.tag == 'returns':
        returns_text = escape_xml_text(element.text.strip() if element.text else "")
        lines.append(f'{indent}<returns>{returns_text}</returns>')
        return lines
    
    elif element.tag == 'value':
        value_text = escape_xml_text(element.text.strip() if element.text else "")
        lines.append(f'{indent}<value>{value_text}</value>')
        return lines
    
    # Generic handling for all other tags (like remarks)
    # Build opening tag with attributes
    tag_parts = [element.tag]
    for attr_name, attr_value in element.attrib.items():
        tag_parts.append(f'{attr_name}="{attr_value}"')
    opening_tag = f'{indent}<{" ".join(tag_parts)}>'
    
    # Check if element has children or text
    has_children = len(element) > 0
    has_text = element.text and element.text.strip()
    
    if not has_children and not has_text:
        # Self-closing tag
        lines.append(f'{indent}<{" ".join(tag_parts)} />')
    elif has_text and not has_children:
        # Simple element with text only
        text = escape_xml_text(element.text.strip())
        lines.append(f'{opening_tag}{text}</{element.tag}>')
    else:
        # Complex element
        lines.append(opening_tag)
        
        # Add text if present
        if has_text:
            # Handle multi-line text
            text_lines = element.text.strip().split('\n')
            for text_line in text_lines:
                if text_line.strip():
                    escaped_line = escape_xml_text(text_line.strip())
                    lines.append(f'{indent}    {escaped_line}')
        
        # Process child elements
        for child in element:
            child_lines = format_element_generic(child, indent_level + 1)
            lines.extend(child_lines)
        
        # Closing tag
        lines.append(f'{indent}</{element.tag}>')
    
    # Handle tail text (text after the element)
    if element.tail and element.tail.strip():
        lines.append(escape_xml_text(element.tail.strip()))
    
    return lines

def format_xml_clean(root):
    """Format XML with clean, minimal whitespace."""
    lines = ['<doc>']
    lines.append('    <assembly>')
    lines.append('        <name>Assembly-CSharp</name>')
    lines.append('    </assembly>')
    lines.append('    <members>')
    
    # Process each member element
    members = root.find('members')
    for i, member in enumerate(members):
        if i > 0:
            lines.append('')  # Blank line between members
        
        # Format member element generically
        member_lines = format_element_generic(member, 2)
        lines.extend(member_lines)
    
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
            # Add members to the master document
            for member in members:
                members_container.append(member)
            
            class_name = os.path.basename(filepath).replace('-Documentation.xml', '')
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
        
        # Format the XML file
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