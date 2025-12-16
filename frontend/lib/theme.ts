export const theme = {
  colors: {
    background: {
      primary: 'bg-slate-950',
      secondary: 'bg-slate-900',
      tertiary: 'bg-slate-800',
      overlay: 'bg-slate-900/50',
      overlayStrong: 'bg-slate-800/95',
      overlayLight: 'bg-slate-800/30',
      hover: 'hover:bg-slate-800',
      hoverLight: 'hover:bg-slate-900/80',
    },
    text: {
      primary: 'text-white',
      secondary: 'text-slate-200',
      tertiary: 'text-slate-300',
      muted: 'text-slate-400',
      subtle: 'text-slate-500',
      disabled: 'text-slate-600',
    },
    border: {
      primary: 'border-slate-700',
      secondary: 'border-slate-800',
      muted: 'border-slate-600',
      focus: 'focus:border-blue-500',
    },
    accent: {
      blue: 'text-blue-400',
      blueHover: 'hover:text-blue-500',
      blueBg: 'bg-blue-500',
      blueBgHover: 'hover:bg-blue-600',
      blueBorder: 'border-blue-500',
      emerald: 'text-emerald-400',
      emeraldBg: 'bg-emerald-600',
      emeraldBgHover: 'hover:bg-emerald-700',
      amber: 'text-amber-400',
      purple: 'text-purple-400',
      red: 'text-red-400',
      redBg: 'bg-red-600',
      redBgHover: 'hover:bg-red-700',
    },
    regionTypes: {
      TABLE: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10',
      HEADING: 'text-amber-400 border-amber-500/30 bg-amber-500/10',
      LIST: 'text-purple-400 border-purple-500/30 bg-purple-500/10',
      TEXT: 'text-blue-400 border-blue-500/30 bg-blue-500/10',
      NONE: 'text-slate-400 border-slate-500/30 bg-slate-500/10',
    },
  },
  spacing: {
    xs: 'p-1',
    sm: 'p-2',
    md: 'p-3',
    lg: 'p-4',
    xl: 'p-8',
    xxl: 'p-16',
  },
  radius: {
    sm: 'rounded',
    md: 'rounded-md',
    lg: 'rounded-lg',
    xl: 'rounded-xl',
    full: 'rounded-full',
  },
  shadow: {
    sm: 'shadow',
    md: 'shadow-md',
    lg: 'shadow-lg',
    blue: 'shadow-lg shadow-blue-500/20',
  },
  transitions: {
    default: 'transition',
    all: 'transition-all',
    colors: 'transition-colors',
  },
  effects: {
    backdropBlur: 'backdrop-blur-sm',
    backdropBlurXl: 'backdrop-blur-xl',
  },
} as const;

export const cn = (...classes: (string | boolean | undefined | null)[]) => {
  return classes.filter(Boolean).join(' ');
};
