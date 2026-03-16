"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { fetchPlants, fetchOccurrences } from "@/lib/api";
import { useStore } from "@/lib/store";
import type { Plant, OccurrencePoint } from "@/lib/types";

interface SearchBarProps {
  globeRef: React.MutableRefObject<any>;
}

export default function SearchBar({ globeRef }: SearchBarProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Plant[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const setOccurrences = useStore((s) => s.setOccurrences);
  const setSelectedPlant = useStore((s) => s.setSelectedPlant);
  const occurrences = useStore((s) => s.occurrences);

  const handleSearch = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults([]);
      setIsOpen(false);
      return;
    }
    try {
      const data = await fetchPlants({ search: q, per_page: 8 });
      setResults(data.plants || []);
      setIsOpen(true);
    } catch {
      setResults([]);
    }
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => handleSearch(val), 300);
  };

  const handleSelect = async (plant: Plant) => {
    setQuery(plant.common_name || plant.scientific_name);
    setIsOpen(false);
    setSelectedPlant(plant);

    try {
      const occData = await fetchOccurrences(plant.trefle_id);
      const points: OccurrencePoint[] = (occData.occurrences || []).map(
        (o: any) => ({
          ...o,
          trefle_id: plant.trefle_id,
          plant_type: plant.plant_type,
          plant_name: plant.common_name || plant.scientific_name,
        })
      );
      setOccurrences([...occurrences, ...points]);

      if (points.length > 0 && globeRef.current) {
        globeRef.current.pointOfView(
          { lat: points[0].lat, lng: points[0].lng, altitude: 1.5 },
          1000
        );
      }
    } catch {
      // occurrence data unavailable
    }
  };

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  return (
    <div className="fixed top-16 left-4 z-40 w-72">
      <input
        type="text"
        value={query}
        onChange={handleChange}
        placeholder="Search plants..."
        className="w-full px-4 py-2 rounded-lg bg-black/30 backdrop-blur-sm text-white placeholder-white/60 border border-white/20 focus:outline-none focus:border-white/50"
        aria-label="Search plants"
      />
      {isOpen && results.length > 0 && (
        <ul className="mt-1 bg-white rounded-lg shadow-lg overflow-hidden max-h-64 overflow-y-auto">
          {results.map((plant) => (
            <li key={plant.trefle_id}>
              <button
                onClick={() => handleSelect(plant)}
                className="w-full px-4 py-2 text-left hover:bg-gray-100 text-sm"
              >
                <span className="font-medium text-gray-900">
                  {plant.common_name || plant.scientific_name}
                </span>
                <span className="block text-xs text-gray-500 italic">
                  {plant.scientific_name}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
