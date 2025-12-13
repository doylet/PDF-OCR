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
        """Try to parse text as a table by detecting common patterns"""
        lines = text.strip().split('\n')
        table_data = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Try to split by multiple spaces (common in OCR text)
            parts = re.split(r'\s{2,}', line)
            if len(parts) > 1:
                table_data.append(parts)
            else:
                # Fallback: split by single space if we have date-like patterns
                parts = line.split()
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
