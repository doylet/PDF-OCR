import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class TextParser:
    """Parse OCR text into structured tables"""
    
    @staticmethod
    def parse_to_table(text: str) -> Optional[List[List[str]]]:
        """
        Parse newline-separated OCR text into table rows using multiple strategies.
        
        Tries strategies in order of specificity:
        1. Date+Volume pairing (telecom bills, usage tables)
        2. Row-based with delimiters (TSV-like)
        3. Generic column layout detection
        """
        lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
        
        if len(lines) < 4:
            return None
        
        # Strategy 1: Date+Volume pairing (most specific, highest confidence)
        result = TextParser._parse_column_layout(lines)
        if result:
            return result
        
        # Strategy 2: Row-based with tab/multi-space separation (structured format)
        result = TextParser._parse_row_layout(lines)
        if result:
            return result
        
        # Strategy 3: Generic column detection (fallback)
        result = TextParser._parse_generic_columns(lines)
        if result:
            return result
        
        return None
    
    @staticmethod
    def _parse_column_layout(lines: List[str]) -> Optional[List[List[str]]]:
        """
        Parse text by detecting date + volume patterns and pairing them into rows.
        
        Handles format where dates and volumes are mixed:
        06 Oct\nData Usage\n671.33MB\n07 Oct\nData Usage\n337.87MB...
        """
        import re
        
        # Detect dates (dd Mon format)
        date_pattern = re.compile(r'^\d{1,2}\s+[A-Z][a-z]{2}$')
        # Detect volumes (number + MB/GB/KB)
        volume_pattern = re.compile(r'^\d+(\.\d+)?(MB|GB|KB)$', re.IGNORECASE)
        
        # Find all dates and volumes with their line indices
        dates = []
        volumes = []
        descriptions = []
        
        for i, line in enumerate(lines):
            if date_pattern.match(line):
                dates.append((i, line))
            elif volume_pattern.match(line):
                volumes.append((i, line))
            elif 'usage' in line.lower() or 'data' in line.lower():
                descriptions.append((i, line))
        
        # Need at least some dates and volumes
        if len(dates) < 2 or len(volumes) < 2:
            logger.debug(f"Not enough dates ({len(dates)}) or volumes ({len(volumes)}) for row parsing")
            return None
        
        # Build rows by pairing dates with their nearest following volume
        table = [["Date", "Description", "Volume"]]
        
        for date_idx, date_text in dates:
            # Find the next volume after this date
            next_volume = None
            for vol_idx, vol_text in volumes:
                if vol_idx > date_idx:
                    next_volume = vol_text
                    break
            
            # Find description between date and volume
            description = "Data Usage"  # Default
            for desc_idx, desc_text in descriptions:
                if date_idx < desc_idx < (vol_idx if next_volume else float('inf')):
                    description = desc_text
                    break
            
            if next_volume:
                table.append([date_text, description, next_volume])
        
        if len(table) > 1:
            logger.info(f"Parsed {len(table)-1} rows using date+volume pairing")
            return table
        
        return None
    
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
    
    @staticmethod
    def _parse_generic_columns(lines: List[str]) -> Optional[List[List[str]]]:
        """
        Generic column detection fallback.
        
        Looks for repeated patterns suggesting columnar structure:
        - Header keywords in first few lines
        - Consistent column count across rows
        """
        import re
        
        # Look for header candidates (common table words)
        header_keywords = ['date', 'time', 'amount', 'total', 'description', 
                          'name', 'number', 'id', 'status', 'type', 'quantity', 'price']
        
        potential_headers = []
        data_start_idx = 0
        
        for idx, line in enumerate(lines[:5]):  # Check first 5 lines for headers
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in header_keywords):
                potential_headers.append(line)
                data_start_idx = idx + 1
        
        if not potential_headers or data_start_idx >= len(lines):
            return None
        
        # Try to detect column count from headers
        header_line = ' '.join(potential_headers)
        possible_columns = re.split(r'[,\t|]|\s{2,}', header_line)
        possible_columns = [col.strip() for col in possible_columns if col.strip()]
        
        if len(possible_columns) < 2:
            return None
        
        # Parse remaining lines into that many columns
        rows = [possible_columns]  # Start with headers
        
        for line in lines[data_start_idx:]:
            cells = re.split(r'[,\t|]|\s{2,}', line)
            cells = [cell.strip() for cell in cells if cell.strip()]
            
            if len(cells) == len(possible_columns):
                rows.append(cells)
            elif len(cells) > 0:
                # Pad or truncate to match column count
                while len(cells) < len(possible_columns):
                    cells.append('')
                rows.append(cells[:len(possible_columns)])
        
        # Only return if we got some data rows
        if len(rows) > 1:
            logger.info(f"Generic column parser extracted {len(rows)-1} rows with {len(possible_columns)} columns")
            return rows
        
        return None
