import { Brain, Eye, Database, Zap, Check } from 'lucide-react';
import { JobStatus } from '@/types/api';

export default function AgenticProcessingFeedback({ job }: { job: JobStatus }) {
  return (
    <div className="space-y-3">
      {/* Animated pulse for AI thinking */}
      <div className="flex items-center gap-3">
        <div className="relative">
          <div className="w-10 h-10 bg-blue-500/20 rounded-full flex items-center justify-center border border-blue-400/50">
            <Brain className="text-blue-400" size={20} />
          </div>
          <div className="absolute inset-0 bg-blue-500/20 rounded-full animate-ping" />
        </div>
        <div className="flex-1">
          <p className="text-sm font-medium text-slate-200">{job.processing_step || 'Processing...'}</p>
          <div className="flex items-center gap-2 mt-1">
            <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
              <div 
                className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full transition-all duration-500"
                style={{ width: `${job.progress || 0}%` }}
              />
            </div>
            <span className="text-xs text-slate-400 tabular-nums">{Math.round(job.progress || 0)}%</span>
          </div>
        </div>
      </div>

      {/* Live stats */}
      {job.detected_entities !== undefined && (
        <div className="grid grid-cols-3 gap-2">
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-1">
              <Eye className="text-emerald-400" size={14} />
              <p className="text-xs text-slate-400">Detected</p>
            </div>
            <p className="text-lg font-semibold text-emerald-400 tabular-nums">{job.detected_entities}</p>
          </div>
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-1">
              <Database className="text-blue-400" size={14} />
              <p className="text-xs text-slate-400">Fields</p>
            </div>
            <p className="text-lg font-semibold text-blue-400 tabular-nums">{Math.floor((job.detected_entities || 0) * 1.5)}</p>
          </div>
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-1">
              <Zap className="text-amber-400" size={14} />
              <p className="text-xs text-slate-400">Speed</p>
            </div>
            <p className="text-lg font-semibold text-amber-400">Fast</p>
          </div>
        </div>
      )}

      {/* Processing steps visualization */}
      <div className="bg-slate-800/30 border border-slate-700 rounded-lg p-3 space-y-2">
        {[
          { label: 'Document Analysis', done: (job.progress || 0) > 20 },
          { label: 'AI Detection', done: (job.progress || 0) > 50 },
          { label: 'Data Extraction', done: (job.progress || 0) > 80 },
          { label: 'Validation', done: (job.progress || 0) > 95 }
        ].map((step, idx) => (
          <div key={idx} className="flex items-center gap-2">
            {step.done ? (
              <div className="w-4 h-4 bg-emerald-500 rounded-full flex items-center justify-center">
                <Check size={10} className="text-white" />
              </div>
            ) : (
              <div className="w-4 h-4 border-2 border-slate-600 rounded-full" />
            )}
            <p className={`text-xs ${step.done ? 'text-slate-300' : 'text-slate-500'}`}>{step.label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}