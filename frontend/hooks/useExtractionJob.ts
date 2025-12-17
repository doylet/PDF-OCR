import { useState, useEffect, useCallback } from 'react';
import { JobStatus, DetectedRegion } from '@/types/api';
import { apiClient } from '@/lib/api-client';

interface UseExtractionJobResult {
  job: JobStatus | null;
  isProcessing: boolean;
  extractRegion: (pdfId: string, region: DetectedRegion, format: 'csv' | 'tsv' | 'json') => Promise<void>;
  downloadResult: () => Promise<void>;
  clearJob: () => void;
}

export const useExtractionJob = (
  onError: (error: string) => void,
  onApprovedRegions?: (regions: DetectedRegion[]) => void
): UseExtractionJobResult => {
  const [job, setJob] = useState<JobStatus | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  // Poll job status
  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed") return;

    const interval = setInterval(async () => {
      try {
        const updatedJob = await apiClient.getJobStatus(job.job_id);
        setJob(updatedJob);
        
        if (updatedJob.status === "completed" && updatedJob.approved_regions) {
          onApprovedRegions?.(updatedJob.approved_regions);
        }
      } catch (err) {
        console.error("Error polling job status:", err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [job, onApprovedRegions]);

  const extractRegion = useCallback(async (
    pdfId: string,
    region: DetectedRegion,
    format: 'csv' | 'tsv' | 'json'
  ) => {
    setIsProcessing(true);
    
    try {
      const regions = [{
        x: region.bbox.x,
        y: region.bbox.y,
        width: region.bbox.w,
        height: region.bbox.h,
        page: region.page,
        label: region.region_type,
      }];

      const extractionRequest = {
        pdf_id: pdfId,
        regions,
        output_format: format,
      };

      const newJob = await apiClient.createExtractionJob(extractionRequest);
      setJob(newJob);
    } catch (err) {
      onError(`Extraction failed: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      setIsProcessing(false);
    }
  }, [onError]);

  const downloadResult = useCallback(async () => {
    if (!job?.result_url) return;

    try {
      const blob = await apiClient.downloadResult(job.result_url);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const format = job.output_format || "csv";
      a.download = `extraction-result.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      onError(`Download failed: ${err instanceof Error ? err.message : "Unknown error"}`);
    }
  }, [job, onError]);

  const clearJob = useCallback(() => {
    setJob(null);
    setIsProcessing(false);
  }, []);

  return {
    job,
    isProcessing,
    extractRegion,
    downloadResult,
    clearJob,
  };
};
