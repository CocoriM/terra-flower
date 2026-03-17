"use client";

import { useEffect, useState } from "react";
import { fetchGallery } from "@/lib/api";

interface GalleryItem {
  id: string;
  image_url: string;
  thumbnail_url: string;
}

export default function PlantGallery({ plantId }: { plantId: string }) {
  const [items, setItems] = useState<GalleryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchGallery(plantId)
      .then((data) => {
        if (!cancelled) setItems(data.items || []);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [plantId]);

  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-2">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="aspect-square bg-gray-200 rounded animate-pulse"
          />
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <p className="text-sm text-gray-500 text-center py-4">
        No community photos yet. Be the first to upload!
      </p>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-2">
      {items.map((item) => (
        <img
          key={item.id}
          src={item.thumbnail_url || item.image_url}
          alt="Plant photo"
          className="aspect-square object-cover rounded"
        />
      ))}
    </div>
  );
}
