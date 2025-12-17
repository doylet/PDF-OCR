import { useState, useCallback } from 'react';
import { apiClient } from '@/lib/api-client';
import { DetectedRegion } from '@/types/api';

interface TraceEvent {
  step: string;
  status: string;
  region_id?: string;
  region_type?: string;
  page?: number;
  bbox?: {
    x: number;
    y: number;
    w: number;
    h: number;
  };
}

interface UsePDFUploadResult {
  file: File | null;
  pdfId: string | null;
  isUploading: boolean;
  isDetecting: boolean;
  error: string | null;
  uploadFile: (file: File) => Promise<void>;
  clearFile: () => void;
  setError: (error: string | null) => void;
}

export const usePDFUpload = (
  onRegionsDetected: (regions: DetectedRegion[]) => void
): UsePDFUploadResult => {
  const [file, setFile] = useState<File | null>(null);
  const [pdfId, setPdfId] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isDetecting, setIsDetecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const uploadFile = useCallback(async (selectedFile: File) => {
    if (selectedFile.type !== "application/pdf") {
      setError("Please select a PDF file");
      return;
    }

    setFile(selectedFile);
    setError(null);
    setIsUploading(true);

    try {
      const { pdf_id, upload_url } = await apiClient.generateUploadURL(selectedFile.name);
      await apiClient.uploadPDF(upload_url, selectedFile);
      setPdfId(pdf_id);

      // Auto-detect regions after upload
      setIsDetecting(true);
      const job = await apiClient.createAgenticExtractionJob({
        pdf_id,
        regions: [],
        output_format: "csv",
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
              const dispatchEvents = data.summary.trace.filter(
                (event: TraceEvent) =>
                  event.step === "dispatch_to_specialist" &&
                  event.status === "started"
              );

              dispatchEvents.forEach((event: TraceEvent) => {
                if (event.region_id && event.region_type && event.page !== undefined) {
                  regions.push({
                    region_id: event.region_id,
                    region_type: event.region_type,
                    page: event.page,
                    bbox: event.bbox || { x: 0, y: 0, w: 1, h: 1 },
                    confidence: 1.0,
                  });
                }
              });
            }

            onRegionsDetected(regions);
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
    } catch (err) {
      setError(`Upload failed: ${err instanceof Error ? err.message : "Unknown error"}`);
      setFile(null);
    } finally {
      setIsUploading(false);
    }
  }, [onRegionsDetected]);

  const clearFile = useCallback(() => {
    setFile(null);
    setPdfId(null);
    setError(null);
  }, []);

  return {
    file,
    pdfId,
    isUploading,
    isDetecting,
    error,
    uploadFile,
    clearFile,
    setError,
  };
};
