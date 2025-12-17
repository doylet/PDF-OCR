import { useState, useCallback } from 'react';
import { Region, DetectedRegion } from '@/types/api';

interface UseRegionManagementResult {
  detectedRegions: DetectedRegion[];
  approvedRegions: DetectedRegion[];
  currentPage: number;
  setCurrentPage: (page: number) => void;
  addRegion: (region: Region) => void;
  removeRegion: (regionId: string) => void;
  updateRegion: (region: DetectedRegion) => void;
  setDetectedRegions: (regions: DetectedRegion[]) => void;
  setApprovedRegions: (regions: DetectedRegion[]) => void;
  clearRegions: () => void;
}

export const useRegionManagement = (): UseRegionManagementResult => {
  const [detectedRegions, setDetectedRegions] = useState<DetectedRegion[]>([]);
  const [approvedRegions, setApprovedRegions] = useState<DetectedRegion[]>([]);
  const [currentPage, setCurrentPage] = useState(1);

  const addRegion = useCallback((region: Region) => {
    const newRegion: DetectedRegion = {
      region_id: `manual_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      region_type: "TABLE",
      bbox: {
        x: region.x,
        y: region.y,
        w: region.width,
        h: region.height,
      },
      page: region.page,
      confidence: 1.0,
    };
    setDetectedRegions(prev => [...prev, newRegion]);
  }, []);

  const removeRegion = useCallback((regionId: string) => {
    setDetectedRegions(prev => prev.filter(r => r.region_id !== regionId));
  }, []);

  const updateRegion = useCallback((updatedRegion: DetectedRegion) => {
    setDetectedRegions(prev =>
      prev.map(r => r.region_id === updatedRegion.region_id ? updatedRegion : r)
    );
  }, []);

  const clearRegions = useCallback(() => {
    setDetectedRegions([]);
    setApprovedRegions([]);
    setCurrentPage(1);
  }, []);

  return {
    detectedRegions,
    approvedRegions,
    currentPage,
    setCurrentPage,
    addRegion,
    removeRegion,
    updateRegion,
    setDetectedRegions,
    setApprovedRegions,
    clearRegions,
  };
};
