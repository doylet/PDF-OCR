'use client';

import { JobStatus } from '@/types/api';
import { CheckCircle, Clock, AlertCircle, Loader2, FileText, ExternalLink } from 'lucide-react';
import { useState, useEffect } from 'react';

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

interface TraceEvent {
  step: string;
  status: string;
  region_id?: string;
  [key: string]: unknown;
}

interface JobStatusDisplayProps {
  job: JobStatus | null;
  onDownload: () => void;
  onRegionsDetected?: (regions: DetectedRegion[]) => void;
}

interface DebugGraph {
  summary?: {
    outcome: string;
    pages: number;
    regions_proposed: number;
    regions_extracted: number;
    trace: TraceEvent[];
  };
  regions?: DetectedRegion[];
}

export default function JobStatusDisplay({ job, onDownload, onRegionsDetected }: JobStatusDisplayProps) {
  const [debugGraph, setDebugGraph] = useState<DebugGraph | null>(null);
  const [showDebug, setShowDebug] = useState(false);
  
  useEffect(() => {
    if (job?.debug_graph_url && job.status === 'completed') {
      fetch(job.debug_graph_url)
        .then(res => res.json())
        .then(data => {
          setDebugGraph(data);
          if (onRegionsDetected && data.regions) {
            onRegionsDetected(data.regions);
          }
        })
        .catch(err => console.error('Failed to load debug graph:', err));
    }
  }, [job?.debug_graph_url, job?.status, onRegionsDetected]);
  
  if (!job) return null;

  const getStatusIcon = () => {
    switch (job.status) {
      case 'pending':
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
      case 'pending':
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
      case 'pending':
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
      
      {debugGraph && (
        <div className="mt-4 border-t pt-4">
          <button
            onClick={() => setShowDebug(!showDebug)}
            className="flex items-center space-x-2 text-sm text-blue-600 hover:text-blue-800 mb-2"
          >
            <FileText size={16} />
            <span>{showDebug ? 'Hide' : 'Show'} Agentic Debug Info</span>
          </button>
          
          {showDebug && debugGraph.summary && (
            <div className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-2 p-3 bg-gray-50 rounded">
                <div>
                  <span className="font-semibold">Outcome:</span>
                  <span className={`ml-2 px-2 py-1 rounded text-xs ${
                    debugGraph.summary.outcome === 'success' ? 'bg-green-200 text-green-800' :
                    debugGraph.summary.outcome === 'partial_success' ? 'bg-yellow-200 text-yellow-800' :
                    debugGraph.summary.outcome === 'no_match' ? 'bg-orange-200 text-orange-800' :
                    'bg-red-200 text-red-800'
                  }`}>
                    {debugGraph.summary.outcome}
                  </span>
                </div>
                <div>
                  <span className="font-semibold">Pages:</span> {debugGraph.summary.pages}
                </div>
                <div>
                  <span className="font-semibold">Regions Proposed:</span> {debugGraph.summary.regions_proposed}
                </div>
                <div>
                  <span className="font-semibold">Regions Extracted:</span> {debugGraph.summary.regions_extracted}
                </div>
              </div>
              
              {debugGraph.summary.trace && debugGraph.summary.trace.length > 0 && (
                <div>
                  <h4 className="font-semibold mb-2">Execution Trace:</h4>
                  <div className="space-y-1 max-h-60 overflow-y-auto bg-gray-50 p-2 rounded">
                    {debugGraph.summary.trace.map((event, idx: number) => (
                      <div key={idx} className="flex items-center space-x-2 text-xs">
                        <span className={`px-2 py-0.5 rounded ${
                          event.status === 'success' ? 'bg-green-100 text-green-800' :
                          event.status === 'failed' ? 'bg-red-100 text-red-800' :
                          'bg-blue-100 text-blue-800'
                        }`}>
                          {event.status}
                        </span>
                        <span className="text-gray-600">{event.step}</span>
                        {event.region_id && <span className="text-gray-400">({event.region_id})</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              <a
                href={job.debug_graph_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center space-x-2 text-blue-600 hover:text-blue-800"
              >
                <ExternalLink size={14} />
                <span>View Full Debug Graph JSON</span>
              </a>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
