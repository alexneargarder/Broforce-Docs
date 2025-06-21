#!/usr/bin/env python3
"""
Convert .NET XML documentation to GitHub wiki Markdown files with full member declarations.
"""

import xml.etree.ElementTree as ET
import re
import os
from pathlib import Path
from collections import defaultdict, OrderedDict
import html
import sys
sys.path.append(str(Path(__file__).parent))
from csharp_parser import parse_csharp_file

# Global cache for source signatures
SOURCE_SIGNATURES_CACHE = {}

def load_source_signatures(class_name):
    """
    Load member signatures from source code and cache them.
    Returns a dict mapping member names to their full signatures.
    """
    if class_name in SOURCE_SIGNATURES_CACHE:
        return SOURCE_SIGNATURES_CACHE[class_name]
    
    signatures = {}
    members, nested_classes, error = parse_csharp_file(class_name)
    
    if error:
        print(f"Warning: Could not parse source for {class_name}: {error}")
        return signatures
    
    if members:
        for member in members:
            # Extract the full signature, removing only the trailing semicolon and brace content
            signature = member['signature'].strip()
            # Remove trailing semicolon
            if signature.endswith(';'):
                signature = signature[:-1].strip()
            # Remove { get; set; } from properties but keep the declaration
            if '{ get' in signature and 'set; }' in signature:
                signature = re.sub(r'\s*\{\s*get;\s*set;\s*\}', '', signature).strip()
            
            # Build the full declaration with all modifiers
            full_signature = signature
            
            signatures[member['name']] = {
                'type': member['type'],
                'signature': full_signature,
                'access': member['access'],
                'modifiers': member['modifiers']
            }
    
    SOURCE_SIGNATURES_CACHE[class_name] = signatures
    return signatures

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

def extract_member_type(member_name):
    """Extract the member type prefix (M:, P:, F:, T:)."""
    match = re.match(r'^([MPTF]):', member_name)
    return match.group(1) if match else None

def get_method_parameter_types(member_name, param_names):
    """Extract parameter types from method signature and match with parameter names."""
    _, _, param_types = parse_method_signature(member_name)
    
    param_info = OrderedDict()
    param_name_list = list(param_names.keys()) if isinstance(param_names, dict) else param_names
    
    for i, param_type in enumerate(param_types):
        normalized_type = normalize_type_name(param_type)
        if i < len(param_name_list):
            param_name = param_name_list[i]
            param_info[param_name] = normalized_type
        else:
            param_info[f"param{i+1}"] = normalized_type
    
    return param_info

def get_return_type_from_signature(source_signature):
    """Extract return type from a method signature."""
    if not source_signature or not source_signature.get('signature'):
        return None
    
    signature = source_signature['signature']
    
    # Common patterns for return types in C# method signatures
    # Pattern 1: "public/private/protected [static] [virtual/override] ReturnType MethodName("
    # Pattern 2: "public/private/protected [static] [virtual/override] [abstract] ReturnType MethodName("
    
    # Remove access modifiers and other keywords to get to the return type
    parts = signature.split()
    
    # Skip access modifiers
    i = 0
    while i < len(parts) and parts[i] in ['public', 'private', 'protected', 'internal']:
        i += 1
    
    # Skip other modifiers
    while i < len(parts) and parts[i] in ['static', 'virtual', 'override', 'abstract', 'sealed', 'readonly', 'extern', 'async', 'unsafe']:
        i += 1
    
    # The next part should be the return type
    if i < len(parts):
        # Find where the method name starts (before the opening parenthesis)
        remaining = ' '.join(parts[i:])
        
        # Extract everything before the method name
        match = re.match(r'^([\w\[\]<>,.\s]+?)\s+\w+\s*\(', remaining)
        if match:
            return_type = match.group(1).strip()
            return normalize_type_name(return_type)
        
        # Fallback: if there's only one part left before the method name
        if i < len(parts) - 1:
            return normalize_type_name(parts[i])
    
    return None

def parse_method_signature(member_name):
    """Parse a method signature to extract class, method name, and parameters."""
    # Remove the M: prefix
    signature = re.sub(r'^M:', '', member_name)
    
    # Extract parameters if present
    param_match = re.search(r'\((.*)\)$', signature)
    params_str = param_match.group(1) if param_match else ""
    
    # Get the part before parameters
    name_part = re.sub(r'\([^)]*\)$', '', signature)
    parts = name_part.split('.')
    
    if len(parts) >= 2:
        class_name = parts[0]
        method_name = parts[-1]
    else:
        class_name = ""
        method_name = parts[0]
    
    # Parse parameters
    parameters = []
    if params_str:
        # Split by comma but handle nested generics
        param_parts = []
        current_param = ""
        paren_depth = 0
        angle_depth = 0
        
        for char in params_str:
            if char == ',' and paren_depth == 0 and angle_depth == 0:
                param_parts.append(current_param.strip())
                current_param = ""
            else:
                current_param += char
                if char == '(':
                    paren_depth += 1
                elif char == ')':
                    paren_depth -= 1
                elif char == '<':
                    angle_depth += 1
                elif char == '>':
                    angle_depth -= 1
        
        if current_param.strip():
            param_parts.append(current_param.strip())
        
        parameters = param_parts
    
    return class_name, method_name, parameters

def parse_property_signature(member_name):
    """Parse a property signature to extract class and property name."""
    # Remove the P: prefix
    signature = re.sub(r'^P:', '', member_name)
    parts = signature.split('.')
    
    if len(parts) >= 2:
        class_name = parts[0]
        property_name = parts[-1]
    else:
        class_name = ""
        property_name = parts[0]
    
    return class_name, property_name

def parse_field_signature(member_name):
    """Parse a field signature to extract class and field name."""
    # Remove the F: prefix
    signature = re.sub(r'^F:', '', member_name)
    parts = signature.split('.')
    
    if len(parts) >= 2:
        class_name = parts[0]
        field_name = parts[-1]
    else:
        class_name = ""
        field_name = parts[0]
    
    return class_name, field_name

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
        'Void': 'void',
        'System.Object': 'object',
        'Object': 'object',
        'System.Byte': 'byte',
        'Byte': 'byte',
        'System.Char': 'char',
        'Char': 'char',
        'System.Int64': 'long',
        'Int64': 'long',
        'System.Int16': 'short',
        'Int16': 'short',
        'System.UInt32': 'uint',
        'UInt32': 'uint',
        'System.UInt64': 'ulong',
        'UInt64': 'ulong',
        'System.UInt16': 'ushort',
        'UInt16': 'ushort',
        'System.SByte': 'sbyte',
        'SByte': 'sbyte',
        'System.Decimal': 'decimal',
        'Decimal': 'decimal'
    }
    
    # Handle out parameters
    if type_name.endswith('@'):
        base_type = type_name[:-1]
        normalized_base = normalize_type_name(base_type)
        return f"out {normalized_base}"
    
    # Handle ref parameters  
    if type_name.endswith('&'):
        base_type = type_name[:-1]
        normalized_base = normalize_type_name(base_type)
        return f"ref {normalized_base}"
    
    # Handle arrays
    if type_name.endswith('[]'):
        base_type = type_name[:-2]
        normalized_base = normalize_type_name(base_type)
        return f"{normalized_base}[]"
    
    # Handle generics
    if '`' in type_name:
        # Simplify generic notation (e.g., List`1 -> List<T>)
        type_name = re.sub(r'`\d+', '', type_name)
    
    # Remove namespace prefixes for non-System types
    if '.' in type_name and not type_name.startswith('System.'):
        type_name = type_name.split('.')[-1]
    
    return type_map.get(type_name, type_name)

def format_method_declaration(method_name, param_descriptions, returns_info=None, source_signature=None):
    """Format a complete method declaration."""
    _, simple_name, param_types = parse_method_signature(method_name)
    
    # If we have the source signature, use it instead of inferring
    if source_signature and source_signature.get('signature'):
        return source_signature['signature']
    
    # Fallback to inference if no source signature available
    # Match parameter types with names from descriptions
    params_with_names = []
    param_names = list(param_descriptions.keys()) if param_descriptions else []
    
    for i, param_type in enumerate(param_types):
        normalized_type = normalize_type_name(param_type)
        if i < len(param_names):
            param_name = param_names[i]
            params_with_names.append(f"{normalized_type} {param_name}")
        else:
            params_with_names.append(f"{normalized_type} param{i+1}")
    
    # For now, we'll use void as default return type since it's not in XML
    # In practice, most Broforce methods that don't specify returns are void
    return_type = "void"
    
    # Special cases where we can infer return type
    if simple_name.startswith("Get") or simple_name.startswith("Is") or simple_name.startswith("Has"):
        if returns_info and "bool" in returns_info.lower():
            return_type = "bool"
        elif returns_info:
            # Try to extract type from returns description
            # This is a heuristic and may not always be accurate
            if "float" in returns_info.lower():
                return_type = "float"
            elif "int" in returns_info.lower():
                return_type = "int"
            elif "string" in returns_info.lower():
                return_type = "string"
            elif any(word in returns_info.lower() for word in ["object", "instance", "reference"]):
                return_type = "object"
    
    params_str = ", ".join(params_with_names)
    return f"{return_type} {simple_name}({params_str})"

def format_property_declaration(property_name, value_info=None, source_signature=None):
    """Format a complete property declaration."""
    _, simple_name = parse_property_signature(property_name)
    
    # If we have the source signature, use it
    if source_signature and source_signature.get('signature'):
        sig = source_signature['signature']
        # Add { get; set; } if not present
        if '{' not in sig:
            sig += " { get; set; }"
        return sig
    
    # Fallback to inference if no source signature available
    # Try to infer type from value description or property name
    prop_type = "object"  # Default type
    
    if value_info:
        value_lower = value_info.lower()
        if "bool" in value_lower or "true" in value_lower or "false" in value_lower:
            prop_type = "bool"
        elif "float" in value_lower or "decimal" in value_lower or "number" in value_lower:
            prop_type = "float"
        elif "int" in value_lower or "count" in value_lower or "index" in value_lower:
            prop_type = "int"
        elif "string" in value_lower or "text" in value_lower or "name" in value_lower:
            prop_type = "string"
    
    # Common property name patterns
    if simple_name.startswith("Is") or simple_name.startswith("Has") or simple_name.startswith("Can"):
        prop_type = "bool"
    elif "Count" in simple_name or "Index" in simple_name or "Size" in simple_name:
        prop_type = "int"
    elif "Name" in simple_name or "Text" in simple_name:
        prop_type = "string"
    
    return f"{prop_type} {simple_name} {{ get; set; }}"

def format_field_declaration(field_name, source_signature=None):
    """Format a complete field declaration."""
    _, simple_name = parse_field_signature(field_name)
    
    # If we have the source signature, use it
    if source_signature and source_signature.get('signature'):
        return source_signature['signature']
    
    # Fallback to inference if no source signature available
    # Try to infer type from field name patterns
    field_type = "object"  # Default type
    
    # Common field name patterns
    if simple_name.startswith("is") or simple_name.startswith("has") or simple_name.startswith("can"):
        field_type = "bool"
    elif any(suffix in simple_name.lower() for suffix in ["count", "index", "size", "length"]):
        field_type = "int"
    elif any(suffix in simple_name.lower() for suffix in ["time", "delay", "duration", "speed", "distance"]):
        field_type = "float"
    elif any(suffix in simple_name.lower() for suffix in ["name", "text", "message"]):
        field_type = "string"
    
    return f"{field_type} {simple_name}"

def format_member_name(member_name):
    """Extract readable name from XML member name."""
    member_type = extract_member_type(member_name)
    
    if member_type == 'M':
        class_name, method_name, _ = parse_method_signature(member_name)
        return class_name, method_name
    elif member_type == 'P':
        return parse_property_signature(member_name)
    elif member_type == 'F':
        return parse_field_signature(member_name)
    else:
        # Fallback to original logic
        name = re.sub(r'^[MPTF]:', '', member_name)
        name_no_params = re.sub(r'\([^)]*\)', '', name)
        parts = name_no_params.split('.')
        
        if len(parts) > 1:
            return parts[0], parts[-1]
        return name, name

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
    section_groups = OrderedDict()
    
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
    
    # Load source signatures for this class
    source_signatures = load_source_signatures(class_name)
    
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
                    
                    # Create member heading with anchor and declaration
                    lines.append(f'<a id="{member_anchor}"></a>')
                    
                    # Get source signature if available
                    source_sig = source_signatures.get(member_simple)
                    
                    # Format the declaration based on member type
                    if category == 'Methods':
                        declaration = format_method_declaration(member['name'], member['params'], member['returns'], source_sig)
                        lines.append(f"#### `{declaration}`")
                    elif category == 'Properties':
                        declaration = format_property_declaration(member['name'], member['value'], source_sig)
                        lines.append(f"#### `{declaration}`")
                    elif category == 'Fields':
                        declaration = format_field_declaration(member['name'], source_sig)
                        lines.append(f"#### `{declaration}`")
                    else:
                        lines.append(f"#### {member_simple}")
                    
                    lines.append("")
                    
                    # Add summary
                    if member['summary']:
                        lines.append(member['summary'])
                        lines.append("")
                    
                    # Add parameters for methods (with better formatting)
                    if category == 'Methods' and member['params']:
                        param_types = get_method_parameter_types(member['name'], member['params'])
                        lines.append("**Parameters:**")
                        for param_name, param_desc in member['params'].items():
                            param_type = param_types.get(param_name, 'object')
                            lines.append(f"- **{param_type} {param_name}**: {param_desc}")
                        lines.append("")
                    
                    # Add return value
                    if member['returns']:
                        lines.append("**Returns:**")
                        # Extract return type from source signature if available
                        return_type = None
                        if source_sig:
                            return_type = get_return_type_from_signature(source_sig)
                        
                        if return_type:
                            lines.append(f"- `{return_type}`: {member['returns']}")
                        else:
                            lines.append(f"- {member['returns']}")
                        lines.append("")
                    
                    # Add value for properties
                    if category == 'Properties' and member['value']:
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
                
                # Get source signature if available
                source_sig = source_signatures.get(member_simple)
                
                # Format the declaration based on member type
                if category == 'Methods':
                    declaration = format_method_declaration(member['name'], member['params'], member['returns'], source_sig)
                    lines.append(f"### `{declaration}`")
                elif category == 'Properties':
                    declaration = format_property_declaration(member['name'], member['value'], source_sig)
                    lines.append(f"### `{declaration}`")
                elif category == 'Fields':
                    declaration = format_field_declaration(member['name'], source_sig)
                    lines.append(f"### `{declaration}`")
                else:
                    lines.append(f"### {member_simple}")
                
                lines.append("")
                
                # Add summary
                if member['summary']:
                    lines.append(member['summary'])
                    lines.append("")
                
                # Add parameters for methods
                if category == 'Methods' and member['params']:
                    param_types = get_method_parameter_types(member['name'], member['params'])
                    lines.append("**Parameters:**")
                    for param_name, param_desc in member['params'].items():
                        param_type = param_types.get(param_name, 'object')
                        lines.append(f"- **{param_type} {param_name}**: {param_desc}")
                    lines.append("")
                
                # Add return value
                if member['returns']:
                    lines.append("**Returns:**")
                    # Extract return type from source signature if available
                    return_type = None
                    if source_sig:
                        return_type = get_return_type_from_signature(source_sig)
                    
                    if return_type:
                        lines.append(f"- `{return_type}`: {member['returns']}")
                    else:
                        lines.append(f"- {member['returns']}")
                    lines.append("")
                
                # Add value for properties
                if category == 'Properties' and member['value']:
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
        params = OrderedDict()
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