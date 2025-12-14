import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class TextParser:
    """Parse OCR text into structured tables"""
    
    @staticmethod
    def parse_to_table(text: str) -> Optional[List[List[str]]]:
        """
        Parse newline-separated OCR text into table rows.
        
        Handles common layouts like:
        - Column headers on separate lines followed by data
        - Values reading top-to-bottom, left-to-right
        """
        lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
        
        if len(lines) < 4:
            return None
        
        # Strategy 1: Detect column-based layout with headers
        # Pattern: "Header1\nvalue1\nvalue2\n...\nHeader2\nvalue1\nvalue2..."
        result = TextParser._parse_column_layout(lines)
        if result:
            return result
        
        # Strategy 2: Row-based with tab/multi-space separation
        result = TextParser._parse_row_layout(lines)
        if result:
            return result
        
        return None
    
    @staticmethod
    def _parse_column_layout(lines: List[str]) -> Optional[List[List[str]]]:
        """
        Parse vertical column layout where headers appear first,
        then all values for column 1, then all values for column 2, etc.
        
        Example:
        Date\n06 Oct\n07 Oct\n...\nDescription\nData Usage\nData Usage\n...\nVolume\n671MB\n337MB...
        """
        # Find potential column headers - typically capitalized words, no digits
        header_indices = []
        
        for i, line in enumerate(lines):
            # Header patterns:
            # - Single capitalized word: "Date", "Volume", "Description"
            # - Two capitalized words: "Data Usage"
            # - No leading digits
            words = line.split()
            if (len(words) <= 3 and 
                line[0].isupper() and 
                not any(char.isdigit() for char in line[:3])):
                header_indices.append(i)
        
        # Need at least 2 columns
        if len(header_indices) < 2:
            return None
        
        # Check if headers are reasonably spaced (not consecutive)
        if all(header_indices[i+1] - header_indices[i] <= 2 for i in range(len(header_indices)-1)):
            # Headers too close together, probably not column headers
            return None
        
        # Extract headers
        headers = [lines[i] for i in header_indices]
        
        # Calculate rows per column
        # Assume equal distribution of data across columns
        total_data_lines = len(lines) - len(header_indices)
        rows_per_column = total_data_lines // len(header_indices)
        
        if rows_per_column == 0:
            return None
        
        # Build data array - track current position after headers
        data_sections = []
        current_pos = 0
        
        for i, header_idx in enumerate(header_indices):
            # Skip to next section (after current header)
            section_start = header_idx + 1
            
            # Find section end (next header or end of list)
            if i < len(header_indices) - 1:
                section_end = header_indices[i + 1]
            else:
                section_end = len(lines)
            
            section_data = lines[section_start:section_end]
            data_sections.append(section_data)
        
        # Verify sections have similar lengths (within 20% tolerance)
        section_lengths = [len(s) for s in data_sections]
        avg_length = sum(section_lengths) / len(section_lengths)
        if not all(abs(length - avg_length) / avg_length < 0.3 for length in section_lengths):
            # Sections too uneven, probably not column layout
            logger.debug(f"Section lengths too uneven: {section_lengths}")
            return None
        
        # Build table rows
        table = [headers]
        num_rows = min(section_lengths)  # Use minimum to avoid index errors
        
        for row_idx in range(num_rows):
            row = []
            for section in data_sections:
                if row_idx < len(section):
                    row.append(section[row_idx])
                else:
                    row.append('')
            table.append(row)
        
        logger.info(f"Parsed {len(table)-1} rows with {len(headers)} columns")
        return table if len(table) > 1 else None
    
    @staticmethod
    def _parse_row_layout(lines: List[str]) -> Optional[List[List[str]]]:
        """Parse traditional row-based layout with delimiters"""
        import re
        
        table = []
        for line in lines:
            # Split by tabs or 3+ spaces
            if '\t' in line:
                parts = line.split('\t')
            else:
                parts = re.split(r'\s{3,}', line)
            
            if len(parts) >= 2:
                table.append([p.strip() for p in parts])
        
        return table if len(table) > 1 else None
