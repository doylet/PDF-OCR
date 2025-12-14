from app.models import ExtractionResult
from typing import List
import csv
import io
import json
import logging
import re

logger = logging.getLogger(__name__)


class FormatterService:
    """Service for formatting extraction results"""
    
    @staticmethod
    def parse_text_as_table(text: str) -> List[List[str]]:
        """Try to parse text as a table by detecting common patterns
        
        Handles both horizontal (row-based) and vertical (column-based) layouts
        """
        lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
        
        if not lines:
            return None
        
        # Check if this looks like vertical columns (header words on separate lines)
        # Pattern: "Date\n06 Oct\n07 Oct\n...\nDescription\nData Usage\n...\nVolume\n671MB\n..."
        if len(lines) > 3 and all(len(line.split()) <= 3 for line in lines[:10]):
            # Try to identify column headers
            potential_headers = []
            data_start_idx = 0
            
            for i, line in enumerate(lines):
                # Column header likely: single word or 2 words, capitalized, no numbers
                if re.match(r'^[A-Z][a-z]+(\s+[A-Z][a-z]+)?$', line):
                    potential_headers.append((i, line))
                elif potential_headers and not re.match(r'^\d', line):
                    # Still might be header if no digits yet
                    potential_headers.append((i, line))
                else:
                    # Found first data line
                    data_start_idx = i
                    break
            
            # If we found headers, try to parse as columns
            if len(potential_headers) >= 2:
                header_indices = [idx for idx, _ in potential_headers]
                headers = [name for _, name in potential_headers]
                num_cols = len(headers)
                
                # Split remaining lines into columns
                remaining_lines = lines[data_start_idx:]
                rows_per_col = len(remaining_lines) // num_cols
                
                if rows_per_col > 0:
                    table_data = [headers]  # Add header row
                    
                    for row_idx in range(rows_per_col):
                        row = []
                        for col_idx in range(num_cols):
                            line_idx = col_idx * rows_per_col + row_idx
                            if line_idx < len(remaining_lines):
                                row.append(remaining_lines[line_idx])
                            else:
                                row.append('')
                        table_data.append(row)
                    
                    return table_data if len(table_data) > 1 else None
        
        # Fallback: try horizontal parsing (original logic)
        table_data = []
        
        for line in lines:
            # First try: split by multiple spaces (most reliable for OCR)
            parts = re.split(r'\s{3,}', line)
            if len(parts) >= 2:
                table_data.append(parts)
                continue
            
            # Second try: Look for data patterns like "DD Mon Description Value"
            match = re.match(r'^(\d{1,2}\s+\w+)\s+(.*?)\s+(\d+[\d.,]*(?:MB|GB|KB)?)$', line, re.IGNORECASE)
            if match:
                table_data.append([match.group(1), match.group(2), match.group(3)])
                continue
            
            # Third try: split by 2 or more spaces
            parts = re.split(r'\s{2,}', line)
            if len(parts) >= 2:
                table_data.append(parts)
        
        return table_data if table_data else None
    
    @staticmethod
    def format_as_csv(results: List[ExtractionResult]) -> str:
        """Format results as CSV"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(["Region", "Page", "Text", "Confidence", "Has_Structured_Data"])
        
        # Write data
        for result in results:
            has_structured = "Yes" if result.structured_data else "No"
            # Escape newlines in text
            text = result.text.replace('\n', ' ').replace('\r', ' ')
            writer.writerow([
                result.region_index,
                result.page,
                text,
                f"{result.confidence:.2f}",
                has_structured
            ])
        
        # Add structured data section if present
        has_structured_data = any(r.structured_data for r in results)
        if has_structured_data:
            writer.writerow([])
            writer.writerow(["=== STRUCTURED DATA ==="])
            
            for result in results:
                if result.structured_data:
                    writer.writerow([])
                    writer.writerow([f"Region {result.region_index} - Page {result.page}"])
                    
                    # Tables
                    if result.structured_data.get("tables"):
                        writer.writerow(["Tables:"])
                        for table_idx, table in enumerate(result.structured_data["tables"]):
                            writer.writerow([f"Table {table_idx + 1}"])
                            for row in table:
                                writer.writerow(row)
                            writer.writerow([])
                    
                    # Form fields
                    if result.structured_data.get("form_fields"):
                        writer.writerow(["Form Fields:"])
                        writer.writerow(["Field Name", "Field Value"])
                        for field in result.structured_data["form_fields"]:
                            writer.writerow([field["name"], field["value"]])
        
        return output.getvalue()
    
    @staticmethod
    def format_as_tsv(results: List[ExtractionResult]) -> str:
        """Format results as TSV - prioritize table data if available"""
        output = io.StringIO()
        writer = csv.writer(output, delimiter='\t')
        
        # Check if we have structured table data
        has_tables = any(r.structured_data and r.structured_data.get("tables") for r in results)
        
        if has_tables:
            # Output detected tables directly in TSV format
            for result in results:
                if result.structured_data and result.structured_data.get("tables"):
                    for table_idx, table in enumerate(result.structured_data["tables"]):
                        if table_idx > 0:
                            writer.writerow([])  # Blank line between tables
                        for row in table:
                            writer.writerow(row)
        else:
            # Try to parse text as table
            parsed_any_table = False
            for result in results:
                parsed_table = FormatterService.parse_text_as_table(result.text)
                if parsed_table:
                    parsed_any_table = True
                    for row in parsed_table:
                        writer.writerow(row)
                    writer.writerow([])  # Blank line between results
            
            # If parsing didn't work, output raw text
            if not parsed_any_table:
                writer.writerow(["Region", "Page", "Text", "Confidence"])
                for result in results:
                    text = result.text.replace('\n', ' ').replace('\r', ' ')
                    writer.writerow([
                        result.region_index,
                        result.page,
                        text,
                        f"{result.confidence:.2f}"
                    ])
        
        return output.getvalue()
    
    @staticmethod
    def format_as_json(results: List[ExtractionResult]) -> str:
        """Format results as JSON"""
        output = {
            "results": [result.dict() for result in results],
            "summary": {
                "total_regions": len(results),
                "average_confidence": sum(r.confidence for r in results) / len(results) if results else 0,
                "regions_with_structured_data": sum(1 for r in results if r.structured_data)
            }
        }
        return json.dumps(output, indent=2)


formatter_service = FormatterService()
