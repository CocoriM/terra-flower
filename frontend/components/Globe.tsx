"use client";

import { useEffect, useMemo, useState, useCallback, useRef } from "react";
import dynamic from "next/dynamic";
import { useStore } from "@/lib/store";
import { fetchPlants, fetchOccurrences, fetchPlantDetail } from "@/lib/api";
import type { OccurrencePoint, Plant } from "@/lib/types";

const ReactGlobe = dynamic(() => import("react-globe.gl"), { ssr: false });

const TYPE_COLORS: Record<string, string> = {
  flower: "#F472B6",
  tree: "#34D399",
  grass: "#FBBF24",
};

const CONCURRENCY = 8;

// Diverse search queries to get global plant coverage
const REGION_QUERIES = [
  "",            // default listing (European plants)
  "eucalyptus",  // Australia, Mediterranean
  "acacia",      // Africa, Australia
  "maple",       // North America, East Asia
  "bamboo",      // Southeast Asia
  "cactus",      // Americas (arid regions)
  "palm",        // Tropics worldwide
  "protea",      // South Africa
];

interface GlobeComponentProps {
  globeRef: React.MutableRefObject<any>;
}

export default function GlobeComponent({ globeRef }: GlobeComponentProps) {
  const selectedPlantType = useStore((s) => s.selectedPlantType);
  const occurrences = useStore((s) => s.occurrences);
  const setPlants = useStore((s) => s.setPlants);
  const setOccurrences = useStore((s) => s.setOccurrences);
  const appendOccurrences = useStore((s) => s.appendOccurrences);
  const setSelectedPlant = useStore((s) => s.setSelectedPlant);
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState("");
  const clickHandlerRef = useRef<(d: any) => void>(() => {});
  const loadedCountRef = useRef(0);
  const totalCountRef = useRef(0);

  clickHandlerRef.current = async (d: any) => {
    try {
      const detail = await fetchPlantDetail(d.trefle_id);
      setSelectedPlant(detail);
    } catch {
      // could not fetch detail
    }
  };

  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      // Clear stale data from previous HMR / navigation
      setOccurrences([]);
      loadedCountRef.current = 0;

      try {
        setProgress("Fetching plant list...");

        // Fetch plants from diverse regions for global coverage
        const searchResults = await Promise.allSettled(
          REGION_QUERIES.map((q) =>
            fetchPlants(q ? { search: q, per_page: 10 } : { per_page: 20 })
          )
        );

        // Deduplicate by trefle_id
        const seen = new Set<number>();
        const allPlants: Plant[] = [];
        for (const r of searchResults) {
          if (r.status !== "fulfilled") continue;
          for (const p of r.value.plants || []) {
            if (!seen.has(p.trefle_id)) {
              seen.add(p.trefle_id);
              allPlants.push(p);
            }
          }
        }

        if (cancelled || allPlants.length === 0) return;
        setPlants(allPlants);
        setLoading(false);
        totalCountRef.current = allPlants.length;
        setProgress(`Loading locations: 0/${allPlants.length}`);

        // Fetch occurrences with concurrency control
        let idx = 0;
        const worker = async () => {
          while (idx < allPlants.length) {
            if (cancelled) return;
            const cur = idx++;
            const plant = allPlants[cur];
            try {
              const occ = await fetchOccurrences(
                plant.trefle_id,
                plant.scientific_name,
                20
              );
              if (cancelled) return;
              const pts: OccurrencePoint[] = (occ.occurrences || []).map(
                (o: any) => ({
                  lat: o.lat,
                  lng: o.lng,
                  country: o.country,
                  year: o.year,
                  trefle_id: plant.trefle_id,
                  plant_type: plant.plant_type,
                  plant_name: plant.common_name || plant.scientific_name,
                  image_url: plant.image_url,
                })
              );
              if (pts.length > 0) appendOccurrences(pts);
            } catch {
              // skip failed
            }
            loadedCountRef.current++;
            setProgress(
              `Loading locations: ${loadedCountRef.current}/${totalCountRef.current}`
            );
          }
        };
        await Promise.all(Array.from({ length: CONCURRENCY }, () => worker()));
        if (!cancelled) setProgress("");
      } catch (err) {
        console.error("[Globe] loadData error:", err);
        if (!cancelled) {
          setLoading(false);
          setProgress("");
        }
      }
    }

    loadData();
    return () => {
      cancelled = true;
    };
  }, [setPlants, setOccurrences, appendOccurrences]);

  const filteredPoints = useMemo(() => {
    if (selectedPlantType === "all") return occurrences;
    return occurrences.filter((p) => p.plant_type === selectedPlantType);
  }, [occurrences, selectedPlantType]);

  // One thumbnail per plant species (at first occurrence location)
  const thumbnailMarkers = useMemo(() => {
    const seen = new Set<number>();
    const markers: OccurrencePoint[] = [];
    for (const p of filteredPoints) {
      if (!seen.has(p.trefle_id)) {
        seen.add(p.trefle_id);
        markers.push(p);
      }
    }
    return markers;
  }, [filteredPoints]);

  const createMarkerElement = useCallback((d: any) => {
    const wrapper = document.createElement("div");
    wrapper.style.cursor = "pointer";
    wrapper.style.pointerEvents = "auto";
    wrapper.style.width = "36px";
    wrapper.style.height = "36px";
    wrapper.style.transform = "translate(-18px, -18px)";

    const borderColor = TYPE_COLORS[d.plant_type] || "#F472B6";

    if (d.image_url) {
      const img = document.createElement("img");
      img.src = d.image_url;
      img.alt = d.plant_name;
      img.style.width = "32px";
      img.style.height = "32px";
      img.style.borderRadius = "50%";
      img.style.objectFit = "cover";
      img.style.border = `2px solid ${borderColor}`;
      img.style.boxShadow = "0 2px 8px rgba(0,0,0,0.5)";
      img.style.backgroundColor = "#222";
      img.style.pointerEvents = "none";
      wrapper.appendChild(img);
    } else {
      const circle = document.createElement("div");
      circle.style.width = "32px";
      circle.style.height = "32px";
      circle.style.borderRadius = "50%";
      circle.style.backgroundColor = borderColor;
      circle.style.border = "2px solid white";
      circle.style.display = "flex";
      circle.style.alignItems = "center";
      circle.style.justifyContent = "center";
      circle.style.color = "white";
      circle.style.fontSize = "14px";
      circle.style.fontWeight = "bold";
      circle.style.boxShadow = "0 2px 8px rgba(0,0,0,0.5)";
      circle.style.pointerEvents = "none";
      circle.textContent = (d.plant_name || "?")[0].toUpperCase();
      wrapper.appendChild(circle);
    }

    wrapper.addEventListener("click", (e) => {
      e.stopPropagation();
      clickHandlerRef.current(d);
    });

    return wrapper;
  }, []);

  return (
    <div className="w-full h-full relative">
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/50 z-10">
          <div className="text-white text-lg flex items-center gap-3">
            <svg
              className="animate-spin h-6 w-6"
              viewBox="0 0 24 24"
              fill="none"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
            Loading globe...
          </div>
        </div>
      )}

      {/* Progress indicator */}
      {progress && !loading && (
        <div className="absolute top-20 left-1/2 -translate-x-1/2 z-10 bg-black/60 text-white text-sm px-4 py-2 rounded-full">
          {progress} · {thumbnailMarkers.length} species on globe
        </div>
      )}

      <ReactGlobe
        ref={globeRef}
        globeImageUrl="//unpkg.com/three-globe/example/img/earth-blue-marble.jpg"
        backgroundImageUrl="//unpkg.com/three-globe/example/img/night-sky.png"
        htmlElementsData={thumbnailMarkers}
        htmlLat="lat"
        htmlLng="lng"
        htmlAltitude={0.02}
        htmlElement={createMarkerElement}
        width={typeof window !== "undefined" ? window.innerWidth : 1000}
        height={typeof window !== "undefined" ? window.innerHeight : 800}
      />
    </div>
  );
}
