"use client";

import { useRef } from "react";
import Navbar from "@/components/Navbar";
import SearchBar from "@/components/SearchBar";
import GlobeComponent from "@/components/Globe";
import PlantDetailDrawer from "@/components/PlantDetailDrawer";
import UploadModal from "@/components/UploadModal";

export default function GlobePage() {
  const globeRef = useRef<any>(null);

  return (
    <main className="w-screen h-screen overflow-hidden bg-black">
      <Navbar />
      <SearchBar globeRef={globeRef} />
      <GlobeComponent globeRef={globeRef} />
      <PlantDetailDrawer />
      <UploadModal />
    </main>
  );
}
