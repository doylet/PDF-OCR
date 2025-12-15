'use client';

import { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { Region, JobStatus } from '@/types/api';
import { apiClient } from '@/lib/api-client';
import RegionList from '@/components/RegionList';
import JobStatusDisplay from '@/components/JobStatusDisplay';
import { Upload, FileText } from 'lucide-react';

// Dynamically import PDFViewer to avoid SSR issues with react-pdf
const PDFViewer = dynamic(() => import('@/components/PDFViewer'), {
  ssr: false,
  loading: () => <div className="flex items-center justify-center h-96 bg-gray-50 rounded-lg">Loading PDF viewer...</div>
});

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [pdfId, setPdfId] = useState<string | null>(null);
  const [regions, setRegions] = useState<Region[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [outputFormat, setOutputFormat] = useState<'csv' | 'tsv' | 'json'>('csv');
  const [extractionMethod, setExtractionMethod] = useState<'classic' | 'agentic'>('agentic');
  const [job, setJob] = useState<JobStatus | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detectedRegions, setDetectedRegions] = useState<any[]>([]);

  // Poll job status
  useEffect(() => {
    if (!job || job.status === 'completed' || job.status === 'failed') return;

    const interval = setInterval(async () => {
      try {
        const updatedJob = await apiClient.getJobStatus(job.job_id);
        setJob(updatedJob);
      } catch (err) {
        console.error('Error polling job status:', err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [job]);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;

    if (selectedFile.type !== 'application/pdf') {
      setError('Please select a PDF file');
      return;
    }

    setFile(selectedFile);
    setRegions([]);
    setJob(null);
    setError(null);

    // Upload PDF
    setIsUploading(true);
    try {
      const { pdf_id, upload_url } = await apiClient.generateUploadURL(selectedFile.name);
      await apiClient.uploadPDF(upload_url, selectedFile);
      setPdfId(pdf_id);
      setError(null);
    } catch (err) {
      setError(`Upload failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
      setFile(null);
    } finally {
      setIsUploading(false);
    }
  };

  const handleRegionAdd = (region: Region) => {
    setRegions([...regions, region]);
  };

  const handleRegionRemove = (index: number) => {
    setRegions(regions.filter((_, i) => i !== index));
  };

  const handleLabelChange = (index: number, label: string) => {
    const updatedRegions = [...regions];
    updatedRegions[index] = { ...updatedRegions[index], label };
    setRegions(updatedRegions);
  };

  const handleExtract = async () => {
    if (!pdfId) return;
    if (extractionMethod === 'classic' && regions.length === 0) return;

    setIsProcessing(true);
    setError(null);

    try {
      const extractionRequest = {
        pdf_id: pdfId,
        regions,
        output_format: outputFormat,
      };
      
      const job = extractionMethod === 'agentic'
        ? await apiClient.createAgenticExtractionJob(extractionRequest)
        : await apiClient.createExtractionJob(extractionRequest);
      
      setJob(job);
    } catch (err) {
      setError(`Extraction failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDownload = async () => {
    if (!job?.result_url) return;

    try {
      const blob = await apiClient.downloadResult(job.result_url);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `extraction-result.${outputFormat}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      setError(`Download failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 py-8 px-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-800 mb-2">PDF-OCR MVP</h1>
          <p className="text-gray-600">
            Extract structured data from PDF regions using GCP Document AI
          </p>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border-2 border-red-200 rounded-lg">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        {/* Upload Section */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-semibold flex items-center">
              <Upload className="mr-2" size={24} />
              Upload PDF
            </h2>
            {file && (
              <span className="text-sm text-gray-600 flex items-center">
                <FileText className="mr-1" size={16} />
                {file.name}
              </span>
            )}
          </div>

          <label className="block">
            <input
              type="file"
              accept="application/pdf"
              onChange={handleFileChange}
              disabled={isUploading}
              className="block w-full text-sm text-gray-500
                file:mr-4 file:py-2 file:px-4
                file:rounded file:border-0
                file:text-sm file:font-semibold
                file:bg-blue-50 file:text-blue-700
                hover:file:bg-blue-100
                disabled:opacity-50"
            />
          </label>

          {isUploading && (
            <p className="mt-2 text-sm text-blue-600">Uploading PDF...</p>
          )}
        </div>

        {/* Main Content */}
        {file && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* PDF Viewer */}
            <div className="lg:col-span-2 bg-white rounded-lg shadow-lg p-6">
              <h2 className="text-2xl font-semibold mb-4">PDF Viewer</h2>
              <PDFViewer
                file={file}
                regions={regions}
                onRegionAdd={handleRegionAdd}
                onRegionRemove={handleRegionRemove}
                currentPage={currentPage}
                onPageChange={setCurrentPage}
                detectedRegions={detectedRegions}
              />
            </div>

            {/* Sidebar */}
            <div className="space-y-6">
              {/* Region List */}
              <div className="bg-white rounded-lg shadow-lg p-6">
                <RegionList
                  regions={regions}
                  onRemove={handleRegionRemove}
                  onLabelChange={handleLabelChange}
                />
              </div>

              {/* Extraction Controls */}
              <div className="bg-white rounded-lg shadow-lg p-6">
                <h3 className="text-lg font-semibold mb-3">Export Settings</h3>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium mb-1">Extraction Method</label>
                    <select
                      value={extractionMethod}
                      onChange={(e) => setExtractionMethod(e.target.value as 'classic' | 'agentic')}
                      className="w-full px-3 py-2 border border-gray-300 rounded"
                    >
                      <option value="classic">Classic (Manual Regions)</option>
                      <option value="agentic">Agentic (Auto-Detect)</option>
                    </select>
                    <p className="text-xs text-gray-500 mt-1">
                      {extractionMethod === 'agentic' 
                        ? '🤖 AI agents auto-detect tables and structure'
                        : '📍 Manually select regions to extract'}
                    </p>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium mb-1">Output Format</label>
                    <select
                      value={outputFormat}
                      onChange={(e) => setOutputFormat(e.target.value as 'csv' | 'tsv' | 'json')}
                      className="w-full px-3 py-2 border border-gray-300 rounded"
                    >
                      <option value="csv">CSV</option>
                      <option value="tsv">TSV</option>
                      <option value="json">JSON</option>
                    </select>
                  </div>

                  <button
                    onClick={handleExtract}
                    disabled={(extractionMethod === 'classic' && regions.length === 0) || isProcessing || !pdfId}
                    className="w-full px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition font-semibold"
                  >
                    {isProcessing ? 'Starting Extraction...' : 'Extract Data'}
                  </button>
                </div>
              </div>

              {/* Job Status */}
              {job && (
                <div className="bg-white rounded-lg shadow-lg p-6">
                  <JobStatusDisplay 
                    job={job} 
                    onDownload={handleDownload}
                    onRegionsDetected={setDetectedRegions}
                  />
                </div>
              )}
            </div>
          </div>
        )}

        {/* Instructions */}
        {!file && (
          <div className="bg-white rounded-lg shadow-lg p-8 text-center">
            <FileText className="mx-auto mb-4 text-gray-400" size={64} />
            <h3 className="text-xl font-semibold mb-2">Get Started</h3>
            <p className="text-gray-600 mb-4">
              Upload a PDF to begin extracting structured data from specific regions
            </p>
            <ol className="text-left max-w-md mx-auto space-y-2 text-sm text-gray-600">
              <li>1. Upload your PDF document</li>
              <li>2. Click and drag to select regions on the PDF</li>
              <li>3. Choose your output format (CSV, TSV, or JSON)</li>
              <li>4. Click &quot;Extract Data&quot; to process</li>
              <li>5. Download your results when complete</li>
            </ol>
          </div>
        )}
      </div>
    </main>
  );
}
