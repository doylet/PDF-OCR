import { HTMLAttributes } from 'react';
import { cn, theme } from '@/lib/theme';

interface BadgeProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'success' | 'warning' | 'error' | 'info' | 'neutral';
  size?: 'sm' | 'md';
}

export const Badge = ({ 
  children, 
  variant = 'neutral', 
  size = 'md',
  className, 
  ...props 
}: BadgeProps) => {
  const variants = {
    success: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
    warning: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
    error: 'bg-red-500/10 border-red-500/30 text-red-400',
    info: 'bg-blue-500/10 border-blue-500/30 text-blue-400',
    neutral: 'bg-slate-500/10 border-slate-500/30 text-slate-400',
  };

  const sizes = {
    sm: 'px-2 py-0.5 text-[10px]',
    md: 'px-2.5 py-1 text-xs',
  };

  return (
    <div
      className={cn(
        'inline-flex items-center gap-1',
        'border',
        theme.radius.md,
        'font-medium uppercase',
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};
