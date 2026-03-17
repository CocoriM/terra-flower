"use client";

import dynamic from "next/dynamic";
import Navbar from "@/components/Navbar";
import SearchBar from "@/components/SearchBar";
import FilterBar from "@/components/FilterBar";
import PlantDetailDrawer from "@/components/PlantDetailDrawer";
import UploadModal from "@/components/UploadModal";

const CesiumGlobe = dynamic(() => import("@/components/CesiumGlobe"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center bg-black">
      <div className="text-white text-lg">Loading globe...</div>
    </div>
  ),
});

export default function GlobePage() {
  return (
    <main className="w-screen h-screen overflow-hidden bg-black">
      <Navbar />
      <FilterBar />
      <SearchBar />
      <CesiumGlobe />
      <PlantDetailDrawer />
      <UploadModal />
    </main>
  );
}
