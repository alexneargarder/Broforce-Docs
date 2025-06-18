#!/usr/bin/env python3
"""
Convert .NET XML documentation to GitHub wiki Markdown files.
"""

import xml.etree.ElementTree as ET
import re
import os
from pathlib import Path
from collections import defaultdict
import html

def clean_xml_text(text):
    """Clean and format XML text content."""
    if not text:
        return ""
    
    # Unescape HTML entities first
    text = html.unescape(text)
    
    # Preserve some structure by converting numbered lists
    text = re.sub(r'(\d+\.\s+\*\*[^*]+\*\*)', r'\n\n\1', text)
    
    # Remove extra whitespace but preserve paragraph breaks
    text = re.sub(r'\s*\n\s*\n\s*', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    
    return text.strip()

def format_member_name(member_name):
    """Extract readable name from XML member name."""
    # Remove prefixes like M:, P:, F:, T:
    name = re.sub(r'^[MPTF]:', '', member_name)
    
    # Extract just the member name (last part after the last dot, before parameters)
    # First remove parameter info to get the clean member name
    name_no_params = re.sub(r'\([^)]*\)', '', name)
    parts = name_no_params.split('.')
    
    if len(parts) > 1:
        class_name = parts[0]
        member_simple = parts[-1]
        return class_name, member_simple
    
    return name, name

def format_parameters(member_name):
    """Extract parameter information from method signatures."""
    param_match = re.search(r'\(([^)]*)\)', member_name)
    if not param_match:
        return []
    
    params = param_match.group(1)
    if not params:
        return []
    
    # Split parameters and clean them up
    param_list = []
    for param in params.split(','):
        param = param.strip()
        if param:
            # Remove namespace prefixes for readability
            param = re.sub(r'[\w.]+\.(\w+)', r'\1', param)
            param_list.append(param)
    
    return param_list

def normalize_type_name(type_name):
    """Convert .NET type names to more readable C# equivalents."""
    type_map = {
        'System.Single': 'float',
        'Single': 'float',
        'System.Int32': 'int',
        'Int32': 'int',
        'System.Boolean': 'bool',
        'Boolean': 'bool',
        'System.String': 'string',
        'String': 'string',
        'System.Double': 'double',
        'Double': 'double',
        'System.Void': 'void',
        'Void': 'void'
    }
    
    # Handle out parameters
    if type_name.endswith('@'):
        base_type = type_name[:-1]
        normalized_base = type_map.get(base_type, base_type)
        return f"out {normalized_base}"
    
    return type_map.get(type_name, type_name)

def format_returns_as_list(returns_description):
    """Format returns section as a list."""
    if not returns_description:
        return []
    
    return [returns_description]

def format_parameters_with_descriptions(member_name, param_descriptions):
    """Format parameters with types and descriptions combined."""
    param_types = format_parameters(member_name)
    
    if not param_descriptions and not param_types:
        return []
    
    formatted_params = []
    
    # If we have parameter descriptions, use them
    if param_descriptions:
        for param_name, param_desc in param_descriptions.items():
            # Try to find matching type from signature
            param_type = "unknown"
            used_type = None
            for ptype in param_types:
                # Simple heuristic: if this is the first unused type, assign it
                # This could be improved with more sophisticated matching
                param_type = normalize_type_name(ptype)
                used_type = ptype
                break
            
            formatted_params.append(f"**{param_name}** (`{param_type}`): {param_desc}")
            # Remove the used type
            if used_type and used_type in param_types:
                param_types.remove(used_type)
    
    # If we have leftover types without descriptions, show them anyway
    for i, param_type in enumerate(param_types):
        normalized_type = normalize_type_name(param_type)
        formatted_params.append(f"**param{i+1}** (`{normalized_type}`): Parameter description not available")
    
    return formatted_params

def categorize_member(member_name):
    """Categorize member by type."""
    if member_name.startswith('M:'):
        return 'Methods'
    elif member_name.startswith('P:'):
        return 'Properties'
    elif member_name.startswith('F:'):
        return 'Fields'
    elif member_name.startswith('T:'):
        return 'Types'
    else:
        return 'Other'

def extract_class_name(member_name):
    """Extract class name from member name."""
    # Remove prefix
    name = re.sub(r'^[MPTF]:', '', member_name)
    
    # For methods/properties/fields, get the class name
    if '.' in name:
        # First, remove parameter info to avoid confusion
        name_no_params = re.sub(r'\([^)]*\)', '', name)
        parts = name_no_params.split('.')
        
        # For simple cases like "ClassName.MemberName", return "ClassName"
        if len(parts) >= 2:
            return parts[0]
        else:
            return parts[0]
    
    return name

def parse_xml_comments_sections(xml_content):
    """Parse XML content to extract section comments and their positions."""
    import re
    
    sections = []
    lines = xml_content.split('\n')
    
    for i, line in enumerate(lines):
        # Look for section comment patterns
        comment_match = re.search(r'<!--\s*([^-]+?)\s*-->', line)
        if comment_match:
            section_name = comment_match.group(1).strip()
            # Only include meaningful section names, skip utility comments
            if any(keyword in section_name.lower() for keyword in ['method', 'properties', 'field', 'lifecycle', 'audio', 'animation', 'combat', 'movement', 'system', 'effect', 'input', 'network']):
                sections.append({
                    'name': section_name,
                    'line_number': i,
                    'members': []
                })
    
    return sections

def group_related_sections(sections):
    """Group related sections (Methods/Properties/Fields) under common parent sections."""
    grouped_sections = []
    section_groups = {}
    
    for section in sections:
        # Extract the base name by removing type suffixes
        base_name = section['name']
        for suffix in [' Methods', ' Properties', ' Fields']:
            if base_name.endswith(suffix):
                base_name = base_name[:-len(suffix)]
                break
        
        # Group sections by base name
        if base_name not in section_groups:
            section_groups[base_name] = {
                'name': base_name,
                'line_number': section['line_number'],  # Use first occurrence line number
                'members': []
            }
        
        # Add all members from this section type to the grouped section
        section_groups[base_name]['members'].extend(section['members'])
    
    # Convert back to list, preserving order by line number
    grouped_sections = list(section_groups.values())
    grouped_sections.sort(key=lambda s: s['line_number'])
    
    return grouped_sections

def assign_members_to_sections(sections, members, xml_content):
    """Assign members to sections based on their position in the XML."""
    lines = xml_content.split('\n')
    
    # Find the line number for each member in the XML
    for member in members:
        member_name_attr = member['name']
        # Look for the member definition in XML
        for i, line in enumerate(lines):
            if f'name="{member_name_attr}"' in line:
                member['xml_line'] = i
                break
        else:
            member['xml_line'] = float('inf')  # Put unmatched members at end
    
    # Sort members by their XML line position
    members.sort(key=lambda m: m.get('xml_line', float('inf')))
    
    # Assign members to sections
    current_section_idx = 0
    
    for member in members:
        member_line = member.get('xml_line', float('inf'))
        
        # Find which section this member belongs to
        while (current_section_idx < len(sections) - 1 and 
               member_line > sections[current_section_idx + 1]['line_number']):
            current_section_idx += 1
        
        if current_section_idx < len(sections):
            sections[current_section_idx]['members'].append(member)
        else:
            # Create a default section for members without clear section
            if not any(s['name'] == 'Other Members' for s in sections):
                sections.append({
                    'name': 'Other Members',
                    'line_number': float('inf'),
                    'members': []
                })
            sections[-1]['members'].append(member)

def create_class_wiki_page(class_name, members, output_dir, xml_content=None):
    """Create a wiki page for a single class."""
    
    # If xml_content not provided, try to read individual class file
    if xml_content is None:
        # Try to find the individual class XML file
        xml_file = Path(f"Classes/{class_name}-Documentation.xml")
        if not xml_file.exists():
            xml_file = Path("Assembly-CSharp.xml")
    
        xml_content = ""
        if xml_file.exists():
            with open(xml_file, 'r', encoding='utf-8') as f:
                xml_content = f.read()
    
    # Parse sections from XML comments
    sections = parse_xml_comments_sections(xml_content)
    
    if sections:
        # Assign members to sections based on XML position
        assign_members_to_sections(sections, members, xml_content)
        
        # Group related sections under common parents
        sections = group_related_sections(sections)
        
        # Start building the markdown content
        lines = []
        lines.append(f"# {class_name}")
        lines.append("")
        
        # Add detailed table of contents
        lines.append("## Table of Contents")
        
        for section in sections:
            if not section['members']:  # Skip empty sections
                continue
                
            section_anchor = re.sub(r'[^\w\s-]', '', section['name']).strip().replace(' ', '-').lower()
            lines.append(f"- [{section['name']}](#{section_anchor})")
            
            # Group members within this section by type for TOC
            section_categorized = defaultdict(list)
            for member in section['members']:
                category = categorize_member(member['name'])
                section_categorized[category].append(member)
            
            # Sort members alphabetically within each subsection for TOC
            for category in ['Methods', 'Properties', 'Fields']:
                if category not in section_categorized:
                    continue
                    
                # Sort members alphabetically by simple name
                sorted_members = sorted(section_categorized[category], 
                                      key=lambda m: format_member_name(m['name'])[1].lower())
                
                category_anchor = f"{section_anchor}-{category.lower()}"
                lines.append(f"  - [{category}](#{category_anchor})")
                
                # Add individual member links
                for member in sorted_members:
                    _, member_simple = format_member_name(member['name'])
                    # Clean up member anchor generation - remove special characters and normalize
                    clean_member_name = re.sub(r'[^a-zA-Z0-9\s-]', '', member_simple).strip().replace(' ', '-').lower()
                    member_anchor = f"{section_anchor}-{category.lower()}-{clean_member_name}"
                    lines.append(f"    - [{member_simple}](#{member_anchor})")
        
        lines.append("")
        
        # Add each section
        for section in sections:
            if not section['members']:  # Skip empty sections
                continue
                
            section_anchor = re.sub(r'[^\w\s-]', '', section['name']).strip().replace(' ', '-').lower()
            lines.append(f'<a id="{section_anchor}"></a>')
            lines.append(f"## {section['name']}")
            lines.append("")
            
            # Group members within this section by type
            section_categorized = defaultdict(list)
            for member in section['members']:
                category = categorize_member(member['name'])
                section_categorized[category].append(member)
            
            # Add subsections for Methods, Properties, Fields within each section
            for category in ['Methods', 'Properties', 'Fields']:
                if category not in section_categorized:
                    continue
                
                # Sort members alphabetically within each subsection
                sorted_members = sorted(section_categorized[category], 
                                      key=lambda m: format_member_name(m['name'])[1].lower())
                
                category_anchor = f"{section_anchor}-{category.lower()}"
                lines.append(f'<a id="{category_anchor}"></a>')
                lines.append(f"### {category}")
                lines.append("")
                
                for member in sorted_members:
                    _, member_simple = format_member_name(member['name'])
                    # Clean up member anchor generation - remove special characters and normalize
                    clean_member_name = re.sub(r'[^a-zA-Z0-9\s-]', '', member_simple).strip().replace(' ', '-').lower()
                    member_anchor = f"{section_anchor}-{category.lower()}-{clean_member_name}"
                    
                    # Create member heading with anchor
                    lines.append(f'<a id="{member_anchor}"></a>')
                    lines.append(f"#### {member_simple}")
                    lines.append("")
                    
                    # Add summary
                    if member['summary']:
                        lines.append(member['summary'])
                        lines.append("")
                    
                    # Add parameters for methods (combine types and descriptions)
                    if category == 'Methods':
                        formatted_params = format_parameters_with_descriptions(member['name'], member['params'])
                        if formatted_params:
                            lines.append("**Parameters:**")
                            for param in formatted_params:
                                lines.append(f"- {param}")
                            lines.append("")
                    
                    # Add return value
                    formatted_returns = format_returns_as_list(member['returns'])
                    if formatted_returns:
                        lines.append("**Returns:**")
                        for return_info in formatted_returns:
                            lines.append(f"- {return_info}")
                        lines.append("")
                    
                    # Add value for properties
                    if member['value']:
                        lines.append(f"**Value:** {member['value']}")
                        lines.append("")
                    
                    lines.append("---")
                    lines.append("")
    else:
        # Fallback to original categorization if no sections found
        # Group members by category
        categorized = defaultdict(list)
        
        for member in members:
            category = categorize_member(member['name'])
            categorized[category].append(member)
        
        # Start building the markdown content
        lines = []
        lines.append(f"# {class_name}")
        lines.append("")
        
        # Add table of contents
        if len(categorized) > 1:
            lines.append("## Table of Contents")
            for category in ['Methods', 'Properties', 'Fields']:
                if category in categorized:
                    lines.append(f"- [{category}](#{category.lower()})")
            lines.append("")
        
        # Add each category
        for category in ['Methods', 'Properties', 'Fields']:
            if category not in categorized:
                continue
                
            lines.append(f"## {category}")
            lines.append("")
            
            # Sort members alphabetically within category
            sorted_members = sorted(categorized[category], 
                                  key=lambda m: format_member_name(m['name'])[1].lower())
            
            for member in sorted_members:
                _, member_simple = format_member_name(member['name'])
                
                # Create member heading
                lines.append(f"### {member_simple}")
                lines.append("")
                
                # Add summary
                if member['summary']:
                    lines.append(member['summary'])
                    lines.append("")
                
                # Add parameters for methods (combine types and descriptions)
                if category == 'Methods':
                    formatted_params = format_parameters_with_descriptions(member['name'], member['params'])
                    if formatted_params:
                        lines.append("**Parameters:**")
                        for param in formatted_params:
                            lines.append(f"- {param}")
                        lines.append("")
                
                # Add return value
                formatted_returns = format_returns_as_list(member['returns'])
                if formatted_returns:
                    lines.append("**Returns:**")
                    for return_info in formatted_returns:
                        lines.append(f"- {return_info}")
                    lines.append("")
                
                # Add value for properties
                if member['value']:
                    lines.append(f"**Value:** {member['value']}")
                    lines.append("")
                
                lines.append("---")
                lines.append("")
    
    # Write to file
    safe_class_name = re.sub(r'[<>:"/\\|?*]', '-', class_name)
    filename = f"{safe_class_name}.md"
    filepath = output_dir / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    return filename

def create_index_page(class_files, output_dir):
    """Create an index page listing all classes."""
    lines = []
    lines.append("# Broforce API Documentation")
    lines.append("")
    lines.append("This documentation covers Broforce classes and their members.")
    lines.append("")
    lines.append("## Classes")
    lines.append("")
    
    # Sort class files
    sorted_files = sorted(class_files.items())
    
    for class_name, filename in sorted_files:
        # Create proper GitHub wiki link (without .md extension)
        wiki_page_name = filename[:-3] if filename.endswith('.md') else filename
        lines.append(f"- [{class_name}]({wiki_page_name})")
    
    lines.append("")
    lines.append("---")
    lines.append("*Generated from Assembly-CSharp.xml documentation*")
    
    # Write index file
    with open(output_dir / "Home.md", 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

def process_single_xml_file(xml_file, output_dir, class_files):
    """Process a single XML file and generate wiki pages."""
    print(f"Parsing {xml_file}...")
    
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
        return
    
    # Read XML content for section parsing
    with open(xml_file, 'r', encoding='utf-8') as f:
        xml_content = f.read()
    
    # Group members by class
    classes = defaultdict(list)
    
    # Process each member
    members_node = root.find('members')
    if members_node is None:
        print(f"No members found in {xml_file}!")
        return
    
    for member_node in members_node.findall('member'):
        member_name = member_node.get('name', '')
        
        if not member_name:
            continue
        
        # Extract class name
        class_name = extract_class_name(member_name)
        
        # Skip if it's a type definition itself
        if member_name.startswith('T:'):
            continue
        
        # Extract member information
        summary_node = member_node.find('summary')
        summary = clean_xml_text(summary_node.text) if summary_node is not None else ""
        
        returns_node = member_node.find('returns')
        returns = clean_xml_text(returns_node.text) if returns_node is not None else ""
        
        value_node = member_node.find('value')
        value = clean_xml_text(value_node.text) if value_node is not None else ""
        
        # Extract parameters
        params = {}
        for param_node in member_node.findall('param'):
            param_name = param_node.get('name', '')
            param_desc = clean_xml_text(param_node.text) if param_node.text else ""
            if param_name:
                params[param_name] = param_desc
        
        member_info = {
            'name': member_name,
            'summary': summary,
            'returns': returns,
            'value': value,
            'params': params
        }
        
        classes[class_name].append(member_info)
    
    # Generate wiki pages for each class
    for class_name, members in classes.items():
        if not members:  # Skip empty classes
            continue
            
        print(f"Generating page for {class_name} ({len(members)} members)...")
        filename = create_class_wiki_page(class_name, members, output_dir, xml_content)
        class_files[class_name] = filename

def main():
    # Set output directory to ../GitHub.wiki
    output_dir = Path("../GitHub.wiki")
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    class_files = {}
    
    # Process all XML files in Classes directory
    classes_dir = Path("Classes")
    if classes_dir.exists():
        xml_files = list(classes_dir.glob("*-Documentation.xml"))
        print(f"Found {len(xml_files)} XML documentation files in Classes directory")
        
        for xml_file in xml_files:
            process_single_xml_file(xml_file, output_dir, class_files)
    else:
        # Fallback to Assembly-CSharp.xml if Classes directory doesn't exist
        xml_file = Path("Assembly-CSharp.xml")
        if xml_file.exists():
            process_single_xml_file(xml_file, output_dir, class_files)
        else:
            print("Error: No XML documentation files found!")
            return
    
    print(f"\nTotal: Found {len(class_files)} classes with documentation")
    
    # Create index page
    print("Creating index page...")
    create_index_page(class_files, output_dir)
    
    print(f"\nGenerated {len(class_files)} wiki pages in {output_dir}/")
    print("Files created:")
    print(f"- Home.md (index page)")
    for class_name, filename in sorted(class_files.items()):
        print(f"- {filename}")
    
    print(f"\nTo use with GitHub wiki:")
    print(f"1. Copy all .md files from {output_dir}/ to your GitHub wiki repository")
    print(f"2. The Home.md file will serve as your wiki's main page")

if __name__ == "__main__":
    main()