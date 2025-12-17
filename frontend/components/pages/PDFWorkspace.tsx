import dynamic from 'next/dynamic';
import { cn, theme } from '@/lib/theme';
import { Loader2 } from 'lucide-react';
import { Region, DetectedRegion, JobStatus } from '@/types/api';
import { RegionsSidebar } from './RegionsSidebar';

const PDFViewer = dynamic(() => import('@/components/pdf/PDFViewer'), {
  ssr: false,
  loading: () => (
    <div
      className={cn(
        theme.colors.background.secondary,
        theme.radius.lg,
        theme.colors.border.primary,
        'border flex items-center justify-center'
      )}
      style={{ minHeight: '700px' }}
    >
      <Loader2 className={theme.colors.foreground.disabled + ' animate-spin'} size={40} />
    </div>
  ),
});

interface PDFWorkspaceProps {
  file: File;
  currentPage: number;
  onPageChange: (page: number) => void;
  detectedRegions: DetectedRegion[];
  approvedRegions: DetectedRegion[];
  onRegionAdd: (region: Region) => void;
  onRegionUpdate: (region: DetectedRegion) => void;
  onRegionRemove: (regionId: string) => void;
  isDetecting: boolean;
  isProcessing: boolean;
  job: JobStatus | null;
  onExtract: (region: DetectedRegion, format: 'csv' | 'tsv' | 'json') => void;
  onDownload: () => void;
}

export const PDFWorkspace = ({
  file,
  currentPage,
  onPageChange,
  detectedRegions,
  approvedRegions,
  onRegionAdd,
  onRegionUpdate,
  onRegionRemove,
  isDetecting,
  isProcessing,
  job,
  onExtract,
  onDownload,
}: PDFWorkspaceProps) => {
  return (
    <div className="flex gap-6 h-[calc(100vh-140px)]">
      {/* Left: PDF Viewer */}
      <div className={cn(
        'flex-[2] overflow-hidden min-w-0',
        theme.colors.background.secondary,
        theme.colors.border.secondary,
        'border',
        theme.radius.lg
      )}>
        <PDFViewer
          file={file}
          onRegionAdd={onRegionAdd}
          currentPage={currentPage}
          onPageChange={onPageChange}
          detectedRegions={detectedRegions}
          approvedRegions={approvedRegions}
          onRegionUpdate={onRegionUpdate}
          onRegionRemove={onRegionRemove}
        />
      </div>

      {/* Right: Regions Sidebar */}
      <RegionsSidebar
        currentPage={currentPage}
        isDetecting={isDetecting}
        detectedRegions={detectedRegions}
        isProcessing={isProcessing}
        job={job}
        onExtract={onExtract}
        onDownload={onDownload}
      />
    </div>
  );
};
