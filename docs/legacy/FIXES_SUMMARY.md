# Fixes Summary

## Issues Addressed

### 1. Theme Accessibility Improvements ✅

**Problem**: Text using slate colors (secondary/tertiary) over emerald backgrounds created poor contrast.

**Solution**: 
- Refactored theme to use `foreground` and `background` pattern instead of just `text`
- Updated `regionTypes` to have proper color structure:
  ```typescript
  TABLE: {
    foreground: 'text-emerald-100',  // High contrast
    background: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
    accent: 'text-emerald-400',
  }
  ```
- Kept `text` as deprecated alias for backward compatibility
- Updated RegionItem component to use new accessible color structure

**Files Changed**:
- `lib/theme.ts` - Added foreground colors, restructured regionTypes
- `components/ui/RegionItem.tsx` - Updated to use new color structure

---

### 2. TSV Download Bug ✅

**Problem**: When extracting a region as TSV format, the downloaded file was named `.csv` instead of `.tsv`.

**Root Cause**: The `handleDownload` function used the global `outputFormat` state (which defaults to "csv") instead of the format that was actually requested for the extraction job.

**Solution**:
- Added `output_format` field to `JobStatus` interface
- Updated `handleDownload` to use the format from the job: `job.output_format || outputFormat`

**Files Changed**:
- `types/api.ts` - Added `output_format?: 'csv' | 'tsv' | 'json'` to JobStatus
- `app/page.tsx` - Fixed download logic to use job's format

---

### 3. PDFViewer Component Extraction ✅

**Problem**: PDFViewer is a large monolithic component that should have reusable UI components extracted.

**Solution**: Created 4 new reusable UI components that can be used across the app:

#### New Components:

**ZoomControls** (`components/ui/ZoomControls.tsx`)
- Zoom in/out buttons with +/- icons
- Current zoom level display (percentage)
- Reset zoom button
- Positioned in top-right corner
- Props: `zoomLevel`, `onZoomIn`, `onZoomOut`, `onResetZoom`, `minZoom`, `maxZoom`

**PageNavigation** (`components/ui/PageNavigation.tsx`)
- Previous/Next page buttons with chevron icons
- Current page / total pages display
- Buttons disabled at boundaries
- Props: `currentPage`, `totalPages`, `onPageChange`

**ThumbnailStrip** (`components/ui/ThumbnailStrip.tsx`)
- Vertical thumbnail sidebar showing all pages
- Highlights current page with blue border
- Fallback icon if thumbnail not loaded
- Props: `numPages`, `currentPage`, `onPageSelect`, `thumbnails?`

**EmptyState** (`components/ui/EmptyState.tsx`)
- Generic empty state component for any context
- Shows icon, title, and optional description
- Centered layout with muted colors
- Props: `icon`, `title`, `description?`

**Files Created**:
- `components/ui/ZoomControls.tsx`
- `components/ui/PageNavigation.tsx`
- `components/ui/ThumbnailStrip.tsx`
- `components/ui/EmptyState.tsx`
- Updated `components/ui/index.ts` with new exports

---

## Testing Recommendations

1. **Accessibility**: Check color contrast ratios meet WCAG AA standards (4.5:1 for normal text)
2. **TSV Downloads**: 
   - Extract a region as TSV
   - Verify downloaded file has `.tsv` extension
   - Verify content is tab-separated, not comma-separated
3. **UI Components**: The new components are ready to be integrated into PDFViewer to replace hardcoded UI sections

---

## Next Steps

To complete the PDFViewer refactoring, replace these sections with the new components:

```typescript
// In PDFViewer.tsx:
import { ZoomControls, PageNavigation, ThumbnailStrip, EmptyState } from '@/components/ui';

// Replace zoom controls section (lines ~817-891) with:
<ZoomControls
  zoomLevel={zoomLevel}
  onZoomIn={() => setZoomLevel(Math.min(3.0, zoomLevel + 0.1))}
  onZoomOut={() => setZoomLevel(Math.max(0.5, zoomLevel - 0.1))}
  onResetZoom={() => setZoomLevel(1.0)}
/>

// Replace page navigation (lines ~1004-1018) with:
<PageNavigation
  currentPage={currentPage}
  totalPages={numPages}
  onPageChange={onPageChange}
/>

// Replace thumbnail strip (lines ~710-749) with:
<ThumbnailStrip
  numPages={numPages}
  currentPage={currentPage}
  onPageSelect={onPageChange}
  thumbnails={thumbnails}
/>

// Replace empty state (lines ~697-709) with:
<EmptyState
  icon={FileText}
  title="No PDF loaded"
  description="Upload a PDF to get started"
/>
```
