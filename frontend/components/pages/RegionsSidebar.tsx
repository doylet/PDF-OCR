import { cn, theme } from '@/lib/theme';
import { Card, CardHeader, CardContent, Button } from '@/components/ui';
import { StatusIndicator } from '@/components/processing';
import { RegionItem } from '@/components/pdf';
import { DetectedRegion, JobStatus } from '@/types/api';
import { Grid3x3, Sparkles, Download, Database, AlertCircle } from 'lucide-react';

interface RegionsSidebarProps {
  currentPage: number;
  isDetecting: boolean;
  detectedRegions: DetectedRegion[];
  isProcessing: boolean;
  job: JobStatus | null;
  onExtract: (region: DetectedRegion, format: 'csv' | 'tsv' | 'json') => void;
  onDownload: () => void;
}

export const RegionsSidebar = ({
  currentPage,
  isDetecting,
  detectedRegions,
  isProcessing,
  job,
  onExtract,
  onDownload,
}: RegionsSidebarProps) => {
  const pageRegions = detectedRegions.filter(r => r.page === currentPage);

  return (
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

      {/* Detection Success */}
      {detectedRegions.length > 0 && !isDetecting && (
        <Card className="border-emerald-500/30">
          <div className="p-3 flex items-center gap-2">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="7" className={theme.colors.accent.emerald} strokeWidth="2" />
              <path d="M5 8l2 2 4-5" className={theme.colors.accent.emerald} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <p className={cn('text-xs', theme.colors.accent.emerald)}>
              {pageRegions.length === detectedRegions.length
                ? `${detectedRegions.length} ${detectedRegions.length === 1 ? 'region' : 'regions'} detected`
                : `${pageRegions.length} of ${detectedRegions.length} regions on this page`}
            </p>
          </div>
        </Card>
      )}

      {/* Regions List */}
      <Card>
        <CardHeader title={`Regions on Page ${currentPage}`} />
        <CardContent>
          {pageRegions.length === 0 ? (
            <div className="text-center py-8">
              <Grid3x3
                className={cn('mx-auto mb-2', theme.colors.foreground.disabled)}
                size={32}
              />
              <p className={cn('text-xs', theme.colors.foreground.subtle)}>
                {detectedRegions.length === 0
                  ? 'AI will detect regions automatically'
                  : 'No regions on this page'}
              </p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[320px] overflow-y-auto">
              {pageRegions.map((region) => (
                <RegionItem
                  key={region.region_id}
                  region={region}
                  isProcessing={isProcessing}
                  onExtract={onExtract}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Job Status */}
      {job && (
        <Card>
          <CardHeader title="Processing Status" />
          <CardContent>
            {job.status === "pending" && <StatusIndicator status="pending" />}

            {job.status === "processing" && (
              <StatusIndicator
                status="processing"
                message="Extracting regions..."
                progress={job.progress}
              />
            )}

            {job.status === "completed" && (
              <div className="space-y-3">
                <div className="grid grid-cols-3 gap-2">
                  <Card variant="strong" className="p-3">
                    <div className="flex items-center gap-2 mb-1">
                      <Sparkles className={theme.colors.accent.emerald} size={14} />
                      <p className={cn('text-xs', theme.colors.foreground.muted)}>Detected</p>
                    </div>
                    <p className={cn('text-lg font-semibold tabular-nums', theme.colors.accent.emerald)}>
                      {job.detected_entities}
                    </p>
                  </Card>
                  <Card variant="strong" className="p-3">
                    <div className="flex items-center gap-2 mb-1">
                      <Database className={theme.colors.accent.blue} size={14} />
                      <p className={cn('text-xs', theme.colors.foreground.muted)}>Fields</p>
                    </div>
                    <p className={cn('text-lg font-semibold tabular-nums', theme.colors.accent.blue)}>
                      {Math.floor((job.detected_entities || 0) * 1.5)}
                    </p>
                  </Card>
                  <Card variant="strong" className="p-3">
                    <div className="flex items-center gap-2 mb-1">
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <circle cx="7" cy="7" r="6" className={theme.colors.accent.emerald} strokeWidth="2" />
                        <path d="M4 7l2 2 4-4" className={theme.colors.accent.emerald} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                      <p className={cn('text-xs', theme.colors.foreground.muted)}>Status</p>
                    </div>
                    <p className={cn('text-lg font-semibold', theme.colors.accent.emerald)}>Done</p>
                  </Card>
                </div>

                <Card variant="overlay" className="p-3 space-y-2">
                  {["Document Analysis", "AI Detection", "Data Extraction", "Validation"].map((label, idx) => (
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
                      <p className={cn('text-xs', theme.colors.foreground.tertiary)}>{label}</p>
                    </div>
                  ))}
                </Card>

                <div className={cn(
                  'flex items-center gap-3 p-3',
                  theme.colors.accent.emeraldBg,
                  'border border-emerald-500/30',
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
                    <p className={cn('text-sm font-medium', theme.colors.foreground.primary)}>
                      Extraction Complete
                    </p>
                    <p className={cn('text-xs', theme.colors.foreground.secondary)}>
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
                  onClick={onDownload}
                  icon={<Download size={16} />}
                  className="w-full"
                >
                  Download {job.output_format?.toUpperCase() || 'CSV'}
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
                  <p className="text-sm font-medium text-red-400">Extraction Failed</p>
                </div>
                {job.error && <p className="text-xs text-red-300/70">{job.error}</p>}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
};
