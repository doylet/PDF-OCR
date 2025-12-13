'use client';

import { JobStatus } from '@/types/api';
import { CheckCircle, Clock, AlertCircle, Loader2 } from 'lucide-react';

interface JobStatusDisplayProps {
  job: JobStatus | null;
  onDownload: () => void;
}

export default function JobStatusDisplay({ job, onDownload }: JobStatusDisplayProps) {
  if (!job) return null;

  const getStatusIcon = () => {
    switch (job.status) {
      case 'queued':
        return <Clock className="text-yellow-500" size={24} />;
      case 'processing':
        return <Loader2 className="text-blue-500 animate-spin" size={24} />;
      case 'completed':
        return <CheckCircle className="text-green-500" size={24} />;
      case 'failed':
        return <AlertCircle className="text-red-500" size={24} />;
    }
  };

  const getStatusText = () => {
    switch (job.status) {
      case 'queued':
        return 'Job queued for processing...';
      case 'processing':
        return 'Processing regions...';
      case 'completed':
        return 'Extraction completed!';
      case 'failed':
        return 'Extraction failed';
    }
  };

  const getStatusColor = () => {
    switch (job.status) {
      case 'queued':
        return 'bg-yellow-50 border-yellow-200';
      case 'processing':
        return 'bg-blue-50 border-blue-200';
      case 'completed':
        return 'bg-green-50 border-green-200';
      case 'failed':
        return 'bg-red-50 border-red-200';
    }
  };

  return (
    <div className={`p-4 rounded-lg border-2 ${getStatusColor()}`}>
      <div className="flex items-center space-x-3 mb-2">
        {getStatusIcon()}
        <div>
          <h3 className="font-semibold">{getStatusText()}</h3>
          <p className="text-sm text-gray-600">Job ID: {job.job_id.slice(0, 8)}...</p>
        </div>
      </div>

      <div className="text-sm text-gray-600 space-y-1">
        <p>Regions processed: {job.regions_count}</p>
        <p>Created: {new Date(job.created_at).toLocaleString()}</p>
        {job.updated_at && (
          <p>Updated: {new Date(job.updated_at).toLocaleString()}</p>
        )}
      </div>

      {job.status === 'completed' && job.result_url && (
        <button
          onClick={onDownload}
          className="mt-4 w-full px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 transition"
        >
          Download Results
        </button>
      )}

      {job.status === 'failed' && job.error_message && (
        <div className="mt-4 p-3 bg-red-100 border border-red-300 rounded">
          <p className="text-sm text-red-800">
            <strong>Error:</strong> {job.error_message}
          </p>
        </div>
      )}
    </div>
  );
}
