"use client";

import { useStore } from "@/lib/store";

const filters = [
  { key: "all" as const, label: "All", color: "bg-gray-500" },
  { key: "flower" as const, label: "Flowers", color: "bg-pink-400" },
  { key: "tree" as const, label: "Trees", color: "bg-emerald-400" },
  { key: "grass" as const, label: "Grass", color: "bg-yellow-400" },
] as const;

export default function FilterBar() {
  const selectedPlantType = useStore((s) => s.selectedPlantType);
  const setPlantType = useStore((s) => s.setPlantType);

  return (
    <div
      className="fixed top-16 left-1/2 -translate-x-1/2 z-40 flex gap-2 bg-black/30 backdrop-blur-sm rounded-full px-4 py-2"
      role="group"
      aria-label="Plant type filter"
    >
      {filters.map((f) => (
        <button
          key={f.key}
          onClick={() => setPlantType(f.key)}
          aria-pressed={selectedPlantType === f.key}
          className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
            selectedPlantType === f.key
              ? `${f.color} text-white`
              : "text-white/80 hover:text-white"
          }`}
        >
          {f.label}
        </button>
      ))}
    </div>
  );
}
