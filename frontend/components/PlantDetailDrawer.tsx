"use client";

import { useEffect, useState } from "react";
import { useStore } from "@/lib/store";
import { fetchPlantDetail } from "@/lib/api";
import PlantGallery from "./PlantGallery";
import UploadButton from "./UploadButton";

const TYPE_BADGE: Record<string, string> = {
  flower: "bg-pink-100 text-pink-800",
  tree: "bg-emerald-100 text-emerald-800",
  grass: "bg-yellow-100 text-yellow-800",
};

export default function PlantDetailDrawer() {
  const selectedPlant = useStore((s) => s.selectedPlant);
  const setSelectedPlant = useStore((s) => s.setSelectedPlant);
  const [detail, setDetail] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selectedPlant) {
      setDetail(null);
      return;
    }

    let cancelled = false;
    setLoading(true);

    fetchPlantDetail(selectedPlant.trefle_id)
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedPlant]);

  if (!selectedPlant) return null;

  const plant = detail || selectedPlant;

  return (
    <div
      role="dialog"
      aria-label="Plant details"
      className="fixed right-0 top-0 h-full w-[420px] max-md:w-full max-md:h-[80vh] max-md:bottom-0 max-md:top-auto max-md:rounded-t-2xl bg-white shadow-2xl z-40 overflow-y-auto"
    >
      {/* Close button */}
      <button
        onClick={() => setSelectedPlant(null)}
        className="absolute top-3 right-3 z-10 w-8 h-8 flex items-center justify-center rounded-full bg-black/30 text-white hover:bg-black/50"
        aria-label="Close plant details"
      >
        &times;
      </button>

      {loading ? (
        <div className="p-6 space-y-4 animate-pulse">
          <div className="h-48 bg-gray-200 rounded" />
          <div className="h-6 bg-gray-200 rounded w-3/4" />
          <div className="h-4 bg-gray-200 rounded w-1/2" />
          <div className="h-20 bg-gray-200 rounded" />
        </div>
      ) : (
        <>
          {/* Hero image */}
          {plant.image_url && (
            <img
              src={plant.image_url}
              alt={plant.common_name || plant.scientific_name}
              className="h-48 w-full object-cover"
            />
          )}

          <div className="p-6 space-y-4">
            {/* Name */}
            <div>
              <h2 className="text-2xl font-bold text-gray-900">
                {plant.common_name || plant.scientific_name}
              </h2>
              {plant.common_name && (
                <p className="text-sm italic text-gray-500">
                  {plant.scientific_name}
                </p>
              )}
            </div>

            {/* Type badge */}
            <span
              className={`inline-block px-3 py-1 rounded-full text-xs font-medium ${TYPE_BADGE[plant.plant_type] || "bg-gray-100 text-gray-800"}`}
            >
              {plant.plant_type}
            </span>

            {/* Regions */}
            {plant.native_regions && plant.native_regions.length > 0 && (
              <p className="text-sm text-gray-600">
                <span className="font-medium">Native to:</span>{" "}
                {plant.native_regions.join(", ")}
              </p>
            )}

            {/* Description */}
            {plant.description && (
              <p className="text-sm text-gray-700 leading-relaxed">
                {plant.description}
              </p>
            )}

            <hr className="border-gray-200" />

            {/* Gallery */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">
                Community Photos
              </h3>
              <PlantGallery trefleId={plant.trefle_id} />
            </div>

            <UploadButton />
          </div>
        </>
      )}
    </div>
  );
}
