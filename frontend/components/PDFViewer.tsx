"use client";

import React, { useState, useRef, useEffect, useMemo } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { Region } from "@/types/api";
import { FileText, Brain } from "lucide-react";
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

interface PDFViewerProps {
  file: File | null;
  regions: Region[];
  onRegionAdd: (region: Region) => void;
  onRegionRemove: (index: number) => void;
  currentPage: number;
  onPageChange: (page: number) => void;
  detectedRegions?: DetectedRegion[];
}



export default function PDFViewer({
  file,
  regions,
  onRegionAdd,
  currentPage,
  onPageChange,
  detectedRegions = [],
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

    setIsDrawing(true);
    setStartPoint({ x, y });
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing || !startPoint) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const width = x - startPoint.x;
    const height = y - startPoint.y;

    setCurrentRect({
      x: Math.min(startPoint.x, x),
      y: Math.min(startPoint.y, y),
      width: Math.abs(width),
      height: Math.abs(height),
      page: currentPage,
    });
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
    setIsDrawing(false);
    setStartPoint(null);
    setCurrentRect(null);
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !pageDimensions) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw detected regions (agentic) for current page
    const pageDetectedRegions = detectedRegions.filter(
      (r) => r.page === currentPage
    );
    pageDetectedRegions.forEach((region) => {
      // Convert from normalized fractions (0-1) to canvas pixels
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
          : "#8b5cf6";

      ctx.strokeStyle = color;
      ctx.fillStyle = `${color}33`; // 20% opacity
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 5]); // Dashed line for detected regions
      ctx.fillRect(canvasX, canvasY, canvasWidth, canvasHeight);
      ctx.strokeRect(canvasX, canvasY, canvasWidth, canvasHeight);
      ctx.setLineDash([]); // Reset

      // Draw region type label
      ctx.fillStyle = color;
      ctx.font = "bold 12px Arial";
      ctx.fillText(
        `${region.region_type} (${Math.round(region.confidence * 100)}%)`,
        canvasX + 5,
        canvasY + 15
      );
    });

    // Draw existing manual regions for current page
    const pageRegions = regions.filter((r) => r.page === currentPage);
    pageRegions.forEach((region, index) => {
      // Convert from normalized fractions (0-1) to canvas pixels
      const canvasX = region.x * canvas.width;
      const canvasY = region.y * canvas.height;
      const canvasWidth = region.width * canvas.width;
      const canvasHeight = region.height * canvas.height;

      ctx.strokeStyle = "#3b82f6";
      ctx.fillStyle = "rgba(59, 130, 246, 0.2)";
      ctx.lineWidth = 2;
      ctx.fillRect(canvasX, canvasY, canvasWidth, canvasHeight);
      ctx.strokeRect(canvasX, canvasY, canvasWidth, canvasHeight);

      // Draw region number
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
  }, [regions, detectedRegions, currentRect, currentPage, pageDimensions]);

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

        {/* Overlay for regions */}
        {regions.length > 0 && (
          <div className="absolute top-4 left-4 bg-slate-800/90 backdrop-blur-sm px-3 py-2 rounded-md border border-slate-600 z-10">
            <p className="text-xs text-slate-300">
              {regions.length} region{regions.length !== 1 ? "s" : ""} selected
            </p>
          </div>
        )}

        {/* Detected regions indicator */}
        {detectedRegions.length > 0 && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-green-500/20 backdrop-blur-sm px-3 py-2 rounded-md border border-green-400/50 z-10">
            <p className="text-xs text-green-300">
              {detectedRegions.filter((r) => r.page === currentPage).length}{" "}
              detected on page {currentPage}
            </p>
          </div>
        )}

        {/* Drawing hint */}
        <div className="absolute top-4 right-4 bg-slate-800/90 backdrop-blur-sm px-3 py-2 rounded-md border border-slate-600 z-10">
          <p className="text-xs text-slate-300">Click & drag to draw regions</p>
        </div>

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
