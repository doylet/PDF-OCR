import { ExtractionRequest, JobStatus, UploadResponse } from '@/types/api';

// Get API configuration from environment variables
// In production, these MUST be set at build time via build args
const getAPIURL = (): string => {
  const url = process.env.NEXT_PUBLIC_API_URL;
  if (!url) {
    throw new Error(
      'NEXT_PUBLIC_API_URL is not configured. ' +
      'For local development, create a .env.local file with NEXT_PUBLIC_API_URL=http://localhost:8000. ' +
      'For production, ensure the environment variable is set during build.'
    );
  }
  return url;
};

const API_URL = getAPIURL();
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || 'dev-api-key-change-in-production';

class APIClient {
  private baseURL: string;
  private apiKey: string;

  constructor() {
    this.baseURL = API_URL;
    this.apiKey = API_KEY;
  }

  private async fetch(endpoint: string, options: RequestInit = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const headers = {
      'X-API-Key': this.apiKey,
      ...options.headers,
    };

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  async generateUploadURL(fileName: string): Promise<UploadResponse> {
    return this.fetch(`/api/upload/generate-url?file_name=${encodeURIComponent(fileName)}`, {
      method: 'POST',
    });
  }

  async uploadPDF(uploadUrl: string, file: File): Promise<void> {
    const response = await fetch(uploadUrl, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/pdf',
      },
      body: file,
    });

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.statusText}`);
    }
  }

  async createExtractionJob(request: ExtractionRequest): Promise<JobStatus> {
    return this.fetch('/api/extract/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
  }

  async createAgenticExtractionJob(request: ExtractionRequest): Promise<JobStatus> {
    return this.fetch('/api/extract/agentic', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
  }

  async getJobStatus(jobId: string): Promise<JobStatus> {
    return this.fetch(`/api/extract/${jobId}`);
  }

  async downloadResult(resultUrl: string): Promise<Blob> {
    const response = await fetch(resultUrl);
    if (!response.ok) {
      throw new Error(`Download failed: ${response.statusText}`);
    }
    return response.blob();
  }

  async submitFeedback(jobId: string, corrections: any[], userId?: string, sessionId?: string): Promise<any> {
    return this.fetch('/api/v1/feedback/corrections', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        job_id: jobId,
        corrections,
        user_id: userId,
        session_id: sessionId,
      }),
    });
  }

  async getFeedback(jobId: string): Promise<any> {
    return this.fetch(`/api/v1/feedback/corrections/${jobId}`);
  }

  async getFeedbackStats(): Promise<any> {
    return this.fetch('/api/v1/feedback/stats');
  }
}

export const apiClient = new APIClient();
