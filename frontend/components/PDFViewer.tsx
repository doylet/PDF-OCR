'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { Region } from '@/types/api';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface PDFViewerProps {
  file: File | null;
  regions: Region[];
  onRegionAdd: (region: Region) => void;
  onRegionRemove: (index: number) => void;
  currentPage: number;
  onPageChange: (page: number) => void;
}

export default function PDFViewer({
  file,
  regions,
  onRegionAdd,
  onRegionRemove,
  currentPage,
  onPageChange,
}: PDFViewerProps) {
  const [numPages, setNumPages] = useState<number>(0);
  const [isDrawing, setIsDrawing] = useState(false);
  const [startPoint, setStartPoint] = useState<{ x: number; y: number } | null>(null);
  const [currentRect, setCurrentRect] = useState<Region | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1.0);

  function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
    setNumPages(numPages);
    onPageChange(1);
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
    if (currentRect && currentRect.width > 10 && currentRect.height > 10) {
      onRegionAdd(currentRect);
    }
    setIsDrawing(false);
    setStartPoint(null);
    setCurrentRect(null);
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw existing regions for current page
    const pageRegions = regions.filter((r) => r.page === currentPage);
    pageRegions.forEach((region, index) => {
      ctx.strokeStyle = '#3b82f6';
      ctx.fillStyle = 'rgba(59, 130, 246, 0.2)';
      ctx.lineWidth = 2;
      ctx.fillRect(region.x, region.y, region.width, region.height);
      ctx.strokeRect(region.x, region.y, region.width, region.height);

      // Draw region number
      ctx.fillStyle = '#3b82f6';
      ctx.font = 'bold 16px Arial';
      ctx.fillText(`#${index + 1}`, region.x + 5, region.y + 20);
    });

    // Draw current drawing rectangle
    if (currentRect) {
      ctx.strokeStyle = '#10b981';
      ctx.fillStyle = 'rgba(16, 185, 129, 0.2)';
      ctx.lineWidth = 2;
      ctx.fillRect(currentRect.x, currentRect.y, currentRect.width, currentRect.height);
      ctx.strokeRect(currentRect.x, currentRect.y, currentRect.width, currentRect.height);
    }
  }, [regions, currentRect, currentPage]);

  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= numPages) {
      onPageChange(newPage);
    }
  };

  return (
    <div className="flex flex-col items-center space-y-4">
      {file && (
        <>
          <div className="flex items-center space-x-4 mb-4">
            <button
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage <= 1}
              className="px-4 py-2 bg-blue-500 text-white rounded disabled:bg-gray-300 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <span className="text-sm">
              Page {currentPage} of {numPages}
            </span>
            <button
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage >= numPages}
              className="px-4 py-2 bg-blue-500 text-white rounded disabled:bg-gray-300 disabled:cursor-not-allowed"
            >
              Next
            </button>
            <div className="flex items-center space-x-2">
              <button
                onClick={() => setScale(Math.max(0.5, scale - 0.1))}
                className="px-3 py-1 bg-gray-200 rounded"
              >
                -
              </button>
              <span className="text-sm">{Math.round(scale * 100)}%</span>
              <button
                onClick={() => setScale(Math.min(2.0, scale + 0.1))}
                className="px-3 py-1 bg-gray-200 rounded"
              >
                +
              </button>
            </div>
          </div>

          <div ref={containerRef} className="relative border-2 border-gray-300 rounded shadow-lg">
            <Document file={file} onLoadSuccess={onDocumentLoadSuccess}>
              <Page
                pageNumber={currentPage}
                scale={scale}
                renderTextLayer={false}
                renderAnnotationLayer={false}
              />
            </Document>
            <canvas
              ref={canvasRef}
              className="absolute top-0 left-0 cursor-crosshair"
              style={{
                width: `${800 * scale}px`,
                height: `${1035 * scale}px`,
              }}
              width={800 * scale}
              height={1035 * scale}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
            />
          </div>

          <div className="text-sm text-gray-600">
            Click and drag on the PDF to select regions for extraction
          </div>
        </>
      )}
    </div>
  );
}
