import { cn, theme } from '@/lib/theme';
import { LucideIcon } from 'lucide-react';

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
}

export const EmptyState = ({ 
  icon: Icon, 
  title, 
  description 
}: EmptyStateProps) => {
  return (
    <div className={cn(
      'flex flex-col items-center justify-center',
      'h-full p-12 text-center'
    )}>
      <Icon className={theme.colors.foreground.disabled} size={48} />
      <p className={cn('mt-4 text-sm', theme.colors.foreground.muted)}>
        {title}
      </p>
      {description && (
        <p className={cn('mt-2 text-xs', theme.colors.foreground.subtle)}>
          {description}
        </p>
      )}
    </div>
  );
};
