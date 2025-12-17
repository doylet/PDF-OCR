"use client";

import { useState } from "react";
import { cn, theme } from "@/lib/theme";
import { DetectedRegion } from "@/types/api";
import { FileInfo } from "@/components/processing";
import { WelcomeScreen, PDFWorkspace } from "@/components/pages";
import { usePDFUpload, useRegionManagement, useExtractionJob } from "@/hooks";
import { FileText, X, AlertCircle } from "lucide-react";

export default function Home() {
  const [error, setError] = useState<string | null>(null);

  const {
    detectedRegions,
    approvedRegions,
    currentPage,
    setCurrentPage,
    addRegion,
    removeRegion,
    updateRegion,
    setDetectedRegions,
    clearRegions,
  } = useRegionManagement();

  const {
    file,
    pdfId,
    isUploading,
    isDetecting,
    error: uploadError,
    uploadFile,
    clearFile,
    setError: setUploadError,
  } = usePDFUpload(setDetectedRegions);

  const {
    job,
    isProcessing,
    extractRegion,
    downloadResult,
    clearJob,
  } = useExtractionJob(setError);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;

    clearRegions();
    clearJob();
    setError(null);
    await uploadFile(selectedFile);
  };

  const handleFileRemove = () => {
    clearFile();
    clearRegions();
    clearJob();
    setError(null);
  };

  const handleExtract = async (region: DetectedRegion, format: 'csv' | 'tsv' | 'json') => {
    if (!pdfId) return;
    await extractRegion(pdfId, region, format);
  };

  const displayError = error || uploadError;

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
                <FileText className={theme.colors.foreground.primary} size={18} />
              </div>
              <div>
                <h1 className={cn('text-lg font-semibold', theme.colors.foreground.primary)}>
                  PDF-OCR
                </h1>
                <p className={cn('text-xs', theme.colors.foreground.muted)}>
                  Document Intelligence Platform
                </p>
              </div>
            </div>

            {file && (
              <div className="flex items-center gap-4">
                <FileInfo file={file} onRemove={handleFileRemove} />
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-[1800px] mx-auto px-6 py-6">
        {/* Error Display */}
        {displayError && (
          <div className={cn(
            'mb-4 p-4',
            'bg-red-500/10 border border-red-500/30',
            theme.radius.lg,
            'flex items-start gap-3'
          )}>
            <AlertCircle className="text-red-400 flex-shrink-0 mt-0.5" size={18} />
            <div className="flex-1">
              <p className="text-sm text-red-300">{displayError}</p>
            </div>
            <button
              onClick={() => {
                setError(null);
                setUploadError(null);
              }}
              className={cn('text-red-400 hover:text-red-300', theme.transitions.default)}
            >
              <X size={16} />
            </button>
          </div>
        )}

        {!file ? (
          <WelcomeScreen onFileSelect={handleFileChange} isUploading={isUploading} />
        ) : (
          <PDFWorkspace
            file={file}
            currentPage={currentPage}
            onPageChange={setCurrentPage}
            detectedRegions={detectedRegions}
            approvedRegions={approvedRegions}
            onRegionAdd={addRegion}
            onRegionUpdate={updateRegion}
            onRegionRemove={removeRegion}
            isDetecting={isDetecting}
            isProcessing={isProcessing}
            job={job}
            onExtract={handleExtract}
            onDownload={downloadResult}
          />
        )}
      </main>
    </div>
  );
}
