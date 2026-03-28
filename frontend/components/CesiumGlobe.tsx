"use client";

import { useEffect, useMemo, useState, useCallback, useRef } from "react";
import { useStore } from "@/lib/store";
import { fetchGlobeMarkers, fetchPlantDetail } from "@/lib/api";
import { createAurora, updateAuroraMonth } from "@/lib/aurora";
import type { AuroraHandle } from "@/lib/aurora";
import type { GlobeMarker } from "@/lib/types";

declare global {
  interface Window {
    Cesium: any;
  }
}

const TYPE_COLORS: Record<string, string> = {
  flower: "#F472B6",
  tree: "#34D399",
  grass: "#FBBF24",
};

export default function CesiumGlobe() {
  const selectedPlantType = useStore((s) => s.selectedPlantType);
  const markers = useStore((s) => s.markers);
  const setMarkers = useStore((s) => s.setMarkers);
  const setSelectedPlant = useStore((s) => s.setSelectedPlant);
  const currentMonth = useStore((s) => s.currentMonth);
  const showAllPlants = useStore((s) => s.showAllPlants);
  const [loading, setLoading] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);
  const entitiesRef = useRef<Map<string, any>>(new Map());
  const auroraRef = useRef<AuroraHandle | null>(null);

  // Initialize Cesium viewer
  useEffect(() => {
    const Cesium = window.Cesium;
    if (!Cesium || !containerRef.current) return;

    Cesium.Ion.defaultAccessToken =
      process.env.NEXT_PUBLIC_CESIUM_ION_TOKEN || "";

    const viewer = new Cesium.Viewer(containerRef.current, {
      timeline: false,
      animation: false,
      homeButton: false,
      geocoder: false,
      baseLayerPicker: false,
      navigationHelpButton: false,
      sceneModePicker: false,
      fullscreenButton: false,
      infoBox: false,
      selectionIndicator: false,
    });

    // 2a: Enable day/night cycle — sun position from Cesium clock
    viewer.scene.globe.enableLighting = true;

    // Set terrain asynchronously (createWorldTerrain removed in Cesium 1.107+)
    Cesium.createWorldTerrainAsync()
      .then((terrain: any) => {
        if (!viewer.isDestroyed()) {
          viewer.terrainProvider = terrain;
        }
      })
      .catch((err: any) => {
        console.error("[CesiumGlobe] Failed to load terrain:", err);
      });

    // Click handler
    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
    handler.setInputAction((click: any) => {
      const picked = viewer.scene.pick(click.position);
      if (Cesium.defined(picked) && picked.id && picked.id._plantMarker) {
        const marker = picked.id._plantMarker as GlobeMarker;
        handleMarkerClick(marker);
      }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

    // Enable trackpad pinch-to-zoom on Mac
    const controller = viewer.scene.screenSpaceCameraController;
    controller.enableZoom = true;
    controller.zoomEventTypes = [
      Cesium.CameraEventType.WHEEL,
      Cesium.CameraEventType.PINCH,
    ];
    controller.tiltEventTypes = [
      Cesium.CameraEventType.MIDDLE_DRAG,
      Cesium.CameraEventType.PINCH,
      {
        eventType: Cesium.CameraEventType.LEFT_DRAG,
        modifier: Cesium.KeyboardEventModifier.CTRL,
      },
    ];

    viewerRef.current = viewer;

    // Initialize aurora borealis / australis
    auroraRef.current = createAurora(viewer, currentMonth);

    return () => {
      if (auroraRef.current) {
        auroraRef.current.cleanup();
        auroraRef.current = null;
      }
      handler.destroy();
      if (!viewer.isDestroyed()) viewer.destroy();
      viewerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load markers from API
  useEffect(() => {
    let cancelled = false;

    async function loadMarkers() {
      try {
        const data = await fetchGlobeMarkers();
        if (!cancelled) {
          setMarkers(data.markers || []);
          setLoading(false);
        }
      } catch (err) {
        console.error("[CesiumGlobe] loadMarkers error:", err);
        if (!cancelled) setLoading(false);
      }
    }

    loadMarkers();
    return () => {
      cancelled = true;
    };
  }, [setMarkers]);

  // Sync Cesium clock with time slider month (for day/night lighting position)
  useEffect(() => {
    const Cesium = window.Cesium;
    const viewer = viewerRef.current;
    if (!Cesium || !viewer || viewer.isDestroyed()) return;

    // Set clock to the 15th of the selected month (mid-month) at noon UTC
    const date = new Date(2024, currentMonth - 1, 15, 12, 0, 0);
    viewer.clock.currentTime = Cesium.JulianDate.fromDate(date);
    viewer.clock.shouldAnimate = false;

    // Update aurora intensity for the new month
    if (auroraRef.current) {
      updateAuroraMonth(auroraRef.current, currentMonth);
    }
  }, [currentMonth]);

  // Filter markers by type and bloom season
  const filteredMarkers = useMemo(() => {
    let filtered = markers;
    if (selectedPlantType !== "all") {
      filtered = filtered.filter((m) => m.plant_type === selectedPlantType);
    }
    if (!showAllPlants) {
      filtered = filtered.filter(
        (m) => m.bloom_months && m.bloom_months.includes(currentMonth)
      );
    }
    return filtered;
  }, [markers, selectedPlantType, showAllPlants, currentMonth]);

  // Sync entities with filtered markers
  useEffect(() => {
    const Cesium = window.Cesium;
    const viewer = viewerRef.current;
    if (!Cesium || !viewer || viewer.isDestroyed()) return;

    // Remove all current marker entities
    entitiesRef.current.forEach((entity) => {
      viewer.entities.remove(entity);
    });
    entitiesRef.current.clear();

    // Add filtered markers
    for (const marker of filteredMarkers) {
      const color = Cesium.Color.fromCssColorString(
        TYPE_COLORS[marker.plant_type] || "#FFFFFF"
      );

      const entity = viewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(
          marker.lng,
          marker.lat,
          marker.elevation || 0
        ),
        point: {
          color: color,
          pixelSize: 10,
          outlineColor: Cesium.Color.WHITE,
          outlineWidth: 2,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
          scaleByDistance: new Cesium.NearFarScalar(1.5e2, 1.5, 1.5e7, 0.5),
        },
      });
      // Attach marker data for click handler
      (entity as any)._plantMarker = marker;
      entitiesRef.current.set(marker.plant_id, entity);
    }
  }, [filteredMarkers]);

  // Handle marker click
  const handleMarkerClick = useCallback(
    async (marker: GlobeMarker) => {
      try {
        const detail = await fetchPlantDetail(marker.plant_id);
        setSelectedPlant(detail);
      } catch {
        setSelectedPlant({
          id: marker.plant_id,
          common_name: marker.common_name,
          common_name_zh: null,
          scientific_name: "",
          plant_type: marker.plant_type,
          family: "",
          genus: "",
          description: null,
          habitat: null,
          hero_image_url: marker.hero_image_url,
          hero_image_attribution: null,
          distribution_count: marker.occurrence_count,
        });
      }
    },
    [setSelectedPlant]
  );

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
      <div ref={containerRef} className="w-full h-full" style={{ touchAction: "none" }} />
    </div>
  );
}
