import { cn, theme } from '@/lib/theme';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from './Button';

interface PageNavigationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

export const PageNavigation = ({
  currentPage,
  totalPages,
  onPageChange,
}: PageNavigationProps) => {
  return (
    <div className={cn(
      'flex items-center justify-center gap-3 py-3',
      theme.colors.background.secondary,
      'border-t',
      theme.colors.border.secondary
    )}>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
        icon={<ChevronLeft size={16} />}
      />
      
      <div className={cn(
        'px-3 py-1',
        theme.colors.background.tertiary,
        theme.radius.md,
        'text-sm',
        theme.colors.foreground.primary
      )}>
        <span className="font-medium">{currentPage}</span>
        <span className={theme.colors.foreground.muted}> / {totalPages}</span>
      </div>
      
      <Button
        variant="ghost"
        size="sm"
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
        icon={<ChevronRight size={16} />}
      />
    </div>
  );
};
