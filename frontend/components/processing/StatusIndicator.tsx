import { HTMLAttributes } from 'react';
import { Loader2 } from 'lucide-react';
import { cn, theme } from '@/lib/theme';

interface ProgressBarProps extends HTMLAttributes<HTMLDivElement> {
  value: number;
  showLabel?: boolean;
  variant?: 'blue' | 'emerald' | 'amber';
}

export const ProgressBar = ({ 
  value, 
  showLabel = true, 
  variant = 'blue',
  className,
  ...props 
}: ProgressBarProps) => {
  const variants = {
    blue: 'bg-blue-500',
    emerald: 'bg-emerald-500',
    amber: 'bg-amber-500',
  };

  return (
    <div className={cn('flex items-center gap-2', className)} {...props}>
      <div className={cn(
        'flex-1 h-1.5',
        theme.colors.background.tertiary,
        theme.radius.full,
        'overflow-hidden'
      )}>
        <div
          className={cn(
            'h-full',
            variants[variant],
            theme.radius.full,
            theme.transitions.all,
            'duration-500'
          )}
          style={{ width: `${value}%` }}
        />
      </div>
      {showLabel && (
        <span className={cn('text-xs tabular-nums', theme.colors.text.muted)}>
          {Math.round(value)}%
        </span>
      )}
    </div>
  );
};

interface StatusIndicatorProps {
  status: 'pending' | 'processing' | 'completed' | 'failed';
  message?: string;
  progress?: number;
}

export const StatusIndicator = ({ status, message, progress }: StatusIndicatorProps) => {
  const statusConfig = {
    pending: {
      icon: <Loader2 className={cn(theme.colors.accent.blue, 'animate-spin')} size={20} />,
      text: message || 'Queued...',
      textColor: theme.colors.text.tertiary,
    },
    processing: {
      icon: <Loader2 className={cn(theme.colors.accent.blue, 'animate-spin')} size={20} />,
      text: message || 'Processing...',
      textColor: theme.colors.text.tertiary,
    },
    completed: {
      icon: (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <circle cx="10" cy="10" r="9" className="stroke-emerald-500" strokeWidth="2" />
          <path d="M6 10l3 3 5-6" className="stroke-emerald-500" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ),
      text: message || 'Completed',
      textColor: 'text-emerald-400',
    },
    failed: {
      icon: (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <circle cx="10" cy="10" r="9" className="stroke-red-500" strokeWidth="2" />
          <path d="M7 7l6 6M13 7l-6 6" className="stroke-red-500" strokeWidth="2" strokeLinecap="round" />
        </svg>
      ),
      text: message || 'Failed',
      textColor: 'text-red-400',
    },
  };

  const config = statusConfig[status];

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        {config.icon}
        <div className="flex-1">
          <p className={cn('text-sm', config.textColor)}>
            {config.text}
          </p>
          {status === 'processing' && progress !== undefined && (
            <ProgressBar value={progress} variant="blue" className="mt-1" />
          )}
        </div>
      </div>
    </div>
  );
};
