#!/usr/bin/env python3
"""
Shared XML utilities for Broforce documentation scripts.
Provides common functionality for parsing, formatting, and manipulating XML documentation files.
"""

import re
import html
import os
import sys
from typing import List, Dict, Tuple, Optional, Union
from functools import wraps


def is_test_mode():
    """Check if running in test mode"""
    return os.environ.get('BROFORCE_TEST_MODE') == '1'


# Global list to capture output during tests
_test_output_buffer = []


def get_test_output():
    """Get captured test output and clear buffer"""
    global _test_output_buffer
    output = '\n'.join(_test_output_buffer)
    _test_output_buffer = []
    return output


def clear_test_output():
    """Clear the test output buffer"""
    global _test_output_buffer
    _test_output_buffer = []


def quiet_print(*args, **kwargs):
    """Print normally or capture to buffer in test mode"""
    if is_test_mode():
        # In test mode, check if we should output to stderr for subprocess tests
        if os.environ.get('BROFORCE_TEST_CAPTURE_OUTPUT') == '1':
            # Output to stderr so tests can capture it
            print(*args, file=sys.stderr, **kwargs)
        else:
            # Capture output to buffer for in-process tests
            import io
            output = io.StringIO()
            print(*args, file=output, **kwargs)
            _test_output_buffer.append(output.getvalue().rstrip('\n'))
    else:
        print(*args, **kwargs)

# Alias for convenience
qprint = quiet_print


def quiet_decorator(func):
    """Decorator to capture all print output from a function during tests"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if is_test_mode():
            # Capture stdout to buffer
            import io
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()
            try:
                sys.stdout = stdout_buffer
                sys.stderr = stderr_buffer
                result = func(*args, **kwargs)
                # Add captured output to test buffer
                stdout_content = stdout_buffer.getvalue()
                if stdout_content:
                    _test_output_buffer.extend(stdout_content.rstrip('\n').split('\n'))
                return result
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
        else:
            return func(*args, **kwargs)
    return wrapper


class XMLPatterns:
    """Common regex patterns used across XML documentation scripts"""
    
    # Comment patterns
    COMMENT = re.compile(r'<!--\s*(.*?)\s*-->')
    SECTION_COMMENT = re.compile(r'<!--\s*(.+?)\s+(Methods|Properties|Fields)\s*-->')
    VALID_SECTION = re.compile(r'^<!--\s*.*\s+(Methods|Properties|Fields)\s*-->$')
    
    # Member patterns
    MEMBER_START = re.compile(r'<member\s+name="([^"]*)"')
    MEMBER_NAME = re.compile(r'name="([^"]*)"')
    MEMBER_TYPE_PREFIX = re.compile(r'name="([MFP]):[^"]+"')
    
    # XML structure patterns
    DOC = re.compile(r'<doc\s*>(.*?)</doc>', re.DOTALL)
    ASSEMBLY = re.compile(r'<assembly\s*>(.*?)</assembly>', re.DOTALL)
    MEMBERS = re.compile(r'<members\s*>(.*?)</members>', re.DOTALL)
    
    # Member content patterns
    SUMMARY = re.compile(r'<summary\s*>(.*?)</summary>', re.DOTALL)
    PARAM = re.compile(r'<param\s+name="([^"]*)">(.*?)</param>', re.DOTALL)
    RETURNS = re.compile(r'<returns>(.*?)</returns>', re.DOTALL)
    REMARKS = re.compile(r'<remarks>(.*?)</remarks>', re.DOTALL)
    
    # Section parsing pattern from tracking files
    TRACKING_SECTION = re.compile(r'^\d+\.\s+\*\*([^*]+)\*\*\s+-\s+[^\n]+', re.MULTILINE)


class SectionManager:
    """Manages XML documentation sections"""
    
    @staticmethod
    def normalize_section_name(section_name: str) -> str:
        """
        Normalize section names to handle & vs &amp; encoding differences and spacing variations.
        
        Args:
            section_name: The section name to normalize
            
        Returns:
            Normalized section name as properly formatted XML comment
        """
        # First strip any surrounding whitespace to avoid double-wrapping
        section_name = section_name.strip()
        
        # Use regex to flexibly match XML comments with any internal spacing
        # Matches: <!--text-->, <!-- text -->, <!--  text  -->, etc.
        comment_pattern = r'^<!--\s*(.*?)\s*-->$'
        match = re.match(comment_pattern, section_name)
        
        if match:
            # Extract the content from the comment
            content = match.group(1)
        else:
            # Not a comment, use as-is
            content = section_name
        
        # Decode any HTML entities to get consistent representation
        content = html.unescape(content)
        
        # Return as properly formatted XML comment with plain & and standard spacing
        return f"<!-- {content} -->"
    
    @staticmethod
    def section_names_match(name1: str, name2: str) -> bool:
        """
        Check if two section names match, accounting for & vs &amp; encoding.
        
        Args:
            name1: First section name
            name2: Second section name
            
        Returns:
            True if the names match when normalized
        """
        return SectionManager.normalize_section_name(name1) == SectionManager.normalize_section_name(name2)
    
    @staticmethod
    def extract_sections_from_xml(xml_file: str) -> List[str]:
        """
        Extract unique section names from XML file by stripping member type suffixes.
        
        Args:
            xml_file: Path to XML file
            
        Returns:
            List of unique section names
        """
        sections = []
        seen_sections = set()
        
        with open(xml_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern to match section comments with member type suffixes
        for match in XMLPatterns.SECTION_COMMENT.finditer(content):
            section_name = match.group(1).strip()
            if section_name not in seen_sections:
                sections.append(section_name)
                seen_sections.add(section_name)
        
        return sections
    
    @staticmethod
    def get_base_section_name(section_comment: str) -> str:
        """
        Extract base section name from a section comment, removing member type suffix.
        
        Args:
            section_comment: Full section comment like "<!-- Unity Lifecycle Methods -->"
            
        Returns:
            Base section name like "Unity Lifecycle"
        """
        match = XMLPatterns.COMMENT.search(section_comment)
        if match:
            content = match.group(1).strip()
            # Remove member type suffix
            base_name = re.sub(r'\s+(Methods|Properties|Fields)$', '', content)
            return base_name.strip()
        return section_comment


class MemberParser:
    """Parses and extracts information from member elements"""
    
    @staticmethod
    def get_member_name(member_lines: Union[List[str], Dict]) -> str:
        """
        Extract member name from XML member element for sorting.
        
        Args:
            member_lines: Either a list of lines or a dict with 'lines' key
            
        Returns:
            Member name for sorting
        """
        # Handle both list and dict inputs
        if isinstance(member_lines, dict):
            lines = member_lines.get('lines', [])
        else:
            lines = member_lines
            
        # Join all lines to handle multi-line member elements
        full_text = ' '.join(lines)
        # Match pattern like name="M:TestVanDammeAnim.MethodName" or name="F:TestVanDammeAnim.FieldName"
        match = re.search(r'name="[MFP]:[^.]+\.([^"(]+)', full_text)
        return match.group(1) if match else lines[0] if lines else ""
    
    @staticmethod
    def get_member_type(member_lines: Union[List[str], str]) -> str:
        """
        Determine member type from XML member element.
        
        Args:
            member_lines: Either a list of lines or full text
            
        Returns:
            'method', 'property', 'field', or 'unknown'
        """
        if isinstance(member_lines, list):
            full_text = ' '.join(member_lines)
        else:
            full_text = member_lines
            
        if 'name="M:' in full_text:
            return 'method'
        elif 'name="P:' in full_text:
            return 'property'
        elif 'name="F:' in full_text:
            return 'field'
        return 'unknown'
    
    @staticmethod
    def parse_member_from_lines(member_lines: List[str], class_name: str, nested_classes: Optional[set] = None) -> Optional[Dict]:
        """
        Parse member information from XML lines.
        
        Args:
            member_lines: List of XML lines for a member element
            class_name: Expected class name
            nested_classes: Optional set of nested class names
            
        Returns:
            Dictionary with parsed member info including:
            - name: Member name
            - type: 'method', 'property', or 'field'
            - full_name: Full member name from XML
            - xml_lines: Original XML lines
            Or None if parsing fails
        """
        if not member_lines:
            return None
            
        # Join lines and extract name attribute
        member_text = '\n'.join(member_lines)
        name_match = XMLPatterns.MEMBER_NAME.search(member_text)
        if not name_match:
            return None
            
        name_attr = name_match.group(1)
        parsed = MemberParser.parse_member_name_from_xml(name_attr, class_name, nested_classes)
        
        if parsed:
            # Add the full name attribute and original lines for convenience
            parsed['full_name'] = name_attr
            parsed['xml_lines'] = member_lines
            
            # Extract the class name from the name attribute
            # Format is like "M:ClassName.MemberName" or "M:ClassName.NestedClass.MemberName"
            if ':' in name_attr and '.' in name_attr:
                name_part = name_attr.split(':', 1)[1]  # Remove prefix
                class_parts = name_part.split('.')
                if class_parts:
                    parsed['class_name'] = class_parts[0]
            
        return parsed
    
    @staticmethod
    def parse_member_name_from_xml(name_attr: str, class_name: str, nested_classes: Optional[set] = None) -> Optional[Dict]:
        """
        Parse member information from XML name attribute.
        
        Args:
            name_attr: The name attribute value (e.g., "M:ClassName.MethodName(params)")
            class_name: The main class name
            nested_classes: Optional set of nested class names
            
        Returns:
            dict with 'type', 'name', and 'is_nested' keys, or None if invalid
        """
        if not name_attr or len(name_attr) < 3:
            return None
            
        # Extract type prefix and name
        member_type_prefix = name_attr[:2]
        name_without_prefix = name_attr[2:]
        
        # Split by dots to get the parts
        parts = name_without_prefix.split('.')
        
        # Check if this is a nested class member
        is_nested = False
        member_name_index = 1  # Default to second part
        
        if nested_classes and len(parts) >= 3:
            # Check if second part is a nested class name
            if parts[1] in nested_classes:
                is_nested = True
                member_name_index = 2  # Member name is third part for nested classes
        
        member_info = {'is_nested': is_nested}
        
        if member_type_prefix == 'M:':
            member_info['type'] = 'method'
            if len(parts) > member_name_index:
                method_part = parts[member_name_index]
                # Remove parameters (everything after first '(')
                member_info['name'] = method_part.split('(')[0]
        elif member_type_prefix == 'P:':
            member_info['type'] = 'property'
            if len(parts) > member_name_index:
                member_info['name'] = parts[member_name_index]
        elif member_type_prefix == 'F:':
            member_info['type'] = 'field'
            if len(parts) > member_name_index:
                member_info['name'] = parts[member_name_index]
        else:
            return None
            
        return member_info
    
    @staticmethod
    def extract_member_signature(name_attr: str) -> Tuple[str, str, str]:
        """
        Extract type, class, and signature from member name attribute.
        
        Args:
            name_attr: Full member name like "M:ClassName.Method(params)"
            
        Returns:
            Tuple of (type_prefix, class_name, member_signature)
        """
        if not name_attr or len(name_attr) < 3:
            return ('', '', '')
            
        type_prefix = name_attr[0]  # M, P, or F
        name_without_prefix = name_attr[2:]  # Remove "M:" etc
        
        parts = name_without_prefix.split('.', 1)
        if len(parts) == 2:
            return (type_prefix, parts[0], parts[1])
        return (type_prefix, parts[0] if parts else '', '')


class XMLFormatter:
    """Handles XML formatting and content escaping"""
    
    @staticmethod
    def escape_xml_content(line: str) -> str:
        """
        Properly escape XML content while preserving comments and XML structure.
        Comments can contain plain & but element content must use &amp;
        
        Args:
            line: Line to escape
            
        Returns:
            Properly escaped line
        """
        stripped = line.strip()
        
        # Don't escape comments
        if stripped.startswith('<!--') and stripped.endswith('-->'):
            return line
        
        # Don't escape pure XML tags (no content on the line)
        if re.match(r'^\s*<[^>]+>\s*$', line):
            return line
        
        # Check for inline content between tags on the same line
        inline_pattern = r'^(\s*<(\w+)(?:\s+[^>]*)?>)(.+?)(</\2>\s*)$'
        match = re.match(inline_pattern, line)
        
        if match:
            # Found inline content between tags
            start = match.group(1)
            content = match.group(3)
            end = match.group(4)
            
            # Escape special XML characters in content only
            # Only escape & that aren't already part of an entity
            content = re.sub(r'&(?!(?:[a-zA-Z]+|#[0-9]+|#x[0-9a-fA-F]+);)', '&amp;', content)
            content = content.replace('<', '&lt;')
            content = content.replace('>', '&gt;')
            
            return start + content + end
        
        # For lines that are pure content (no tags), escape everything
        if not '<' in line and not '>' in line:
            # Only escape & that aren't already part of an entity
            escaped_line = re.sub(r'&(?!(?:[a-zA-Z]+|#[0-9]+|#x[0-9a-fA-F]+);)', '&amp;', line)
            return escaped_line
        
        # For mixed content, be conservative and only escape unescaped ampersands
        escaped_line = re.sub(r'&(?!(?:[a-zA-Z]+|#[0-9]+|#x[0-9a-fA-F]+);)', '&amp;', line)
        
        # Check for content that appears to be text with < or > that should be escaped
        if not (re.search(r'<[^/>]+>', line) and re.search(r'</[^>]+>', line)):
            # Check if < or > appear in what looks like text content
            if not re.search(r'</?[a-zA-Z][^>]*>', line):
                escaped_line = escaped_line.replace('<', '&lt;')
                escaped_line = escaped_line.replace('>', '&gt;')
        
        return escaped_line
    
    @staticmethod
    def format_line(line: str, indent_level: int, target_length: int = 100) -> List[str]:
        """
        Format a line with proper indentation and wrapping.
        
        Args:
            line: Line to format
            indent_level: Number of indent levels (4 spaces each)
            target_length: Target line length for wrapping
            
        Returns:
            List of formatted lines
        """
        indent = '    ' * indent_level
        
        # Don't wrap comments or short lines
        if len(line) <= target_length or '<!--' in line:
            return [indent + line.strip()]
        
        # For long lines, try to wrap at appropriate points
        words = line.strip().split()
        lines = []
        current_line = indent
        
        for word in words:
            if len(current_line) + len(word) + 1 <= target_length:
                if current_line.strip():
                    current_line += ' '
                current_line += word
            else:
                if current_line.strip():
                    lines.append(current_line)
                current_line = indent + '    ' + word  # Extra indent for continuation
        
        if current_line.strip():
            lines.append(current_line)
            
        return lines if lines else [indent + line.strip()]


class XMLFileReader:
    """Reads and parses XML documentation files"""
    
    @staticmethod
    def read_xml_file(xml_path: str) -> Dict:
        """
        Read and parse XML file into structured sections and members.
        
        Args:
            xml_path: Path to XML file
            
        Returns:
            dict with 'header_lines', 'footer_lines', and 'sections'
            Each section now includes a 'subsections' dict organizing members by type
        """
        with open(xml_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        
        # Find where members section starts and ends
        members_start = -1
        members_end = -1
        
        for i, line in enumerate(lines):
            if '<members>' in line:
                members_start = i
            elif '</members>' in line:
                members_end = i
                break
        
        if members_start == -1 or members_end == -1:
            raise ValueError("Could not find members section")
        
        # Extract header and footer
        header_lines = lines[:members_start + 1]
        footer_lines = lines[members_end:]
        
        # Parse members section - Phase 1: Collect all data
        sections = {}
        current_section = None
        current_subsection_type = None
        
        i = members_start + 1
        while i < members_end:
            line = lines[i]
            
            # Check for section comment
            if '<!--' in line and '-->' in line:
                match = re.search(r'<!--\s*(.+?)\s*-->', line)
                if match:
                    comment_text = match.group(1).strip()
                    
                    # Check if this is a subsection comment (ends with Methods/Properties/Fields)
                    subsection_match = re.match(r'^(.+?)\s+(Methods|Properties|Fields)$', comment_text)
                    
                    if subsection_match:
                        # This is a subsection comment
                        section_name = subsection_match.group(1).strip()
                        subsection_type = subsection_match.group(2)
                        
                        if section_name not in sections:
                            sections[section_name] = {
                                'comments': [],
                                'subsections': {}
                            }
                        
                        sections[section_name]['comments'].append(line)
                        current_section = section_name
                        current_subsection_type = subsection_type
                        
                        # Initialize subsection
                        if subsection_type not in sections[section_name]['subsections']:
                            sections[section_name]['subsections'][subsection_type] = {
                                'comment': line.rstrip('\n'),  # Keep indentation, just remove newline
                                'members': []
                            }
                    else:
                        # This is a regular section comment (no type suffix)
                        section_name = comment_text
                        
                        if section_name not in sections:
                            sections[section_name] = {
                                'comments': [],
                                'subsections': {}
                            }
                        
                        sections[section_name]['comments'].append(line)
                        current_section = section_name
                        current_subsection_type = None
            
            # Check for member element
            elif '<member' in line:
                member_lines = [line]
                j = i + 1
                
                # Collect all lines for this member
                while j < members_end and '</member>' not in lines[j - 1]:
                    if j < len(lines):
                        member_lines.append(lines[j])
                    j += 1
                
                if current_section:
                    # Only add to subsection - members must be in subsections
                    if current_subsection_type and current_subsection_type in sections[current_section]['subsections']:
                        sections[current_section]['subsections'][current_subsection_type]['members'].append(member_lines)
                    else:
                        # Members outside of subsections are invalid
                        raise ValueError(
                            f"Invalid XML format: Found member outside of a subsection. All members must be within "
                            f"Methods/Properties/Fields subsections. Member found after line {i + members_start + 1}"
                        )
                
                i = j - 1
            
            i += 1
        
        return {
            'header_lines': header_lines,
            'footer_lines': footer_lines,
            'sections': sections
        }
    
    @staticmethod
    def extract_members_from_file(xml_path: str) -> List[str]:
        """
        Extract all member names from an XML file.
        
        Args:
            xml_path: Path to XML file
            
        Returns:
            List of member names
        """
        members = []
        
        with open(xml_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        for match in XMLPatterns.MEMBER_NAME.finditer(content):
            members.append(match.group(1))
            
        return members


class XMLFileWriter:
    """Writes XML documentation files"""
    
    @staticmethod
    def _apply_indentation(line: str, indent_level: int) -> str:
        """
        Apply proper indentation to a line based on indent level.
        
        Args:
            line: The line to indent (indentation will be stripped first)
            indent_level: Number of indent levels (4 spaces each)
            
        Returns:
            Line with proper indentation
        """
        # Strip existing indentation
        stripped = line.lstrip()
        
        # Apply new indentation
        indent = '    ' * indent_level
        return indent + stripped
    
    @staticmethod
    def _get_indent_level_for_line(line: str) -> int:
        """
        Determine the appropriate indent level for a line based on its content.
        
        Args:
            line: The XML line
            
        Returns:
            Indent level (0-based)
        """
        stripped = line.strip()
        
        # XML declaration and root elements have no indentation
        if stripped.startswith('<?xml') or stripped == '<doc>' or stripped == '</doc>':
            return 0
        
        # Assembly block
        if stripped in ['<assembly>', '</assembly>']:
            return 1
        if stripped.startswith('<name>') and 'Assembly-CSharp' in stripped:
            return 2
            
        # Members block
        if stripped in ['<members>', '</members>']:
            return 1
            
        # Comments and member elements within members
        if stripped.startswith('<!--') or stripped.startswith('<member '):
            return 2
            
        # Closing member tag
        if stripped == '</member>':
            return 2
            
        # Content within member elements (summary, param, returns, etc.)
        if any(tag in stripped for tag in ['<summary', '</summary', '<param', '</param', 
                                           '<returns', '</returns', '<remarks', '</remarks']):
            return 3
            
        # Text content within documentation tags
        # This is a bit tricky - we need to maintain relative indentation
        # Default to 4 levels for content
        return 4
    
    @staticmethod
    def write_xml_file(xml_path: str, data: Dict, format_content: bool = True):
        """
        Write structured data back to XML file with automatic indentation and formatting.
        
        Args:
            xml_path: Path to output file
            data: Dict with 'header_lines', 'footer_lines', and 'sections'
                  Each section may have 'subsections' dict organizing members by type
            format_content: If True (default), apply text wrapping and whitespace normalization
        """
        lines = []
        
        # Process header with proper indentation
        for line in data['header_lines']:
            indent_level = XMLFileWriter._get_indent_level_for_line(line)
            lines.append(XMLFileWriter._apply_indentation(line, indent_level))
        
        # Process sections with formatting
        for section_name, section_data in data['sections'].items():
            if not section_data.get('subsections'):
                # Sections without subsections are invalid
                raise ValueError(
                    f"Invalid XML format: Section '{section_name}' has no subsections. "
                    f"All sections must have Methods/Properties/Fields subsections."
                )
            
            # Handle subsections in order: Methods, Properties, Fields
            subsec_order = {'Methods': 0, 'Properties': 1, 'Fields': 2}
            sorted_subsections = sorted(
                section_data['subsections'].items(),
                key=lambda x: subsec_order.get(x[0], 3)
            )
            
            for subsec_type, subsec_data in sorted_subsections:
                # Add subsection comment with proper indentation
                comment = subsec_data['comment']
                lines.append(XMLFileWriter._apply_indentation(comment, 2))
                
                # Process and format members
                for member_lines in subsec_data['members']:
                    formatted_lines = XMLFileWriter._format_member_lines(member_lines, format_content)
                    lines.extend(formatted_lines)
        
        # Process footer
        for line in data['footer_lines']:
            indent_level = XMLFileWriter._get_indent_level_for_line(line)
            lines.append(XMLFileWriter._apply_indentation(line, indent_level))
        
        # Write file
        with open(xml_path, 'w', encoding='utf-8', newline='\r\n') as f:
            f.write('\n'.join(lines))
    
    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        """
        Normalize whitespace in text content.
        Converts multiple spaces, tabs, and newlines to single spaces.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text
        """
        return ' '.join(text.split())
    
    @staticmethod
    def _wrap_text(text: str, indent_length: int, target_line_length: int = 100) -> List[str]:
        """
        Wrap text to fit within target line length.
        
        Args:
            text: Text to wrap
            indent_length: Length of indentation (in characters)
            target_line_length: Target total line length including indentation
            
        Returns:
            List of wrapped lines (without indentation applied)
        """
        if not text:
            return []
            
        words = text.split()
        lines = []
        current_line = []
        
        # Calculate available width for text
        available_width = target_line_length - indent_length
        
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
    
    @staticmethod
    def _format_member_lines(member_lines: List[str], format_content: bool) -> List[str]:
        """
        Format member element lines with proper indentation and content formatting.
        
        Args:
            member_lines: List of lines for a member element
            format_content: If True, apply text wrapping and normalization
            
        Returns:
            List of formatted lines
        """
        if not format_content:
            # Just apply indentation without content formatting
            formatted = []
            inside_member = False
            inside_doc_tag = False
            
            for line in member_lines:
                stripped = line.strip()
                
                if stripped.startswith('<member '):
                    inside_member = True
                    formatted.append(XMLFileWriter._apply_indentation(line, 2))
                elif stripped == '</member>':
                    inside_member = False
                    formatted.append(XMLFileWriter._apply_indentation(line, 2))
                elif inside_member:
                    if any(tag in stripped for tag in ['<summary', '<param', '<returns', '<remarks']):
                        inside_doc_tag = True
                        formatted.append(XMLFileWriter._apply_indentation(line, 3))
                    elif any(tag in stripped for tag in ['</summary>', '</param>', '</returns>', '</remarks>']):
                        inside_doc_tag = False
                        formatted.append(XMLFileWriter._apply_indentation(line, 3))
                    elif inside_doc_tag and stripped:
                        formatted.append(XMLFileWriter._apply_indentation(line, 4))
                    else:
                        formatted.append(XMLFileWriter._apply_indentation(line, 3))
                else:
                    formatted.append(line)
                    
            return formatted
        
        # Parse member to extract components
        member_text = '\n'.join(member_lines)
        name_match = XMLPatterns.MEMBER_NAME.search(member_text)
        if not name_match:
            return member_lines  # Can't parse, return as-is
            
        member_name = name_match.group(1)
        formatted = []
        
        # Member opening tag
        formatted.append(f'        <member name="{member_name}">')
        
        # Extract and format each component in order
        # 1. Summary
        summary_match = XMLPatterns.SUMMARY.search(member_text)
        if summary_match:
            summary_text = XMLFileWriter._normalize_whitespace(summary_match.group(1))
            if summary_text:  # Only output non-empty summaries
                formatted.append('            <summary>')
                wrapped = XMLFileWriter._wrap_text(summary_text, 16)  # 4 levels * 4 spaces
                for line in wrapped:
                    formatted.append(f'                {line}')
                formatted.append('            </summary>')
        
        # 2. Parameters (one line each)
        params = XMLPatterns.PARAM.findall(member_text)
        for param_name, param_desc in params:
            param_desc = XMLFileWriter._normalize_whitespace(param_desc)
            formatted.append(f'            <param name="{param_name}">{param_desc}</param>')
        
        # 3. Returns (one line)
        returns_match = XMLPatterns.RETURNS.search(member_text)
        if returns_match:
            returns_text = XMLFileWriter._normalize_whitespace(returns_match.group(1))
            if returns_text:
                formatted.append(f'            <returns>{returns_text}</returns>')
        
        # 4. Remarks (multi-line like summary)
        remarks_match = XMLPatterns.REMARKS.search(member_text)
        if remarks_match:
            remarks_text = XMLFileWriter._normalize_whitespace(remarks_match.group(1))
            if remarks_text:  # Only output non-empty remarks
                formatted.append('            <remarks>')
                wrapped = XMLFileWriter._wrap_text(remarks_text, 16)  # 4 levels * 4 spaces
                for line in wrapped:
                    formatted.append(f'                {line}')
                formatted.append('            </remarks>')
        
        # Member closing tag
        formatted.append('        </member>')
        
        return formatted
    
    @staticmethod
    def format_member_element(member_data: Dict, indent_level: int = 2) -> List[str]:
        """
        Format a member element with proper indentation.
        
        Args:
            member_data: Dict with 'name', 'summary', 'params', 'returns', etc.
            indent_level: Base indentation level
            
        Returns:
            List of formatted lines
        """
        indent = '    ' * indent_level
        lines = [f'{indent}<member name="{member_data["name"]}">']
        
        if 'summary' in member_data:
            lines.append(f'{indent}    <summary>')
            summary_lines = member_data['summary'].strip().split('\n')
            for line in summary_lines:
                lines.append(f'{indent}        {line.strip()}')
            lines.append(f'{indent}    </summary>')
        
        if 'params' in member_data:
            for param_name, param_desc in member_data['params'].items():
                lines.append(f'{indent}    <param name="{param_name}">{param_desc}</param>')
        
        if 'returns' in member_data:
            lines.append(f'{indent}    <returns>{member_data["returns"]}</returns>')
        
        if 'remarks' in member_data:
            lines.append(f'{indent}    <remarks>')
            remarks_lines = member_data['remarks'].strip().split('\n')
            for line in remarks_lines:
                lines.append(f'{indent}        {line.strip()}')
            lines.append(f'{indent}    </remarks>')
        
        lines.append(f'{indent}</member>')
        return lines


class XMLSectionExtractor:
    """Utilities for extracting specific subsections from XML data"""
    
    @staticmethod
    def extract_subsections(xml_data: Dict, subsection_specs: List[str]) -> Dict:
        """
        Extract specific subsections like "Animation & Sprite Systems Methods".
        
        Args:
            xml_data: Data from XMLFileReader.read_xml_file()
            subsection_specs: List like ["Animation & Sprite Systems Methods", ...]
            
        Returns:
            New xml_data dict with only requested subsections
        """
        # Create a new structure with same format but filtered content
        extracted_data = {
            'header_lines': xml_data['header_lines'],
            'footer_lines': xml_data['footer_lines'],
            'sections': {}
        }
        
        # Parse subsection specs to determine what to extract
        sections_to_extract = {}  # section_name -> set of subsection types
        
        for spec in subsection_specs:
            # Try to parse as "Section Name Type" where Type is Methods/Properties/Fields
            parts = spec.rsplit(' ', 1)
            if len(parts) == 2 and parts[1] in ['Methods', 'Properties', 'Fields']:
                section_name = parts[0]
                subsection_type = parts[1]
                
                if section_name not in sections_to_extract:
                    sections_to_extract[section_name] = set()
                sections_to_extract[section_name].add(subsection_type)
            else:
                # Not a subsection spec, might be a full section name
                sections_to_extract[spec] = None  # None means extract all subsections
        
        # Extract requested sections/subsections
        for section_name, subsection_types in sections_to_extract.items():
            if section_name in xml_data['sections']:
                source_section = xml_data['sections'][section_name]
                
                if subsection_types is None:
                    # Extract the entire section
                    extracted_data['sections'][section_name] = source_section
                else:
                    # Extract only specific subsections
                    new_section = {
                        'comments': [],
                        'subsections': {}
                    }
                    
                    # Add comments for requested subsections
                    for subsec_type in subsection_types:
                        if subsec_type in source_section.get('subsections', {}):
                            subsec_data = source_section['subsections'][subsec_type]
                            new_section['comments'].append(subsec_data['comment'])
                            new_section['subsections'][subsec_type] = subsec_data
                            
                    
                    if new_section['subsections']:  # Only add if we found subsections
                        extracted_data['sections'][section_name] = new_section
        
        return extracted_data
    
    @staticmethod
    def extract_sections(xml_data: Dict, section_names: List[str]) -> Dict:
        """
        Extract complete sections by name (without subsection filtering).
        
        Args:
            xml_data: Data from XMLFileReader.read_xml_file()
            section_names: List of section names to extract
            
        Returns:
            New xml_data dict with only requested sections
        """
        extracted_data = {
            'header_lines': xml_data['header_lines'],
            'footer_lines': xml_data['footer_lines'],
            'sections': {}
        }
        
        for section_name in section_names:
            if section_name in xml_data['sections']:
                extracted_data['sections'][section_name] = xml_data['sections'][section_name]
        
        return extracted_data


# Utility functions that don't fit into classes
def get_class_name_from_path(xml_path: str) -> str:
    """
    Extract class name from XML file path.
    
    Args:
        xml_path: Path like "Classes/TestClass-Documentation.xml"
        
    Returns:
        Class name like "TestClass"
    """
    filename = os.path.basename(xml_path)
    if filename.endswith('-Documentation.xml'):
        return filename[:-len('-Documentation.xml')]
    return filename.replace('.xml', '')


def sort_members_by_type(members: List[Dict]) -> List[Dict]:
    """
    Sort members by type (Methods, Properties, Fields) and then alphabetically.
    
    Args:
        members: List of member dicts with 'type' and 'name' keys
        
    Returns:
        Sorted list of members
    """
    # Define sort order
    type_order = {'method': 0, 'property': 1, 'field': 2, 'unknown': 3}
    
    return sorted(members, key=lambda m: (
        type_order.get(m.get('type', 'unknown'), 3),
        m.get('name', '').lower()
    ))