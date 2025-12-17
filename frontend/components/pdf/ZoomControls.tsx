import { cn, theme } from '@/lib/theme';
import { ZoomIn, ZoomOut, Maximize2 } from 'lucide-react';
import { Button } from '@/components/ui';

interface ZoomControlsProps {
  zoomLevel: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onResetZoom: () => void;
  minZoom?: number;
  maxZoom?: number;
}

export const ZoomControls = ({
  zoomLevel,
  onZoomIn,
  onZoomOut,
  onResetZoom,
  minZoom = 0.5,
  maxZoom = 3.0,
}: ZoomControlsProps) => {
  return (
    <div className={cn(
      'absolute top-4 right-4 z-20',
      theme.colors.background.overlayStrong,
      'border',
      theme.colors.border.primary,
      theme.radius.lg,
      theme.shadow.md,
      'p-2 space-y-2'
    )}>
      <Button
        variant="ghost"
        size="sm"
        onClick={onZoomIn}
        disabled={zoomLevel >= maxZoom}
        icon={<ZoomIn size={16} />}
        title="Zoom In"
      />
      
      <div className={cn(
        'px-2 py-1 text-xs font-mono text-center',
        theme.colors.foreground.secondary
      )}>
        {Math.round(zoomLevel * 100)}%
      </div>
      
      <Button
        variant="ghost"
        size="sm"
        onClick={onZoomOut}
        disabled={zoomLevel <= minZoom}
        icon={<ZoomOut size={16} />}
        title="Zoom Out"
      />
      
      <div className={cn('border-t pt-2', theme.colors.border.primary)}>
        <Button
          variant="ghost"
          size="sm"
          onClick={onResetZoom}
          icon={<Maximize2 size={16} />}
          title="Reset Zoom"
        />
      </div>
    </div>
  );
};
