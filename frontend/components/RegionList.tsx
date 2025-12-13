'use client';

import { Region } from '@/types/api';
import { X } from 'lucide-react';

interface RegionListProps {
  regions: Region[];
  onRemove: (index: number) => void;
  onLabelChange: (index: number, label: string) => void;
}

export default function RegionList({ regions, onRemove, onLabelChange }: RegionListProps) {
  if (regions.length === 0) {
    return (
      <div className="text-center text-gray-500 py-8">
        No regions selected yet. Draw regions on the PDF to get started.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <h3 className="text-lg font-semibold mb-3">Selected Regions ({regions.length})</h3>
      {regions.map((region, index) => (
        <div
          key={index}
          className="flex items-center justify-between p-3 bg-gray-50 rounded border border-gray-200"
        >
          <div className="flex-1">
            <div className="flex items-center space-x-2">
              <span className="font-semibold text-blue-600">#{index + 1}</span>
              <span className="text-sm text-gray-600">
                Page {region.page} • {Math.round(region.width)}x{Math.round(region.height)}px
              </span>
            </div>
            <input
              type="text"
              placeholder="Add label (optional)"
              value={region.label || ''}
              onChange={(e) => onLabelChange(index, e.target.value)}
              className="mt-1 text-sm w-full px-2 py-1 border border-gray-300 rounded"
            />
          </div>
          <button
            onClick={() => onRemove(index)}
            className="ml-3 p-1 text-red-500 hover:bg-red-50 rounded"
          >
            <X size={18} />
          </button>
        </div>
      ))}
    </div>
  );
}
