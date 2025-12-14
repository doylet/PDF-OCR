#!/usr/bin/env python3
"""Script to create a Document AI Form Parser processor"""

from google.cloud import documentai_v1 as documentai
import os

def create_form_parser_processor():
    # Get project ID from environment or use default
    project_id = os.environ.get('GCP_PROJECT_ID', 'sylvan-replica-478802-p4')
    location = 'us'
    
    # Initialize client
    client = documentai.DocumentProcessorServiceClient()
    
    # The parent resource name
    parent = client.common_location_path(project_id, location)
    
    # Create the processor
    processor = documentai.Processor(
        display_name="pdf-ocr-form-parser",
        type_="FORM_PARSER_PROCESSOR"
    )
    
    print(f"Creating Form Parser processor in {parent}...")
    
    try:
        operation = client.create_processor(
            parent=parent,
            processor=processor
        )
        
        print(f"Processor created successfully!")
        print(f"Processor ID: {operation.name.split('/')[-1]}")
        print(f"Full name: {operation.name}")
        
        return operation.name.split('/')[-1]
    
    except Exception as e:
        print(f"Error creating processor: {e}")
        return None

if __name__ == "__main__":
    processor_id = create_form_parser_processor()
    if processor_id:
        print(f"\nUpdate your backend configuration with this processor ID: {processor_id}")
