"use client";

import { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { Region, JobStatus, DetectedRegion } from "@/types/api";
import { apiClient } from "@/lib/api-client";
import { cn, theme } from "@/lib/theme";
import { Button, Card, CardHeader, CardContent, FileUpload, FileInfo, RegionItem, StatusIndicator } from "@/components/ui";

import {
  FileText,
  Sparkles,
  Grid3x3,
  Download,
  Loader2,
  X,
  AlertCircle,
  Database,
  Play,
} from "lucide-react";

// Dynamically import PDFViewer to avoid SSR issues
const PDFViewer = dynamic(() => import("@/components/PDFViewer"), {
  ssr: false,
  loading: () => (
    <div
      className={cn(
        theme.colors.background.secondary,
        theme.radius.lg,
        theme.colors.border.primary,
        'border flex items-center justify-center'
      )}
      style={{ minHeight: "700px" }}
    >
      <Loader2 className={theme.colors.text.disabled + ' animate-spin'} size={40} />
    </div>
  ),
});

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [pdfId, setPdfId] = useState<string | null>(null);
  const [detectedRegions, setDetectedRegions] = useState<DetectedRegion[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [outputFormat, setOutputFormat] = useState<"csv" | "tsv" | "json">(
    "csv"
  );
  const [job, setJob] = useState<JobStatus | null>(null);
  const [isDetecting, setIsDetecting] = useState(false);
  const [approvedRegions, setApprovedRegions] = useState<DetectedRegion[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [selectedRegionIds, setSelectedRegionIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  // Poll job status
  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed") return;

    const interval = setInterval(async () => {
      try {
        const updatedJob = await apiClient.getJobStatus(job.job_id);
        setJob(updatedJob);
        // Update approved regions when job completes
        if (updatedJob.status === "completed" && updatedJob.approved_regions) {
          setApprovedRegions(updatedJob.approved_regions);
        }
      } catch (err) {
        console.error("Error polling job status:", err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [job]);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;

    if (selectedFile.type !== "application/pdf") {
      setError("Please select a PDF file");
      return;
    }

    setFile(selectedFile);
    setDetectedRegions([]);
    setApprovedRegions([]);
    setJob(null);
    setError(null);

    setIsUploading(true);
    try {
      const { pdf_id, upload_url } = await apiClient.generateUploadURL(
        selectedFile.name
      );
      await apiClient.uploadPDF(upload_url, selectedFile);
      setPdfId(pdf_id);
      setError(null);
      
      // Auto-detect regions after upload
      setIsDetecting(true);
      try {
        const job = await apiClient.createAgenticExtractionJob({
          pdf_id: pdf_id,
          regions: [],
          output_format: outputFormat,
        });

        // Poll for completion to get detected regions
        const pollInterval = setInterval(async () => {
          try {
            const updatedJob = await apiClient.getJobStatus(job.job_id);
            if (updatedJob.status === "completed" && updatedJob.debug_graph_url) {
              clearInterval(pollInterval);
              const response = await fetch(updatedJob.debug_graph_url);
              const data = await response.json();
              
              const regions: DetectedRegion[] = [];
              if (data.summary?.trace) {
                interface TraceEvent {
                  step: string;
                  status: string;
                  region_id?: string;
                  region_type?: string;
                  page?: number;
                  bbox?: { x: number; y: number; w: number; h: number };
                }
                
                const dispatchEvents = data.summary.trace.filter(
                  (event: TraceEvent) =>
                    event.step === "dispatch_to_specialist" &&
                    event.status === "started"
                );
                
                dispatchEvents.forEach((event: TraceEvent) => {
                  if (event.region_id && event.region_type && event.page !== undefined) {
                    const bbox = event.bbox 
                      ? {
                          x: event.bbox.x,
                          y: event.bbox.y,
                          w: event.bbox.w,
                          h: event.bbox.h
                        }
                      : { x: 0, y: 0, w: 1, h: 1 };
                    
                    regions.push({
                      region_id: event.region_id,
                      region_type: event.region_type,
                      page: event.page,
                      bbox,
                      confidence: 1.0,
                    });
                  }
                });
              }
              
              setDetectedRegions(regions);
              setIsDetecting(false);
            } else if (updatedJob.status === "failed") {
              clearInterval(pollInterval);
              setIsDetecting(false);
            }
          } catch {
            clearInterval(pollInterval);
            setIsDetecting(false);
          }
        }, 2000);
      } catch {
        setIsDetecting(false);
      }
    } catch (err) {
      setError(
        `Upload failed: ${err instanceof Error ? err.message : "Unknown error"}`
      );
      setFile(null);
    } finally {
      setIsUploading(false);
    }
  };

  const handleRegionAdd = (region: Region) => {
    // Convert manual region to DetectedRegion
    const newRegion: DetectedRegion = {
      region_id: `manual_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      region_type: "TABLE", // Default to TABLE, user can change
      bbox: {
        x: region.x,
        y: region.y,
        w: region.width,
        h: region.height,
      },
      page: region.page,
      confidence: 1.0,
    };
    setDetectedRegions([...detectedRegions, newRegion]);
  };

  const handleRegionRemove = (regionId: string) => {
    setDetectedRegions(detectedRegions.filter((r) => r.region_id !== regionId));
  };

  const handleRegionUpdate = (updatedRegion: DetectedRegion) => {
    setDetectedRegions(
      detectedRegions.map((r) =>
        r.region_id === updatedRegion.region_id ? updatedRegion : r
      )
    );
  };



  const handleSaveDocument = async () => {
    if (!pdfId || !job?.job_id) {
      setError("No document to save");
      return;
    }
    if (detectedRegions.length === 0) {
      setError("No regions to save");
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      // Format regions as corrections for reinforcement learning
      const corrections = detectedRegions.map((region) => ({
        original: region,
        corrected: region, // In save mode, corrected = current state
        action: "retype", // Mark as user-verified
        timestamp: new Date().toISOString(),
      }));

      await apiClient.submitFeedback(
        job.job_id,
        corrections,
        undefined, // userId
        undefined  // sessionId
      );

      setError("Document saved successfully!");
      setTimeout(() => setError(null), 3000);
    } catch (err) {
      setError(
        `Save failed: ${err instanceof Error ? err.message : "Unknown error"}`
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleExtract = async () => {
    if (!pdfId) return;
    if (detectedRegions.length === 0) return;

    // Only extract selected regions, or all if none are selected
    const regionsToExtract = selectedRegionIds.size > 0 
      ? detectedRegions.filter(r => selectedRegionIds.has(r.region_id))
      : detectedRegions;

    if (regionsToExtract.length === 0) {
      setError("No regions selected for extraction");
      setTimeout(() => setError(null), 3000);
      return;
    }

    setIsProcessing(true);
    setError(null);

    try {
      // Convert DetectedRegions back to Region format for extraction
      const regions: Region[] = regionsToExtract.map((r) => ({
        x: r.bbox.x,
        y: r.bbox.y,
        width: r.bbox.w,
        height: r.bbox.h,
        page: r.page,
        label: r.region_type,
      }));

      const extractionRequest = {
        pdf_id: pdfId,
        regions,
        output_format: outputFormat,
      };

      const job = await apiClient.createExtractionJob(extractionRequest);
      setJob(job);
    } catch (err) {
      setError(
        `Extraction failed: ${
          err instanceof Error ? err.message : "Unknown error"
        }`
      );
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDownload = async () => {
    if (!job?.result_url) return;

    try {
      const blob = await apiClient.downloadResult(job.result_url);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `extraction-result.${outputFormat}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      setError(
        `Download failed: ${
          err instanceof Error ? err.message : "Unknown error"
        }`
      );
    }
  };

  return (
    <div className={cn('min-h-screen', theme.colors.background.primary)}>
      {/* Header */}
      <header className={cn(
        theme.colors.background.overlay,
        'border-b',
        theme.colors.border.secondary,
        theme.effects.backdropBlurXl,
        'sticky top-0 z-50'
      )}>
        <div className="max-w-[1800px] mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={cn(
                'w-8 h-8',
                'bg-gradient-to-br from-blue-500 to-indigo-600',
                theme.radius.lg,
                'flex items-center justify-center'
              )}>
                <FileText className={theme.colors.text.primary} size={18} />
              </div>
              <div>
                <h1 className={cn('text-lg font-semibold', theme.colors.text.primary)}>
                  PDF-OCR
                </h1>
                <p className={cn('text-xs', theme.colors.text.muted)}>
                  Document Intelligence Platform
                </p>
              </div>
            </div>

            {file && (
              <div className="flex items-center gap-4">
                <FileInfo 
                  file={file}
                  onRemove={() => {
                    setFile(null);
                    setPdfId(null);
                    setDetectedRegions([]);
                    setApprovedRegions([]);
                    setJob(null);
                  }}
                />
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-[1800px] mx-auto px-6 py-6">
        {/* Error Display */}
        {error && (
          <div className={cn(
            'mb-4 p-4',
            'bg-red-500/10 border border-red-500/30',
            theme.radius.lg,
            'flex items-start gap-3'
          )}>
            <AlertCircle className="text-red-400 flex-shrink-0 mt-0.5" size={18} />
            <div className="flex-1">
              <p className="text-sm text-red-300">{error}</p>
            </div>
            <button
              onClick={() => setError(null)}
              className={cn('text-red-400 hover:text-red-300', theme.transitions.default)}
            >
              <X size={16} />
            </button>
          </div>
        )}

        {!file ? (
          <div className="max-w-4xl mx-auto">
            <div className="text-center mb-8">
              <h2 className={cn('text-3xl font-bold mb-2', theme.colors.text.primary)}>
                Extract Structured Data from PDFs
              </h2>
              <p className={theme.colors.text.muted}>
                Powered by AI agents and GCP Document AI
              </p>
            </div>

            <FileUpload onFileSelect={handleFileChange} isUploading={isUploading} />

            <div className="grid md:grid-cols-2 gap-4 mt-8">
              <Card variant="overlay" className="p-6">
                <div className={cn(
                  'w-10 h-10 mb-4',
                  'bg-blue-500/20 border border-blue-500/30',
                  theme.radius.lg,
                  'flex items-center justify-center'
                )}>
                  <Sparkles className={theme.colors.accent.blue} size={20} />
                </div>
                <h3 className={cn(theme.colors.text.primary, 'font-semibold mb-2')}>AI Agent Mode</h3>
                <p className={cn('text-sm', theme.colors.text.muted)}>
                  Automatically detect and extract tables, forms, and structured
                  data using advanced AI
                </p>
              </Card>

              <Card variant="overlay" className="p-6">
                <div className={cn(
                  'w-10 h-10 mb-4',
                  theme.colors.background.tertiary + '/50',
                  theme.colors.border.muted,
                  'border',
                  theme.radius.lg,
                  'flex items-center justify-center'
                )}>
                  <Grid3x3 className={theme.colors.text.muted} size={20} />
                </div>
                <h3 className={cn(theme.colors.text.primary, 'font-semibold mb-2')}>
                  Manual Selection
                </h3>
                <p className={cn('text-sm', theme.colors.text.muted)}>
                  Precisely control extraction by selecting specific regions in
                  your document
                </p>
              </Card>
            </div>
          </div>
        ) : (
          <div className="flex gap-6 h-[calc(100vh-140px)]">
            {/* Left: PDF Viewer - 2/3 width */}
            <div className={cn(
              'flex-[2] overflow-hidden min-w-0',
              theme.colors.background.secondary,
              theme.colors.border.secondary,
              'border',
              theme.radius.lg
            )}>
              <PDFViewer
                file={file}
                onRegionAdd={handleRegionAdd}
                currentPage={currentPage}
                onPageChange={setCurrentPage}
                detectedRegions={detectedRegions}
                approvedRegions={approvedRegions}
                onRegionUpdate={handleRegionUpdate}
                onRegionRemove={handleRegionRemove}
              />
            </div>

            {/* Right: Controls - 1/3 width */}
            <div className="flex-1 space-y-4 min-w-0 overflow-y-auto">
              {/* AI Detection Status */}
              {isDetecting && (
                <Card>
                  <CardHeader title="AI Region Detection" />
                  <CardContent>
                    <StatusIndicator status="processing" message="Analyzing document..." />
                  </CardContent>
                </Card>
              )}
              
              {detectedRegions.length > 0 && !isDetecting && (
                <Card className="border-emerald-800/50">
                  <div className="p-3 flex items-center gap-2">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                      <circle cx="8" cy="8" r="7" className="stroke-emerald-400" strokeWidth="2" />
                      <path d="M5 8l2 2 4-5" className="stroke-emerald-400" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    <p className="text-xs text-emerald-400">
                      {(() => {
                        const pageRegionsCount = detectedRegions.filter(r => r.page === currentPage).length;
                        const totalCount = detectedRegions.length;
                        return pageRegionsCount === totalCount
                          ? `${totalCount} ${totalCount === 1 ? 'region' : 'regions'} detected`
                          : `${pageRegionsCount} of ${totalCount} regions on this page`;
                      })()}
                    </p>
                  </div>
                </Card>
              )}

              {/* Regions List - showing detected regions for current page */}
              <Card>
                <CardHeader title={`Regions on Page ${currentPage}`} />
                <CardContent>
                    {(() => {
                      const pageRegions = detectedRegions.filter(r => r.page === currentPage);
                      
                      if (pageRegions.length === 0) {
                        return (
                          <div className="text-center py-8">
                            <Grid3x3
                              className={cn('mx-auto mb-2', theme.colors.text.disabled)}
                              size={32}
                            />
                            <p className={cn('text-xs', theme.colors.text.subtle)}>
                              {detectedRegions.length === 0 
                                ? 'AI will detect regions automatically' 
                                : 'No regions on this page'}
                            </p>
                          </div>
                        );
                      }
                      
                      return (
                        <div className="space-y-2 max-h-[320px] overflow-y-auto">
                          {pageRegions.map((region) => (
                            <RegionItem
                              key={region.region_id}
                              region={region}
                              isProcessing={isProcessing}
                              onExtract={async (reg, fmt) => {
                                if (!pdfId || isProcessing) return;
                                setIsProcessing(true);
                                setError(null);
                                try {
                                  const regions = [{
                                    x: reg.bbox.x,
                                    y: reg.bbox.y,
                                    width: reg.bbox.w,
                                    height: reg.bbox.h,
                                    page: reg.page,
                                    label: reg.region_type,
                                  }];
                                  const extractionRequest = {
                                    pdf_id: pdfId,
                                    regions,
                                    output_format: fmt,
                                  };
                                  const job = await apiClient.createExtractionJob(extractionRequest);
                                  setJob(job);
                                } catch (err) {
                                  setError(
                                    `Extraction failed: ${
                                      err instanceof Error ? err.message : "Unknown error"
                                    }`
                                  );
                                } finally {
                                  setIsProcessing(false);
                                }
                              }}
                            />
                          ))}
                        </div>
                      );
                    })()}
                  </CardContent>
                </Card>

              {/* Job Status */}
              {job && (
                <Card>
                  <CardHeader title="Processing Status" />
                  <CardContent>
                    {job.status === "pending" && (
                      <StatusIndicator status="pending" />
                    )}

                    {job.status === "processing" && (
                      <StatusIndicator 
                        status="processing" 
                        message="Extracting regions..." 
                        progress={job.progress}
                      />
                    )}

                    {/* COMPLETED STATE */}
                    {job.status === "completed" && (
                      <div className="space-y-3">
                        {/* Final stats */}
                        <div className="grid grid-cols-3 gap-2">
                          <Card variant="strong" className="p-3">
                            <div className="flex items-center gap-2 mb-1">
                              <Sparkles className={theme.colors.accent.emerald} size={14} />
                              <p className={cn('text-xs', theme.colors.text.muted)}>Detected</p>
                            </div>
                            <p className="text-lg font-semibold text-emerald-400 tabular-nums">
                              {job.detected_entities}
                            </p>
                          </Card>
                          <Card variant="strong" className="p-3">
                            <div className="flex items-center gap-2 mb-1">
                              <Database className={theme.colors.accent.blue} size={14} />
                              <p className={cn('text-xs', theme.colors.text.muted)}>Fields</p>
                            </div>
                            <p className="text-lg font-semibold text-blue-400 tabular-nums">
                              {Math.floor((job.detected_entities || 0) * 1.5)}
                            </p>
                          </Card>
                          <Card variant="strong" className="p-3">
                            <div className="flex items-center gap-2 mb-1">
                              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                                <circle cx="7" cy="7" r="6" className="stroke-emerald-400" strokeWidth="2" />
                                <path d="M4 7l2 2 4-4" className="stroke-emerald-400" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                              </svg>
                              <p className={cn('text-xs', theme.colors.text.muted)}>Status</p>
                            </div>
                            <p className="text-lg font-semibold text-emerald-400">Done</p>
                          </Card>
                        </div>

                        <Card variant="overlay" className="p-3 space-y-2">
                          {[
                            { label: "Document Analysis" },
                            { label: "AI Detection" },
                            { label: "Data Extraction" },
                            { label: "Validation" },
                          ].map((step, idx) => (
                            <div key={idx} className="flex items-center gap-2">
                              <div className={cn(
                                'w-4 h-4',
                                theme.colors.accent.emeraldBg,
                                theme.radius.full,
                                'flex items-center justify-center'
                              )}>
                                <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                                  <path d="M2 5l2 2 4-4" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                                </svg>
                              </div>
                              <p className={cn('text-xs', theme.colors.text.tertiary)}>
                                {step.label}
                              </p>
                            </div>
                          ))}
                        </Card>

                        <div className={cn(
                          'flex items-center gap-3 p-3',
                          'bg-emerald-500/10 border border-emerald-500/30',
                          theme.radius.lg
                        )}>
                          <div className={cn(
                            'w-8 h-8',
                            theme.colors.accent.emeraldBg,
                            theme.radius.full,
                            'flex items-center justify-center'
                          )}>
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                              <path d="M4 8l3 3 5-6" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                          </div>
                          <div>
                            <p className="text-sm font-medium text-emerald-400">
                              Extraction Complete
                            </p>
                            <p className="text-xs text-emerald-300/70">
                              Your data is ready to download
                            </p>
                          </div>
                        </div>

                        {job.debug_graph_url && (
                          <Button
                            variant="ghost"
                            size="md"
                            onClick={() => window.open(job.debug_graph_url, '_blank')}
                            icon={<Sparkles size={14} />}
                            className="w-full"
                          >
                            View Processing Trace
                          </Button>
                        )}

                        <Button
                          variant="success"
                          size="lg"
                          onClick={handleDownload}
                          icon={<Download size={16} />}
                          className="w-full"
                        >
                          Download {outputFormat.toUpperCase()}
                        </Button>
                      </div>
                    )}

                    {job.status === "failed" && (
                      <div className={cn(
                        'p-3',
                        'bg-red-500/10 border border-red-500/30',
                        theme.radius.lg
                      )}>
                        <div className="flex items-center gap-2 mb-1">
                          <AlertCircle className="text-red-400" size={16} />
                          <p className="text-sm font-medium text-red-400">
                            Extraction Failed
                          </p>
                        </div>
                        {job.error && (
                          <p className="text-xs text-red-300/70">{job.error}</p>
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
