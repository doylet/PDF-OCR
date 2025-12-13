export interface Region {
  x: number;
  y: number;
  width: number;
  height: number;
  page: number;
  label?: string;
}

export interface ExtractionRequest {
  pdf_id: string;
  regions: Region[];
  output_format: 'csv' | 'tsv' | 'json';
}

export interface JobStatus {
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  created_at: string;
  updated_at: string;
  pdf_id: string;
  regions_count: number;
  result_url?: string;
  error_message?: string;
}

export interface UploadResponse {
  pdf_id: string;
  upload_url: string;
  file_name: string;
}
