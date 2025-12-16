import { Upload, Loader2, FileText } from 'lucide-react';
import { cn, theme } from '@/lib/theme';

interface FileUploadProps {
  onFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  isUploading?: boolean;
  accept?: string;
}

export const FileUpload = ({ 
  onFileSelect, 
  isUploading, 
  accept = 'application/pdf' 
}: FileUploadProps) => {
  return (
    <div className="group relative">
      <input
        type="file"
        accept={accept}
        onChange={onFileSelect}
        disabled={isUploading}
        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed z-10"
      />
      <div
        className={cn(
          theme.colors.background.overlay,
          'border-2 border-dashed',
          theme.colors.border.primary,
          'hover:border-blue-500/50',
          theme.radius.xl,
          'p-16 text-center',
          theme.transitions.all,
          theme.colors.background.hoverLight,
        )}
      >
        {isUploading ? (
          <>
            <Loader2
              className={cn(theme.colors.accent.blue, 'animate-spin mb-4')}
              size={48}
            />
            <p className={cn(theme.colors.text.tertiary, 'font-medium')}>
              Uploading...
            </p>
          </>
        ) : (
          <>
            <Upload
              className={cn(
                'mx-auto mb-4',
                theme.colors.text.subtle,
                'group-hover:text-blue-500',
                theme.transitions.default
              )}
              size={48}
            />
            <p className={cn(theme.colors.text.tertiary, 'font-medium mb-2')}>
              Click to upload or drag and drop
            </p>
            <p className={cn('text-sm', theme.colors.text.muted)}>
              PDF documents only
            </p>
          </>
        )}
      </div>
    </div>
  );
};

interface FileInfoProps {
  file: File;
  onRemove: () => void;
}

export const FileInfo = ({ file, onRemove }: FileInfoProps) => {
  return (
    <div
      className={cn(
        'flex items-center gap-3',
        'px-4 py-2',
        theme.colors.background.tertiary,
        theme.colors.border.primary,
        'border',
        theme.radius.lg,
      )}
    >
      <FileText className={theme.colors.text.muted} size={16} />
      <div className="flex-1 min-w-0">
        <p className={cn('text-sm truncate', theme.colors.text.secondary)}>
          {file.name}
        </p>
        <p className={cn('text-xs', theme.colors.text.subtle)}>
          {(file.size / 1024 / 1024).toFixed(2)} MB
        </p>
      </div>
      <button
        onClick={onRemove}
        className={cn(
          'p-2',
          theme.colors.text.muted,
          'hover:text-white',
          theme.colors.background.hover,
          theme.radius.lg,
          theme.transitions.default,
        )}
        aria-label="Remove file"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
          <path d="M12 4L4 12M4 4l8 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </button>
    </div>
  );
};
