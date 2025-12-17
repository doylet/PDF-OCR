import { cn, theme } from '@/lib/theme';
import { Card } from '@/components/ui';
import { FileUpload } from '@/components/processing';
import { FileText, Sparkles, Grid3x3 } from 'lucide-react';

interface WelcomeScreenProps {
  onFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  isUploading: boolean;
}

export const WelcomeScreen = ({ onFileSelect, isUploading }: WelcomeScreenProps) => {
  return (
    <div className="max-w-4xl mx-auto">
      <div className="text-center mb-8">
        <h2 className={cn('text-3xl font-bold mb-2', theme.colors.foreground.primary)}>
          Extract Structured Data from PDFs
        </h2>
        <p className={theme.colors.foreground.muted}>
          Powered by AI agents and GCP Document AI
        </p>
      </div>

      <FileUpload onFileSelect={onFileSelect} isUploading={isUploading} />

      <div className="grid md:grid-cols-2 gap-4 mt-8">
        <Card variant="overlay" className="p-6">
          <div className={cn(
            'w-10 h-10 mb-4',
            'bg-blue-500/20 border border-blue-500/30',
            theme.radius.lg,
            'flex items-center justify-center'
          )}>
            <Sparkles className={theme.colors.accent.blue} size={20} />
          </div>
          <h3 className={cn(theme.colors.foreground.primary, 'font-semibold mb-2')}>
            AI Agent Mode
          </h3>
          <p className={cn('text-sm', theme.colors.foreground.muted)}>
            Automatically detect and extract tables, forms, and structured
            data using advanced AI
          </p>
        </Card>

        <Card variant="overlay" className="p-6">
          <div className={cn(
            'w-10 h-10 mb-4',
            theme.colors.background.tertiary + '/50',
            theme.colors.border.muted,
            'border',
            theme.radius.lg,
            'flex items-center justify-center'
          )}>
            <Grid3x3 className={theme.colors.foreground.muted} size={20} />
          </div>
          <h3 className={cn(theme.colors.foreground.primary, 'font-semibold mb-2')}>
            Manual Selection
          </h3>
          <p className={cn('text-sm', theme.colors.foreground.muted)}>
            Precisely control extraction by selecting specific regions in
            your document
          </p>
        </Card>
      </div>
    </div>
  );
};
