"use client";

import React, { useState, useRef, useEffect } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { Region } from "@/types/api";
import { FileText } from "lucide-react";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface DetectedRegion {
  region_id: string;
  region_type: string;
  bbox: {
    x: number;
    y: number;
    w: number;
    h: number;
  };
  page: number;
  confidence: number;
}

type RegionEditMode = 'move' | 'resize-nw' | 'resize-ne' | 'resize-sw' | 'resize-se' | 'resize-n' | 'resize-s' | 'resize-e' | 'resize-w' | null;

interface RegionCorrection {
  original: DetectedRegion;
  corrected?: DetectedRegion;
  action: 'delete' | 'move' | 'resize' | 'retype';
  timestamp: string;
}

interface PDFViewerProps {
  file: File | null;
  regions: Region[];
  onRegionAdd: (region: Region) => void;
  onRegionRemove: (index: number) => void;
  currentPage: number;
  onPageChange: (page: number) => void;
  detectedRegions?: DetectedRegion[];
  onRegionCorrection?: (correction: RegionCorrection) => void;
  jobId?: string;
  onRegionsSelectedForExtraction?: (regionIds: string[]) => void;
  onRegionSelected?: (regionId: string | null) => void;
  selectedRegionId?: string | null;
}



export default function PDFViewer({
  file,
  regions,
  onRegionAdd,
  currentPage,
  onPageChange,
  detectedRegions = [],
  onRegionCorrection,
  onRegionsSelectedForExtraction,
  onRegionSelected,
  selectedRegionId,
}: PDFViewerProps) {
  const [numPages, setNumPages] = useState<number>(0);
  const [isDrawing, setIsDrawing] = useState(false);
  const [startPoint, setStartPoint] = useState<{ x: number; y: number } | null>(
    null
  );
  const [currentRect, setCurrentRect] = useState<Region | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [pageDimensions, setPageDimensions] = useState<{
    width: number;
    height: number;
  } | null>(null);
  const [scale, setScale] = useState<number>(1.0);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  
  // Interactive editing state
  const [selectedRegion, setSelectedRegion] = useState<string | null>(selectedRegionId || null);
  
  // Sync with external selection
  useEffect(() => {
    if (selectedRegionId !== undefined) {
      setSelectedRegion(selectedRegionId);
    }
  }, [selectedRegionId]);
  const [editMode, setEditMode] = useState<RegionEditMode>(null);
  const [editedRegions, setEditedRegions] = useState<DetectedRegion[]>(detectedRegions);
  const [hoveredRegion, setHoveredRegion] = useState<string | null>(null);
  const [corrections, setCorrections] = useState<RegionCorrection[]>([]);
  const [selectedForExtraction, setSelectedForExtraction] = useState<Set<string>>(new Set());
  const [originalRegionBeforeEdit, setOriginalRegionBeforeEdit] = useState<DetectedRegion | null>(null);
  
  // Update edited regions when detectedRegions changes
  useEffect(() => {
    setEditedRegions(detectedRegions);
  }, [detectedRegions]);

  // Create a stable blob URL from the file
  useEffect(() => {
    if (!file) {
      setBlobUrl(null);
      return;
    }

    const url = URL.createObjectURL(file);
    setBlobUrl(url);

    return () => {
      URL.revokeObjectURL(url);
    };
  }, [file]);

  function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
    setNumPages(numPages);
    onPageChange(1);
  }

  function onPageLoadSuccess(page: {
    getViewport: (options: { scale: number }) => {
      width: number;
      height: number;
    };
  }) {
    const viewport = page.getViewport({ scale: 1.0 });
    const container = containerRef.current;
    
    if (container) {
      // Calculate scale to fit container (max 2/3 of screen width)
      const containerWidth = container.clientWidth - 48; // Account for padding
      const containerHeight = container.clientHeight - 48;
      
      const scaleWidth = containerWidth / viewport.width;
      const scaleHeight = containerHeight / viewport.height;
      const optimalScale = Math.min(scaleWidth, scaleHeight, 2.0); // Cap at 2x
      
      setScale(optimalScale);
    }
    
    setPageDimensions({
      width: viewport.width,
      height: viewport.height,
    });
  }

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    // Check if clicking on existing region
    const clickedRegion = getRegionAtPoint(x, y, canvas);
    
    // Ctrl/Cmd + click toggles extraction selection without editing
    if (clickedRegion && (e.ctrlKey || e.metaKey)) {
      toggleExtractionSelection(clickedRegion.region_id);
      return;
    }
    
    if (clickedRegion) {
      // Select region and immediately enter edit mode for click-and-drag
      const mode = getResizeHandle(x, y, clickedRegion, canvas);
      console.log('Click: Selected region', clickedRegion.region_id, 'edit mode:', mode, 'startPoint:', { x, y });
      setSelectedRegion(clickedRegion.region_id);
      if (onRegionSelected) {
        onRegionSelected(clickedRegion.region_id);
      }
      setEditMode(mode);
      setIsDrawing(false);
      setStartPoint({ x, y });
      setOriginalRegionBeforeEdit(clickedRegion); // Store original before editing
    } else {
      // Drawing new manual region
      setSelectedRegion(null);
      if (onRegionSelected) {
        onRegionSelected(null);
      }
      setIsDrawing(true);
      setStartPoint({ x, y });
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    // Update cursor based on hover
    const hoveredReg = getRegionAtPoint(x, y, canvas);
    setHoveredRegion(hoveredReg?.region_id || null);
    
    if (hoveredReg && selectedRegion === hoveredReg.region_id) {
      const mode = getResizeHandle(x, y, hoveredReg, canvas);
      canvas.style.cursor = mode === 'move' ? 'move' : 
                           mode?.includes('resize') ? 'nwse-resize' : 'default';
    } else if (hoveredReg) {
      canvas.style.cursor = 'pointer';
    } else {
      canvas.style.cursor = 'crosshair';
    }
    
    // Handle drawing new region
    if (isDrawing && startPoint) {
      const width = x - startPoint.x;
      const height = y - startPoint.y;

      setCurrentRect({
        x: Math.min(startPoint.x, x),
        y: Math.min(startPoint.y, y),
        width: Math.abs(width),
        height: Math.abs(height),
        page: currentPage,
      });
      return;
    }
    
    // Handle editing existing region
    if (editMode && selectedRegion && startPoint) {
      const region = editedRegions.find(r => r.region_id === selectedRegion);
      if (!region) {
        console.log('Region not found for editing:', selectedRegion);
        return;
      }
      
      const dx = (x - startPoint.x) / canvas.width;
      const dy = (y - startPoint.y) / canvas.height;
      console.log('Move: mode=', editMode, 'dx=', dx.toFixed(4), 'dy=', dy.toFixed(4));
      
      const newBbox = { ...region.bbox };
      
      if (editMode === 'move') {
        newBbox.x += dx;
        newBbox.y += dy;
      } else if (editMode === 'resize-se') {
        newBbox.w += dx;
        newBbox.h += dy;
      } else if (editMode === 'resize-nw') {
        newBbox.x += dx;
        newBbox.y += dy;
        newBbox.w -= dx;
        newBbox.h -= dy;
      } else if (editMode === 'resize-ne') {
        newBbox.y += dy;
        newBbox.w += dx;
        newBbox.h -= dy;
      } else if (editMode === 'resize-sw') {
        newBbox.x += dx;
        newBbox.w -= dx;
        newBbox.h += dy;
      } else if (editMode === 'resize-e') {
        newBbox.w += dx;
      } else if (editMode === 'resize-w') {
        newBbox.x += dx;
        newBbox.w -= dx;
      } else if (editMode === 'resize-n') {
        newBbox.y += dy;
        newBbox.h -= dy;
      } else if (editMode === 'resize-s') {
        newBbox.h += dy;
      }
      
      // Clamp to bounds
      newBbox.x = Math.max(0, Math.min(1 - newBbox.w, newBbox.x));
      newBbox.y = Math.max(0, Math.min(1 - newBbox.h, newBbox.y));
      newBbox.w = Math.max(0.02, Math.min(1 - newBbox.x, newBbox.w));
      newBbox.h = Math.max(0.02, Math.min(1 - newBbox.y, newBbox.h));
      
      const corrected = { ...region, bbox: newBbox };
      
      setEditedRegions(editedRegions.map(r => 
        r.region_id === selectedRegion ? corrected : r
      ));
      setStartPoint({ x, y });
    }
  };

  const handleMouseUp = () => {
    if (
      currentRect &&
      currentRect.width > 10 &&
      currentRect.height > 10 &&
      pageDimensions
    ) {
      const canvas = canvasRef.current;
      if (!canvas) return;

      // Convert canvas coordinates to normalized fractions (0-1)
      // This eliminates all DPI/scale confusion - backend will multiply by its rendered image size
      const pdfRegion: Region = {
        x: currentRect.x / canvas.width,
        y: currentRect.y / canvas.height,
        width: currentRect.width / canvas.width,
        height: currentRect.height / canvas.height,
        page: currentPage,
      };

      onRegionAdd(pdfRegion);
    }
    
    // Record correction if we were editing a region
    if (editMode && selectedRegion && originalRegionBeforeEdit) {
      const editedRegion = editedRegions.find(r => r.region_id === selectedRegion);
      if (editedRegion) {
        const correction: RegionCorrection = {
          original: originalRegionBeforeEdit,
          corrected: editedRegion,
          action: editMode === 'move' ? 'move' : 'resize',
          timestamp: new Date().toISOString(),
        };
        
        setCorrections([...corrections, correction]);
        
        if (onRegionCorrection) {
          onRegionCorrection(correction);
        }
      }
    }
    
    setIsDrawing(false);
    setStartPoint(null);
    setCurrentRect(null);
    setEditMode(null);
    setOriginalRegionBeforeEdit(null);
  };
  
  // Interactive editing handlers
  const getRegionAtPoint = (x: number, y: number, canvas: HTMLCanvasElement): DetectedRegion | null => {
    const pageRegions = editedRegions.filter(r => r.page === currentPage);
    
    // Check in reverse order (topmost first)
    for (let i = pageRegions.length - 1; i >= 0; i--) {
      const region = pageRegions[i];
      const rx = region.bbox.x * canvas.width;
      const ry = region.bbox.y * canvas.height;
      const rw = region.bbox.w * canvas.width;
      const rh = region.bbox.h * canvas.height;
      
      if (x >= rx && x <= rx + rw && y >= ry && y <= ry + rh) {
        return region;
      }
    }
    return null;
  };
  
  const getResizeHandle = (x: number, y: number, region: DetectedRegion, canvas: HTMLCanvasElement): RegionEditMode => {
    const rx = region.bbox.x * canvas.width;
    const ry = region.bbox.y * canvas.height;
    const rw = region.bbox.w * canvas.width;
    const rh = region.bbox.h * canvas.height;
    const handleSize = 8;
    
    // Check corners first
    if (Math.abs(x - rx) < handleSize && Math.abs(y - ry) < handleSize) return 'resize-nw';
    if (Math.abs(x - (rx + rw)) < handleSize && Math.abs(y - ry) < handleSize) return 'resize-ne';
    if (Math.abs(x - rx) < handleSize && Math.abs(y - (ry + rh)) < handleSize) return 'resize-sw';
    if (Math.abs(x - (rx + rw)) < handleSize && Math.abs(y - (ry + rh)) < handleSize) return 'resize-se';
    
    // Check edges
    if (Math.abs(x - rx) < handleSize && y > ry && y < ry + rh) return 'resize-w';
    if (Math.abs(x - (rx + rw)) < handleSize && y > ry && y < ry + rh) return 'resize-e';
    if (Math.abs(y - ry) < handleSize && x > rx && x < rx + rw) return 'resize-n';
    if (Math.abs(y - (ry + rh)) < handleSize && x > rx && x < rx + rw) return 'resize-s';
    
    return 'move';
  };
  
  const handleRegionDelete = (regionId: string) => {
    const region = editedRegions.find(r => r.region_id === regionId);
    if (!region) return;
    
    const correction: RegionCorrection = {
      original: region,
      action: 'delete',
      timestamp: new Date().toISOString(),
    };
    
    setCorrections([...corrections, correction]);
    setEditedRegions(editedRegions.filter(r => r.region_id !== regionId));
    setSelectedRegion(null);
    
    if (onRegionCorrection) {
      onRegionCorrection(correction);
    }
  };
  
  const handleRegionTypeChange = (regionId: string, newType: string) => {
    const region = editedRegions.find(r => r.region_id === regionId);
    if (!region) return;
    
    // If marked as NONE, treat as deletion/false positive
    if (newType === 'NONE') {
      const correction: RegionCorrection = {
        original: region,
        action: 'delete',
        timestamp: new Date().toISOString(),
      };
      setCorrections([...corrections, correction]);
      setEditedRegions(editedRegions.filter(r => r.region_id !== regionId));
      setSelectedRegion(null);
      if (onRegionCorrection) {
        onRegionCorrection(correction);
      }
      return;
    }
    
    const corrected = { ...region, region_type: newType };
    
    const correction: RegionCorrection = {
      original: region,
      corrected,
      action: 'retype',
      timestamp: new Date().toISOString(),
    };
    
    setCorrections([...corrections, correction]);
    setEditedRegions(editedRegions.map(r => r.region_id === regionId ? corrected : r));
    
    if (onRegionCorrection) {
      onRegionCorrection(correction);
    }
  };

  const toggleExtractionSelection = (regionId: string) => {
    const newSelection = new Set(selectedForExtraction);
    if (newSelection.has(regionId)) {
      newSelection.delete(regionId);
    } else {
      newSelection.add(regionId);
    }
    setSelectedForExtraction(newSelection);
    
    if (onRegionsSelectedForExtraction) {
      onRegionsSelectedForExtraction(Array.from(newSelection));
    }
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !pageDimensions) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw detected regions (agentic) for current page
    const pageEditedRegions = editedRegions.filter(
      (r) => r.page === currentPage
    );
    pageEditedRegions.forEach((region) => {
      const isSelected = selectedRegion === region.region_id;
      const isHovered = hoveredRegion === region.region_id;
      const isMarkedForExtraction = selectedForExtraction.has(region.region_id);
      
      const canvasX = region.bbox.x * canvas.width;
      const canvasY = region.bbox.y * canvas.height;
      const canvasWidth = region.bbox.w * canvas.width;
      const canvasHeight = region.bbox.h * canvas.height;

      // Different colors based on region type
      const color =
        region.region_type === "TABLE"
          ? "#10b981"
          : region.region_type === "HEADING"
          ? "#f59e0b"
          : region.region_type === "LIST"
          ? "#8b5cf6"
          : region.region_type === "NONE"
          ? "#64748b"
          : "#3b82f6";

      // Dimmed appearance for regions not selected for extraction
      const opacity = isMarkedForExtraction ? "33" : "11";
      ctx.strokeStyle = color;
      ctx.fillStyle = `${color}${opacity}`;
      ctx.lineWidth = isSelected ? 4 : isHovered ? 3 : isMarkedForExtraction ? 2 : 1;
      ctx.setLineDash(isSelected || isHovered ? [] : [5, 5]);
      ctx.fillRect(canvasX, canvasY, canvasWidth, canvasHeight);
      ctx.strokeRect(canvasX, canvasY, canvasWidth, canvasHeight);
      ctx.setLineDash([]);

      // Draw region type label
      ctx.fillStyle = color;
      ctx.font = "bold 12px Arial";
      ctx.fillText(
        `${region.region_type} (${Math.round(region.confidence * 100)}%)`,
        canvasX + 5,
        canvasY + 15
      );

      // Draw checkmark for regions marked for extraction
      if (isMarkedForExtraction) {
        const checkSize = 20;
        const checkX = canvasX + canvasWidth - checkSize - 5;
        const checkY = canvasY + 5;
        
        // Draw circle background
        ctx.fillStyle = "#10b981";
        ctx.beginPath();
        ctx.arc(checkX + checkSize/2, checkY + checkSize/2, checkSize/2, 0, 2 * Math.PI);
        ctx.fill();
        
        // Draw checkmark
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(checkX + 5, checkY + checkSize/2);
        ctx.lineTo(checkX + checkSize/2.5, checkY + checkSize - 6);
        ctx.lineTo(checkX + checkSize - 4, checkY + 4);
        ctx.stroke();
      }

      // Draw resize handles for selected region
      if (isSelected) {
        const handleSize = 8;
        ctx.fillStyle = "#ffffff";
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;

        // Corner handles
        const corners = [
          { x: canvasX, y: canvasY }, // NW
          { x: canvasX + canvasWidth, y: canvasY }, // NE
          { x: canvasX, y: canvasY + canvasHeight }, // SW
          { x: canvasX + canvasWidth, y: canvasY + canvasHeight }, // SE
        ];
        
        // Edge handles
        const edges = [
          { x: canvasX + canvasWidth / 2, y: canvasY }, // N
          { x: canvasX + canvasWidth / 2, y: canvasY + canvasHeight }, // S
          { x: canvasX, y: canvasY + canvasHeight / 2 }, // W
          { x: canvasX + canvasWidth, y: canvasY + canvasHeight / 2 }, // E
        ];

        [...corners, ...edges].forEach(handle => {
          ctx.fillRect(
            handle.x - handleSize / 2,
            handle.y - handleSize / 2,
            handleSize,
            handleSize
          );
          ctx.strokeRect(
            handle.x - handleSize / 2,
            handle.y - handleSize / 2,
            handleSize,
            handleSize
          );
        });

        // Draw delete icon in top-right corner
        const deleteX = canvasX + canvasWidth - 20;
        const deleteY = canvasY + 5;
        ctx.fillStyle = "#ef4444";
        ctx.beginPath();
        ctx.arc(deleteX, deleteY, 10, 0, 2 * Math.PI);
        ctx.fill();
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(deleteX - 4, deleteY - 4);
        ctx.lineTo(deleteX + 4, deleteY + 4);
        ctx.moveTo(deleteX + 4, deleteY - 4);
        ctx.lineTo(deleteX - 4, deleteY + 4);
        ctx.stroke();
      }
    });

    // Draw existing manual regions for current page
    const pageRegions = regions.filter((r) => r.page === currentPage);
    pageRegions.forEach((region, index) => {
      const canvasX = region.x * canvas.width;
      const canvasY = region.y * canvas.height;
      const canvasWidth = region.width * canvas.width;
      const canvasHeight = region.height * canvas.height;

      ctx.strokeStyle = "#3b82f6";
      ctx.fillStyle = "rgba(59, 130, 246, 0.2)";
      ctx.lineWidth = 2;
      ctx.fillRect(canvasX, canvasY, canvasWidth, canvasHeight);
      ctx.strokeRect(canvasX, canvasY, canvasWidth, canvasHeight);

      ctx.fillStyle = "#3b82f6";
      ctx.font = "bold 16px Arial";
      ctx.fillText(`#${index + 1}`, canvasX + 5, canvasY + 20);
    });

    // Draw current drawing rectangle
    if (currentRect) {
      ctx.strokeStyle = "#10b981";
      ctx.fillStyle = "rgba(16, 185, 129, 0.2)";
      ctx.lineWidth = 2;
      ctx.fillRect(
        currentRect.x,
        currentRect.y,
        currentRect.width,
        currentRect.height
      );
      ctx.strokeRect(
        currentRect.x,
        currentRect.y,
        currentRect.width,
        currentRect.height
      );
    }
  }, [regions, editedRegions, currentRect, currentPage, pageDimensions, selectedRegion, hoveredRegion, selectedForExtraction]);

  if (!file) {
    return (
      <div className="flex-1 bg-slate-900 rounded-lg border border-slate-700 p-8">
        <div className="text-center text-slate-400">
          <FileText className="mx-auto mb-4" size={64} />
          <p>No PDF loaded</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3 h-full">
      {/* Thumbnail Strip */}
      <div
        className="w-24 bg-slate-900/50 border border-slate-700 rounded-lg p-2 overflow-y-auto"
        style={{ maxHeight: "700px" }}
      >
        <div className="space-y-2">
          {Array.from({ length: numPages }, (_, i) => i + 1).map((pageNum) => (
            <button
              key={pageNum}
              onClick={() => onPageChange(pageNum)}
              className={`w-full aspect-[8.5/11] rounded border-2 transition-all relative group overflow-hidden ${
                currentPage === pageNum
                  ? "border-blue-500 bg-blue-500/10"
                  : "border-slate-600 hover:border-slate-500 bg-slate-800/50"
              }`}
            >
              <div className="absolute inset-0 flex items-center justify-center bg-slate-800 overflow-hidden">
                {blobUrl && numPages > 0 ? (
                  <Document file={blobUrl} key={`thumb-${pageNum}`}>
                    <Page
                      pageNumber={pageNum}
                      width={68}
                      renderTextLayer={false}
                      renderAnnotationLayer={false}
                      className="pointer-events-none"
                    />
                  </Document>
                ) : (
                  <FileText
                    className={`${
                      currentPage === pageNum ? "text-blue-400" : "text-slate-600"
                    }`}
                    size={20}
                  />
                )}
              </div>
              <div
                className={`absolute bottom-1 left-0 right-0 text-center text-[10px] font-medium bg-slate-900/80 backdrop-blur-sm py-0.5 z-10 ${
                  currentPage === pageNum ? "text-blue-400" : "text-slate-300"
                }`}
              >
                {pageNum}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Main PDF Viewer */}
      <div
        className="flex-1 bg-slate-900 rounded-lg border border-slate-700 relative overflow-hidden"
        style={{ minHeight: "700px" }}
      >
        <div
          ref={containerRef}
          className="absolute inset-0 overflow-auto flex items-center justify-center"
        >
          <div className="relative">
            <Document
              file={blobUrl}
              onLoadSuccess={onDocumentLoadSuccess}
              className="flex justify-center"
            >
              <Page
                pageNumber={currentPage}
                onLoadSuccess={onPageLoadSuccess}
                scale={scale}
                renderTextLayer={true}
                renderAnnotationLayer={true}
                className="shadow-lg"
              />
            </Document>
            {pageDimensions && (
              <canvas
                ref={canvasRef}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
                className="absolute top-0 left-0 cursor-crosshair"
                style={{
                  width: pageDimensions.width * scale,
                  height: pageDimensions.height * scale,
                  touchAction: 'none',
                  zIndex: 10,
                }}
                width={pageDimensions.width * scale}
                height={pageDimensions.height * scale}
              />
            )}
          </div>
        </div>

        {/* Detected regions indicator */}
        {editedRegions.length > 0 && (() => {
          const currentPageRegions = editedRegions.filter((r) => r.page === currentPage);
          return (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-slate-800/95 backdrop-blur-sm px-4 py-2 rounded-lg border border-slate-600 z-10">
            <div className="text-xs text-slate-300">
              <span className="font-semibold text-emerald-400">{currentPageRegions.length}</span>{" "}
              {currentPageRegions.length === 1 ? 'region' : 'regions'} detected on page {currentPage}
            </div>
          </div>
          );
        })()}

        {/* Drawing hint - positioned to avoid overlap */}
        <div className="absolute bottom-20 left-1/2 -translate-x-1/2 bg-slate-800/90 backdrop-blur-sm px-3 py-2 rounded-md border border-slate-600 z-10">
          <p className="text-xs text-slate-300">
            {selectedRegion 
              ? 'Edit region: drag to move, resize handles, or delete' 
              : 'Click to edit region • Cmd/Ctrl+Click to toggle extraction • Drag to draw new'}
          </p>
        </div>

        {/* Region Edit Controls */}
        {selectedRegion && (() => {
          const region = editedRegions.find(r => r.region_id === selectedRegion);
          if (!region || region.page !== currentPage) return null;
          
          return (
            <div className="absolute top-16 right-4 bg-slate-800/95 backdrop-blur-sm px-4 py-3 rounded-lg border border-slate-600 shadow-lg z-20 space-y-2">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-medium text-slate-300">Region Type:</span>
                <select
                  value={region.region_type}
                  onChange={(e) => handleRegionTypeChange(selectedRegion, e.target.value)}
                  className="text-xs bg-slate-700 text-slate-200 border border-slate-600 rounded px-2 py-1 focus:outline-none focus:border-blue-500"
                >
                  <option value="TABLE">TABLE</option>
                  <option value="HEADING">HEADING</option>
                  <option value="LIST">LIST</option>
                  <option value="TEXT">TEXT</option>
                  <option value="NONE" className="text-slate-500">NONE (False Positive)</option>
                </select>
              </div>
              
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <span>Confidence:</span>
                <span className="font-mono text-slate-300">{Math.round(region.confidence * 100)}%</span>
              </div>
              
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <span>Size:</span>
                <span className="font-mono text-slate-300">
                  {Math.round(region.bbox.w * 100)}% × {Math.round(region.bbox.h * 100)}%
                </span>
              </div>
              
              <div className="border-t border-slate-600 my-2 pt-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedForExtraction.has(selectedRegion)}
                    onChange={() => toggleExtractionSelection(selectedRegion)}
                    className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-0"
                  />
                  <span className="text-xs text-slate-300 font-medium">
                    Include in Extraction
                  </span>
                </label>
              </div>
              
              <button
                onClick={() => handleRegionDelete(selectedRegion)}
                className="w-full mt-2 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-xs font-medium rounded transition flex items-center justify-center gap-1"
              >
                <span>×</span>
                Delete Region
              </button>
            </div>
          );
        })()}



        {/* Integrated Page Navigation */}
        <div className="absolute bottom-4 left-4 right-4 flex items-center justify-between z-10">
          <button
            onClick={() => onPageChange(Math.max(1, currentPage - 1))}
            disabled={currentPage === 1}
            className="px-3 py-2 bg-slate-800/90 backdrop-blur-sm border border-slate-600 rounded-lg text-slate-300 hover:text-white hover:border-slate-500 transition disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
          >
            ← Previous
          </button>

          <div className="bg-slate-800/90 backdrop-blur-sm px-4 py-2 rounded-lg border border-slate-600">
            <span className="text-slate-300 text-sm font-medium">
              Page{" "}
              <span className="text-white tabular-nums">{currentPage}</span> of{" "}
              <span className="text-slate-400 tabular-nums">{numPages}</span>
            </span>
          </div>

          <button
            onClick={() => onPageChange(Math.min(numPages, currentPage + 1))}
            disabled={currentPage === numPages}
            className="px-3 py-2 bg-slate-800/90 backdrop-blur-sm border border-slate-600 rounded-lg text-slate-300 hover:text-white hover:border-slate-500 transition disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
          >
            Next →
          </button>
        </div>
      </div>
    </div>
  );
}
