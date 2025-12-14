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
