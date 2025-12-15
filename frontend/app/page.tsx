'use client';

import { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { Region, JobStatus } from '@/types/api';
import { apiClient } from '@/lib/api-client';
import AgenticProcessingFeedback from '@/components/AgenticProcessingFeedback';
import { Upload, FileText, Sparkles, Grid3x3, Download, Check, Loader2, X, Brain, Play, AlertCircle } from 'lucide-react';

interface DetectedRegion {
  region_id: string;
  region_type: string;
  bbox: {
    x: number;
    y: number;
    w: number;
    h: number;
  };
  page: number;
  confidence: number;
}

// Dynamically import PDFViewer to avoid SSR issues
const PDFViewer = dynamic(() => import('@/components/PDFViewer'), {
  ssr: false,
  loading: () => (
    <div className="bg-slate-900 rounded-lg border border-slate-700 flex items-center justify-center" style={{ minHeight: '700px' }}>
      <Loader2 className="text-slate-600 animate-spin" size={40} />
    </div>
  )
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
  const [detectedRegions, setDetectedRegions] = useState<DetectedRegion[]>([]);

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
    <div className="min-h-screen bg-slate-950">
      {/* Header */}
      <header className="bg-slate-900/50 border-b border-slate-800 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-[1800px] mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg flex items-center justify-center">
                <FileText className="text-white" size={18} />
              </div>
              <div>
                <h1 className="text-lg font-semibold text-white">PDF-OCR</h1>
                <p className="text-xs text-slate-400">Document Intelligence Platform</p>
              </div>
            </div>
            
            {file && (
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-3 px-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg">
                  <FileText className="text-slate-400" size={16} />
                  <div>
                    <p className="text-sm text-slate-200">{file.name}</p>
                    <p className="text-xs text-slate-500">{(file.size / 1024).toFixed(1)} KB</p>
                  </div>
                </div>
                <button
                  onClick={() => {
                    setFile(null);
                    setPdfId(null);
                    setRegions([]);
                    setJob(null);
                  }}
                  className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition"
                >
                  <X size={18} />
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-[1800px] mx-auto px-6 py-6">
        {/* Error Display */}
        {error && (
          <div className="mb-4 p-4 bg-red-500/10 border border-red-500/30 rounded-lg flex items-start gap-3">
            <AlertCircle className="text-red-400 flex-shrink-0 mt-0.5" size={18} />
            <div className="flex-1">
              <p className="text-sm text-red-300">{error}</p>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-red-400 hover:text-red-300 transition"
            >
              <X size={16} />
            </button>
          </div>
        )}

        {!file ? (
          /* Upload Screen */
          <div className="max-w-4xl mx-auto">
            <div className="text-center mb-8">
              <h2 className="text-3xl font-bold text-white mb-2">Extract Structured Data from PDFs</h2>
              <p className="text-slate-400">Powered by AI agents and GCP Document AI</p>
            </div>

            <label className="block cursor-pointer group">
              <div className="bg-slate-900/50 border-2 border-dashed border-slate-700 hover:border-blue-500/50 rounded-xl p-16 text-center transition-all hover:bg-slate-900/80">
                {isUploading ? (
                  <div className="flex flex-col items-center">
                    <Loader2 className="text-blue-500 animate-spin mb-4" size={48} />
                    <p className="text-slate-300 font-medium">Uploading...</p>
                  </div>
                ) : (
                  <>
                    <Upload className="mx-auto text-slate-500 group-hover:text-blue-500 transition mb-4" size={48} />
                    <p className="text-lg text-slate-200 font-medium mb-2">Drop your PDF here or click to browse</p>
                    <p className="text-sm text-slate-500">Supports PDF files up to 50MB</p>
                  </>
                )}
              </div>
              <input
                type="file"
                accept="application/pdf"
                onChange={handleFileChange}
                disabled={isUploading}
                className="hidden"
              />
            </label>

            <div className="grid md:grid-cols-2 gap-4 mt-8">
              <div className="bg-slate-900/30 border border-slate-800 rounded-lg p-6">
                <div className="w-10 h-10 bg-blue-500/20 border border-blue-500/30 rounded-lg flex items-center justify-center mb-4">
                  <Sparkles className="text-blue-400" size={20} />
                </div>
                <h3 className="text-white font-semibold mb-2">AI Agent Mode</h3>
                <p className="text-sm text-slate-400">Automatically detect and extract tables, forms, and structured data using advanced AI</p>
              </div>

              <div className="bg-slate-900/30 border border-slate-800 rounded-lg p-6">
                <div className="w-10 h-10 bg-slate-700/50 border border-slate-600 rounded-lg flex items-center justify-center mb-4">
                  <Grid3x3 className="text-slate-400" size={20} />
                </div>
                <h3 className="text-white font-semibold mb-2">Manual Selection</h3>
                <p className="text-sm text-slate-400">Precisely control extraction by selecting specific regions in your document</p>
              </div>
            </div>
          </div>
        ) : (
          /* Main Interface */
          <div className="grid grid-cols-1 lg:grid-cols-[1fr,380px] gap-6">
            {/* Left: PDF Viewer */}
            <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
              <PDFViewer
                file={file}
                regions={regions}
                onRegionAdd={handleRegionAdd}
                onRegionRemove={handleRegionRemove}
                currentPage={currentPage}
                onPageChange={setCurrentPage}
                detectedRegions={detectedRegions}
                onRegionsDetected={setDetectedRegions}
              />
            </div>

            {/* Right: Controls */}
            <div className="space-y-4">
              {/* Mode Toggle */}
              <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-1 flex gap-1">
                <button
                  onClick={() => setExtractionMethod('agentic')}
                  className={`flex-1 px-4 py-3 rounded-md font-medium text-sm transition-all flex items-center justify-center gap-2 ${
                    extractionMethod === 'agentic'
                      ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-lg shadow-blue-500/20'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Sparkles size={16} />
                  AI Agent
                </button>
                <button
                  onClick={() => setExtractionMethod('classic')}
                  className={`flex-1 px-4 py-3 rounded-md font-medium text-sm transition-all flex items-center justify-center gap-2 ${
                    extractionMethod === 'classic'
                      ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-lg shadow-blue-500/20'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Grid3x3 size={16} />
                  Manual
                </button>
              </div>

              {/* Mode Description */}
              <div className="bg-slate-900/30 border border-slate-800 rounded-lg p-4">
                {extractionMethod === 'agentic' ? (
                  <div className="flex items-start gap-3">
                    <Brain className="text-blue-400 flex-shrink-0 mt-0.5" size={18} />
                    <div>
                      <p className="text-sm font-medium text-slate-200 mb-1">AI-Powered Detection</p>
                      <p className="text-xs text-slate-400">AI agents analyze your document to automatically identify and extract structured data</p>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-start gap-3">
                    <Grid3x3 className="text-slate-400 flex-shrink-0 mt-0.5" size={18} />
                    <div>
                      <p className="text-sm font-medium text-slate-200 mb-1">Manual Precision</p>
                      <p className="text-xs text-slate-400">Draw regions on the document to specify exactly which areas to extract</p>
                    </div>
                  </div>
                )}
              </div>

              {/* Regions List (Classic Mode) */}
              {extractionMethod === 'classic' && (
                <div className="bg-slate-900/50 border border-slate-800 rounded-lg">
                  <div className="px-4 py-3 border-b border-slate-800">
                    <h3 className="text-sm font-semibold text-slate-200">Selected Regions</h3>
                  </div>
                  <div className="p-3">
                    {regions.length === 0 ? (
                      <div className="text-center py-8">
                        <Grid3x3 className="mx-auto text-slate-700 mb-2" size={32} />
                        <p className="text-xs text-slate-500">Click and drag on the PDF to select regions</p>
                      </div>
                    ) : (
                      <div className="space-y-2 max-h-[240px] overflow-y-auto">
                        {regions.map((region, idx) => (
                          <div key={idx} className="bg-slate-800/50 border border-slate-700 rounded-lg p-3">
                            <div className="flex items-start justify-between mb-2">
                              <span className="text-xs font-medium text-slate-300">Region {idx + 1}</span>
                              <button
                                onClick={() => handleRegionRemove(idx)}
                                className="text-slate-500 hover:text-red-400 transition"
                              >
                                <X size={14} />
                              </button>
                            </div>
                            <input
                              type="text"
                              placeholder="Label (optional)"
                              value={region.label || ''}
                              onChange={(e) => handleLabelChange(idx, e.target.value)}
                              className="w-full px-2 py-1.5 text-xs bg-slate-900 border border-slate-700 rounded text-slate-200 placeholder-slate-500 focus:border-blue-500 focus:outline-none"
                            />
                            <p className="text-xs text-slate-500 mt-1.5">Page {region.page}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Export Settings */}
              <div className="bg-slate-900/50 border border-slate-800 rounded-lg">
                <div className="px-4 py-3 border-b border-slate-800">
                  <h3 className="text-sm font-semibold text-slate-200">Export Settings</h3>
                </div>
                <div className="p-4 space-y-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-2">Output Format</label>
                    <div className="grid grid-cols-3 gap-2">
                      {(['csv', 'tsv', 'json'] as const).map((format) => (
                        <button
                          key={format}
                          onClick={() => setOutputFormat(format)}
                          className={`px-3 py-2 text-xs font-medium rounded-md border transition ${
                            outputFormat === format
                              ? 'border-blue-500 bg-blue-500/10 text-blue-400'
                              : 'border-slate-700 text-slate-400 hover:border-slate-600 hover:text-slate-300'
                          }`}
                        >
                          {format.toUpperCase()}
                        </button>
                      ))}
                    </div>
                  </div>

                  <button
                    onClick={handleExtract}
                    disabled={(extractionMethod === 'classic' && regions.length === 0) || isProcessing || !pdfId}
                    className="w-full px-4 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-lg font-medium text-sm disabled:from-slate-700 disabled:to-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed transition shadow-lg shadow-blue-500/20 disabled:shadow-none flex items-center justify-center gap-2"
                  >
                    {isProcessing ? (
                      <>
                        <Loader2 className="animate-spin" size={16} />
                        Starting...
                      </>
                    ) : (
                      <>
                        <Play size={16} />
                        Extract Data
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Job Status */}
              {job && (
                <div className="bg-slate-900/50 border border-slate-800 rounded-lg">
                  <div className="px-4 py-3 border-b border-slate-800">
                    <h3 className="text-sm font-semibold text-slate-200">Processing Status</h3>
                  </div>
                  <div className="p-4">
                    {job.status === 'pending' && (
                      <div className="flex items-center gap-3">
                        <Loader2 className="text-blue-500 animate-spin" size={20} />
                        <span className="text-sm text-slate-300">Queued...</span>
                      </div>
                    )}

                    {job.status === 'processing' && extractionMethod === 'agentic' && (
                      <AgenticProcessingFeedback job={job} />
                    )}

                    {job.status === 'processing' && extractionMethod === 'classic' && (
                      <div className="space-y-3">
                        <div className="flex items-center gap-3">
                          <Loader2 className="text-blue-500 animate-spin" size={20} />
                          <div className="flex-1">
                            <p className="text-sm text-slate-300">Extracting regions...</p>
                            <div className="flex items-center gap-2 mt-1">
                              <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                                <div 
                                  className="h-full bg-blue-500 rounded-full transition-all duration-500"
                                  style={{ width: `${job.progress || 0}%` }}
                                />
                              </div>
                              <span className="text-xs text-slate-400 tabular-nums">{Math.round(job.progress || 0)}%</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {job.status === 'completed' && (
                      <div className="space-y-3">
                        <div className="flex items-center gap-3 p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
                          <div className="w-8 h-8 bg-emerald-500 rounded-full flex items-center justify-center">
                            <Check className="text-white" size={16} />
                          </div>
                          <div>
                            <p className="text-sm font-medium text-emerald-400">Extraction Complete</p>
                            <p className="text-xs text-emerald-300/70">Your data is ready to download</p>
                          </div>
                        </div>

                        <button
                          onClick={handleDownload}
                          className="w-full px-4 py-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg font-medium text-sm transition shadow-lg shadow-emerald-500/20 flex items-center justify-center gap-2"
                        >
                          <Download size={16} />
                          Download {outputFormat.toUpperCase()}
                        </button>
                      </div>
                    )}

                    {job.status === 'failed' && (
                      <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                        <div className="flex items-center gap-2 mb-1">
                          <AlertCircle className="text-red-400" size={16} />
                          <p className="text-sm font-medium text-red-400">Extraction Failed</p>
                        </div>
                        {job.error_message && <p className="text-xs text-red-300/70">{job.error_message}</p>}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}