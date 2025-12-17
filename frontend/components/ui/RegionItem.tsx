import { DetectedRegion } from '@/types/api';
import { cn, theme } from '@/lib/theme';
import { Badge } from './Badge';

interface RegionItemProps {
  region: DetectedRegion;
  isSelected?: boolean;
  onExtract?: (region: DetectedRegion, format: 'csv' | 'tsv' | 'json') => void;
  isProcessing?: boolean;
}

export const RegionItem = ({ 
  region, 
  isSelected = false, 
  onExtract,
  isProcessing = false 
}: RegionItemProps) => {
  const typeColors = theme.colors.regionTypes;
  const colors = typeColors[region.region_type as keyof typeof typeColors] || typeColors.TEXT;

  return (
    <div className={cn(
      'border p-3',
      theme.radius.lg,
      colors.foreground,
      colors.background,
      colors.border
    )}>
      <div className="flex items-start justify-between mb-2">
        <div className="flex-1">
          <Badge variant={getVariantForType(region.region_type)} size="sm">
            {region.region_type}
          </Badge>
          <p className={cn('text-xs mt-0.5', colors.accent)}>
            {Math.round(region.confidence * 100)}% confidence
          </p>
        </div>
      </div>
      
      {onExtract && (
        <div className="space-y-2 mt-2 pt-2 border-t border-current/20">
          <div className="grid grid-cols-3 gap-1">
            {(['csv', 'tsv', 'json'] as const).map((fmt) => (
              <button
                key={fmt}
                onClick={() => onExtract(region, fmt)}
                disabled={isProcessing}
                className={cn(
                  'px-2 py-1 text-[10px] font-bold uppercase',
                  theme.radius.sm,
                  'border border-current/30',
                  'hover:bg-current/20',
                  'disabled:opacity-50 disabled:cursor-not-allowed',
                  theme.transitions.default
                )}
              >
                {fmt}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

function getVariantForType(type: string): 'success' | 'warning' | 'info' | 'neutral' {
  const mapping: Record<string, 'success' | 'warning' | 'info' | 'neutral'> = {
    TABLE: 'success',
    HEADING: 'warning',
    LIST: 'info',
    TEXT: 'info',
    NONE: 'neutral',
  };
  return mapping[type] || 'neutral';
}
