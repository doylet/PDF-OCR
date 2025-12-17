import { cn, theme } from '@/lib/theme';
import { FileText } from 'lucide-react';

interface ThumbnailStripProps {
  numPages: number;
  currentPage: number;
  onPageSelect: (page: number) => void;
  thumbnails?: Record<number, string>;
}

export const ThumbnailStrip = ({
  numPages,
  currentPage,
  onPageSelect,
  thumbnails = {},
}: ThumbnailStripProps) => {
  return (
    <div className={cn(
      'w-24 border-r',
      theme.colors.border.secondary,
      theme.colors.background.secondary,
      'overflow-y-auto'
    )}>
      <div className="p-2 space-y-2">
        {Array.from({ length: numPages }, (_, i) => i + 1).map((pageNum) => (
          <button
            key={pageNum}
            onClick={() => onPageSelect(pageNum)}
            className={cn(
              'w-full aspect-[3/4]',
              theme.radius.md,
              'border-2',
              currentPage === pageNum
                ? cn(theme.colors.accent.blueBorder, theme.colors.accent.blueBg + '/10')
                : theme.colors.border.primary,
              'overflow-hidden',
              theme.colors.background.tertiary,
              theme.transitions.default,
              theme.colors.background.hover,
              'flex items-center justify-center'
            )}
          >
            {thumbnails[pageNum] ? (
              <img
                src={thumbnails[pageNum]}
                alt={`Page ${pageNum}`}
                className="w-full h-full object-contain"
              />
            ) : (
              <div className="flex flex-col items-center gap-1">
                <FileText className={theme.colors.foreground.disabled} size={20} />
                <span className={cn('text-xs', theme.colors.foreground.muted)}>
                  {pageNum}
                </span>
              </div>
            )}
          </button>
        ))}
      </div>
    </div>
  );
};
