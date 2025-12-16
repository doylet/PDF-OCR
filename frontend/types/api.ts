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

export interface UploadResponse {
  pdf_id: string;
  upload_url: string;
  file_name: string;
}

export interface DetectedRegion {
  region_id: string;
  page: number;
  bbox: {
    x: number;
    y: number;
    w: number;
    h: number;
  };
  region_type: string;
  confidence: number;
}

export interface JobStatus {
  job_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  created_at: string;
  updated_at: string;
  pdf_id: string;
  regions_count: number;
  error_message?: string;
  debug_graph_url?: string;
  result_url?: string;
  error?: string;
  progress?: number;
  detected_entities?: number;
  processing_step?: string;
  approved_regions?: DetectedRegion[];
}
