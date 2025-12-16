import { HTMLAttributes } from 'react';
import { cn, theme } from '@/lib/theme';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'overlay' | 'strong';
}

export const Card = ({ children, variant = 'default', className, ...props }: CardProps) => {
  const variants = {
    default: cn(
      theme.colors.background.overlay,
      theme.colors.border.secondary,
    ),
    overlay: cn(
      theme.colors.background.overlayStrong,
      theme.colors.border.muted,
      theme.effects.backdropBlur,
    ),
    strong: cn(
      theme.colors.background.tertiary,
      theme.colors.border.primary,
    ),
  };

  return (
    <div
      className={cn(
        'border',
        theme.radius.lg,
        variants[variant],
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};

interface CardHeaderProps extends HTMLAttributes<HTMLDivElement> {
  title: string;
  subtitle?: string;
}

export const CardHeader = ({ title, subtitle, className, ...props }: CardHeaderProps) => (
  <div
    className={cn(
      'px-4 py-3',
      'border-b',
      theme.colors.border.secondary,
      className
    )}
    {...props}
  >
    <h3 className={cn('text-sm font-semibold', theme.colors.text.secondary)}>
      {title}
    </h3>
    {subtitle && (
      <p className={cn('text-xs mt-1', theme.colors.text.muted)}>
        {subtitle}
      </p>
    )}
  </div>
);

export const CardContent = ({ children, className, ...props }: HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('p-4', className)} {...props}>
    {children}
  </div>
);
