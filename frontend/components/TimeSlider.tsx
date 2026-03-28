"use client";

import { useStore } from "@/lib/store";

const MONTH_LABELS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export default function TimeSlider() {
  const currentMonth = useStore((s) => s.currentMonth);
  const setCurrentMonth = useStore((s) => s.setCurrentMonth);
  const showAllPlants = useStore((s) => s.showAllPlants);
  const setShowAllPlants = useStore((s) => s.setShowAllPlants);

  return (
    <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 flex flex-col items-center gap-2">
      {/* Month label */}
      <div className="bg-black/70 text-white px-4 py-1.5 rounded-full text-sm font-medium backdrop-blur-sm">
        {MONTH_LABELS[currentMonth - 1]}
      </div>

      {/* Slider + bloom toggle row */}
      <div className="bg-black/70 backdrop-blur-sm rounded-full px-5 py-3 flex items-center gap-4">
        <span className="text-white/60 text-xs w-8">Jan</span>
        <input
          type="range"
          min={1}
          max={12}
          step={1}
          value={currentMonth}
          onChange={(e) => setCurrentMonth(Number(e.target.value))}
          className="w-64 sm:w-80 accent-emerald-400 cursor-pointer"
        />
        <span className="text-white/60 text-xs w-8">Dec</span>

        {/* Bloom filter toggle */}
        <button
          onClick={() => setShowAllPlants(!showAllPlants)}
          className={`ml-2 px-3 py-1 rounded-full text-xs font-medium transition-colors ${
            showAllPlants
              ? "bg-white/20 text-white/80 hover:bg-white/30"
              : "bg-emerald-500 text-white hover:bg-emerald-600"
          }`}
        >
          {showAllPlants ? "Show all" : "Blooming now"}
        </button>
      </div>
    </div>
  );
}
