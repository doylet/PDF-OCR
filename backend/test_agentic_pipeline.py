"""
Test script for agentic document understanding pipeline.
"""
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.agents.orchestrator import ExpectOrchestrator
from app.agents.table_agent import TableAgent
from app.agents.validator_agent import ValidatorAgent

def test_orchestrator():
    """Test the full orchestration pipeline"""
    
    # Use your test PDF path
    pdf_path = "path/to/your/test.pdf"
    job_id = "test-job-001"
    
    print(f"Testing orchestrator with {pdf_path}...")
    
    # Run orchestrator
    orchestrator = ExpectOrchestrator(pdf_path, job_id)
    graph = orchestrator.run()
    
    # Print results
    print(f"\nJob Status: {graph.status}")
    print(f"Pages: {len(graph.pages)}")
    print(f"Tokens: {len(graph.tokens)}")
    print(f"Regions: {len(graph.regions)}")
    print(f"Extractions: {len(graph.extractions)}")
    
    # Print decisions
    print("\nAgent Decisions:")
    for decision in graph.decisions:
        print(f"  {decision}")
    
    # Print extractions
    print("\nExtractions:")
    for extraction in graph.extractions:
        print(f"\n  {extraction.extraction_id}:")
        print(f"    Type: {extraction.region_id}")
        print(f"    Status: {extraction.validation_status}")
        print(f"    Confidence: {extraction.confidence:.2f}")
        if extraction.data.get("rows"):
            print(f"    Rows: {len(extraction.data['rows'])}")
            print(f"    Sample: {extraction.data['rows'][:2]}")
    
    return graph

def test_table_agent():
    """Test table extraction on a specific region"""
    from app.models.document_graph import (
        DocumentGraph, Token, Region, BBox,
        TokenType, RegionType, ExtractionMethod
    )
    
    # Create mock graph with tokens
    graph = DocumentGraph(job_id="test-table", pdf_path="test.pdf")
    
    # Add mock tokens simulating a 3x3 table
    # Header row
    graph.add_token(Token("Date", BBox(0.1, 0.1, 0.1, 0.05), 0, TokenType.TEXT))
    graph.add_token(Token("Description", BBox(0.3, 0.1, 0.2, 0.05), 0, TokenType.TEXT))
    graph.add_token(Token("Amount", BBox(0.6, 0.1, 0.1, 0.05), 0, TokenType.TEXT))
    
    # Data row 1
    graph.add_token(Token("01/12", BBox(0.1, 0.2, 0.1, 0.05), 0, TokenType.DATE))
    graph.add_token(Token("Purchase", BBox(0.3, 0.2, 0.2, 0.05), 0, TokenType.TEXT))
    graph.add_token(Token("$45.67", BBox(0.6, 0.2, 0.1, 0.05), 0, TokenType.CURRENCY))
    
    # Create region
    region = Region(
        region_id="test_table_region",
        region_type=RegionType.TABLE,
        bbox=BBox(0.1, 0.1, 0.7, 0.2),
        page=0,
        token_ids=[0, 1, 2, 3, 4, 5],
        detected_by="test",
        confidence=1.0
    )
    graph.add_region(region)
    
    # Extract table
    extraction = TableAgent.extract_table(graph, region)
    
    if extraction:
        print(f"\nTable extracted:")
        print(f"  Rows: {len(extraction.data['rows'])}")
        print(f"  Columns: {len(extraction.data['columns'])}")
        print(f"  Data: {extraction.data['rows']}")
    else:
        print("Table extraction failed")
    
    return extraction

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Agentic Document Understanding Pipeline")
    print("=" * 60)
    
    # Test 1: Table Agent (unit test)
    print("\n[TEST 1] Table Agent Unit Test")
    print("-" * 60)
    test_table_agent()
    
    # Test 2: Full orchestrator (if PDF available)
    # Uncomment and provide your PDF path
    # print("\n[TEST 2] Full Orchestrator")
    # print("-" * 60)
    # test_orchestrator()
    
    print("\n" + "=" * 60)
    print("Tests complete!")
