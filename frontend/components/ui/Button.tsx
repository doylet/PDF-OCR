import { ButtonHTMLAttributes, forwardRef } from 'react';
import { Loader2 } from 'lucide-react';
import { cn, theme } from '@/lib/theme';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'success' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  icon?: React.ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ 
    children, 
    variant = 'primary', 
    size = 'md', 
    isLoading, 
    icon, 
    className,
    disabled,
    ...props 
  }, ref) => {
    const baseClasses = cn(
      'font-medium',
      theme.radius.lg,
      theme.transitions.default,
      'flex items-center justify-center gap-2',
      'disabled:cursor-not-allowed disabled:opacity-50',
    );

    const variants = {
      primary: cn(
        'bg-gradient-to-r from-blue-600 to-indigo-600',
        'hover:from-blue-500 hover:to-indigo-500',
        'text-white',
        theme.shadow.blue,
        'disabled:from-slate-700 disabled:to-slate-700',
        'disabled:text-slate-500 disabled:shadow-none',
      ),
      secondary: cn(
        theme.colors.background.tertiary,
        theme.colors.border.primary,
        theme.colors.text.tertiary,
        'border',
        theme.colors.background.hover,
        'hover:text-white',
      ),
      success: cn(
        theme.colors.accent.emeraldBg,
        theme.colors.accent.emeraldBgHover,
        'text-white',
        'disabled:bg-slate-700',
      ),
      danger: cn(
        theme.colors.accent.redBg,
        theme.colors.accent.redBgHover,
        'text-white',
      ),
      ghost: cn(
        theme.colors.text.muted,
        'hover:text-white',
        theme.colors.background.hover,
      ),
    };

    const sizes = {
      sm: 'px-2 py-1 text-xs',
      md: 'px-4 py-2.5 text-sm',
      lg: 'px-4 py-3 text-sm',
    };

    return (
      <button
        ref={ref}
        className={cn(baseClasses, variants[variant], sizes[size], className)}
        disabled={disabled || isLoading}
        {...props}
      >
        {isLoading ? (
          <>
            <Loader2 className="animate-spin" size={16} />
            {children}
          </>
        ) : (
          <>
            {icon}
            {children}
          </>
        )}
      </button>
    );
  }
);

Button.displayName = 'Button';
