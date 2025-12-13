# Sample PDFs for Testing PDF-OCR MVP

This directory contains sample PDFs for testing different extraction scenarios.

## Test Cases

### 1. Simple Invoice
- **File**: `sample-invoice.pdf`
- **Use Case**: Vendor information extraction
- **Regions to Test**:
  - Vendor name and address (top section)
  - Invoice number and date
  - Line items table
  - Total amount

### 2. Form with Fields
- **File**: `sample-form.pdf`
- **Use Case**: Form field extraction
- **Regions to Test**:
  - Name field
  - Address fields
  - Date fields
  - Checkbox sections

### 3. Financial Statement
- **File**: `sample-statement.pdf`
- **Use Case**: Table extraction
- **Regions to Test**:
  - Income statement table
  - Balance sheet
  - Notes section

### 4. Receipt
- **File**: `sample-receipt.pdf`
- **Use Case**: Line item extraction
- **Regions to Test**:
  - Store information
  - Item list
  - Payment details

## Creating Your Own Test PDFs

### Best Practices
1. **Resolution**: 300 DPI or higher
2. **Format**: Searchable PDF (not scanned image)
3. **Text Quality**: Clear, legible fonts
4. **Tables**: Well-defined borders
5. **Size**: Under 10 MB for faster processing

### Tools for Creating Test PDFs
- **Microsoft Word**: Save as PDF
- **Google Docs**: Download as PDF
- **LibreOffice**: Export to PDF
- **Online Tools**: PDF.co, PDFescape

## Demo Scenarios

### Scenario 1: Vendor Invoice Processing
1. Upload `sample-invoice.pdf`
2. Select vendor info region
3. Select line items table
4. Export as CSV
5. Show structured data in Excel

### Scenario 2: Form Data Entry
1. Upload `sample-form.pdf`
2. Select individual form fields
3. Export as JSON
4. Show key-value pairs

### Scenario 3: Financial Analysis
1. Upload `sample-statement.pdf`
2. Select financial tables
3. Export as TSV
4. Import into analysis tool

## Where to Find Test PDFs

### Free Resources
- **Invoice PDFs**: Search "sample invoice PDF" on Google
- **Forms**: Government forms (IRS, DMV)
- **Financial**: Company annual reports (10-K filings)
- **Receipts**: Create your own or use template sites

### Commercial Samples
- **PDF.co**: Sample documents library
- **DocHub**: Template documents
- **Template.net**: Business forms

## Tips for Demo

1. **Prepare Multiple PDFs**: Have 3-4 ready
2. **Test Beforehand**: Verify extraction quality
3. **Know the Content**: Understand what's in each PDF
4. **Show Variety**: Different document types
5. **Highlight Accuracy**: Point out confidence scores

## Troubleshooting

### Low Confidence Scores
- Increase PDF resolution
- Use clearer fonts
- Ensure good contrast

### Table Extraction Issues
- Use Form Parser processor (not Document OCR)
- Ensure tables have clear borders
- Test with simpler tables first

### Missing Text
- Verify PDF is searchable (not scanned image)
- Check if text is actually embedded
- Try different processor types

## Note

This MVP does not include sample PDFs in the repository due to copyright concerns. Please create your own or use publicly available documents for testing.
