# Component Organization

This directory is organized by feature domain for better maintainability and discoverability.

## Structure

```
components/
├── ui/                  # Primitive, reusable UI components
│   ├── Badge.tsx       # Status badges
│   ├── Button.tsx      # Button variants (primary, secondary, ghost, etc)
│   ├── Card.tsx        # Card container with header/content
│   └── EmptyState.tsx  # Empty state display
│
├── pdf/                 # PDF viewer and related components
│   ├── PDFViewer.tsx        # Main PDF viewer component
│   ├── RegionList.tsx       # List of detected regions
│   ├── RegionItem.tsx       # Individual region card
│   ├── PageNavigation.tsx   # Page prev/next controls
│   ├── ThumbnailStrip.tsx   # Thumbnail sidebar
│   └── ZoomControls.tsx     # Zoom in/out/reset controls
│
└── processing/          # Job processing and upload components
    ├── AgenticProcessingFeedback.tsx  # AI processing feedback
    ├── JobStatusDisplay.tsx           # Job status overview
    ├── StatusIndicator.tsx            # Progress/status indicators
    └── FileUpload.tsx                 # File upload with drag-drop

```

## Import Patterns

### UI Components (shared primitives)
```tsx
import { Button, Card, Badge, EmptyState } from '@/components/ui';
```

### PDF Components
```tsx
import { PDFViewer, RegionItem, ZoomControls } from '@/components/pdf';
```

### Processing Components
```tsx
import { FileUpload, StatusIndicator, JobStatusDisplay } from '@/components/processing';
```

## Guidelines

### ui/ - Primitive Components
- **Purpose**: Truly reusable, generic UI primitives
- **No domain logic**: Should not contain PDF or job-specific logic
- **Theme-aware**: Use theme tokens exclusively
- **Examples**: buttons, cards, badges, inputs, dialogs

### pdf/ - PDF Domain
- **Purpose**: All PDF viewing, annotation, and region detection UI
- **Self-contained**: PDF-specific logic lives here
- **Reusable**: Components can be composed together
- **Examples**: viewer, regions, navigation, zoom

### processing/ - Job Processing Domain
- **Purpose**: File upload, job status, AI processing feedback
- **Workflow-focused**: Components related to the extraction pipeline
- **Examples**: upload, status, progress, feedback

## Adding New Components

1. **Identify the domain**: Is it a primitive (ui/), PDF-related (pdf/), or processing-related (processing/)?
2. **Create the component**: Add to the appropriate folder
3. **Update index.ts**: Export from the folder's barrel export
4. **Use theme tokens**: Import `theme` from `@/lib/theme` and use tokens
5. **Document props**: Add TypeScript interfaces for all props

## Migration Notes

Previous flat structure moved to domain-based organization on Dec 17, 2025:
- `components/PDFViewer.tsx` → `components/pdf/PDFViewer.tsx`
- `components/ui/RegionItem.tsx` → `components/pdf/RegionItem.tsx`
- `components/ui/FileUpload.tsx` → `components/processing/FileUpload.tsx`
- etc.

All imports updated in app/page.tsx to reflect new structure.
