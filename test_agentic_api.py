#!/usr/bin/env python3
import requests
import json
import sys

API_URL = "https://pdf-ocr-api-785693222332.us-central1.run.app"

def test_health():
    print("Testing health endpoint...")
    response = requests.get(f"{API_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}\n")
    return response.status_code == 200

def test_agentic_extraction(pdf_path):
    print(f"Testing agentic extraction with: {pdf_path}")
    
    if not pdf_path:
        print("No PDF path provided. Please provide a PDF file path as argument.")
        print("Usage: python test_agentic_api.py <path_to_pdf>")
        return False
    
    try:
        with open(pdf_path, 'rb') as f:
            files = {'file': (pdf_path.split('/')[-1], f, 'application/pdf')}
            
            print("Uploading PDF to agentic extraction endpoint...")
            response = requests.post(
                f"{API_URL}/extract/agentic",
                files=files,
                params={'output_format': 'json'}
            )
            
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                
                print("\n=== EXTRACTION RESULT ===")
                print(json.dumps(result, indent=2))
                
                if 'summary' in result:
                    summary = result['summary']
                    print("\n=== SUMMARY ===")
                    print(f"Outcome: {summary.get('outcome')}")
                    print(f"Pages: {summary.get('pages')}")
                    print(f"Regions Proposed: {summary.get('regions_proposed')}")
                    print(f"Regions Extracted: {summary.get('regions_extracted')}")
                    
                    if 'trace' in summary:
                        print("\n=== TRACE ===")
                        for i, entry in enumerate(summary['trace'], 1):
                            print(f"{i}. {entry.get('step')} - {entry.get('status')}")
                            for key, value in entry.items():
                                if key not in ['step', 'status', 'timestamp']:
                                    print(f"   {key}: {value}")
                
                return True
            else:
                print(f"Error: {response.text}")
                return False
                
    except FileNotFoundError:
        print(f"Error: PDF file not found at {pdf_path}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    print("=== PDF OCR API Test ===\n")
    
    if test_health():
        pdf_path = sys.argv[1] if len(sys.argv) > 1 else None
        if pdf_path:
            test_agentic_extraction(pdf_path)
        else:
            print("\nSkipping agentic extraction test - no PDF provided")
            print("To test extraction: python test_agentic_api.py <path_to_pdf>")
    else:
        print("Health check failed!")
