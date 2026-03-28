import { create } from "zustand";
import type { Plant, GlobeMarker, AIResult, User } from "./types";

interface AppState {
  selectedPlantType: "all" | "flower" | "tree" | "grass";
  setPlantType: (type: "all" | "flower" | "tree" | "grass") => void;
  markers: GlobeMarker[];
  setMarkers: (markers: GlobeMarker[]) => void;
  currentMonth: number; // 1–12
  setCurrentMonth: (month: number) => void;
  showAllPlants: boolean; // true = ignore bloom filter
  setShowAllPlants: (show: boolean) => void;
  selectedPlant: Plant | null;
  setSelectedPlant: (plant: Plant | null) => void;
  isUploadModalOpen: boolean;
  openUploadModal: () => void;
  closeUploadModal: () => void;
  identificationResults: AIResult[] | null;
  setIdentificationResults: (results: AIResult[] | null) => void;
  user: User | null;
  setUser: (user: User | null) => void;
  accessToken: string | null;
  setAccessToken: (token: string | null) => void;
}

export const useStore = create<AppState>((set) => ({
  selectedPlantType: "all",
  setPlantType: (type) => set({ selectedPlantType: type }),
  markers: [],
  setMarkers: (markers) => set({ markers }),
  currentMonth: new Date().getMonth() + 1, // default to current month
  setCurrentMonth: (month) => set({ currentMonth: month }),
  showAllPlants: true, // default: show all, not just blooming
  setShowAllPlants: (show) => set({ showAllPlants: show }),
  selectedPlant: null,
  setSelectedPlant: (plant) => set({ selectedPlant: plant }),
  isUploadModalOpen: false,
  openUploadModal: () => set({ isUploadModalOpen: true }),
  closeUploadModal: () => set({ isUploadModalOpen: false, identificationResults: null }),
  identificationResults: null,
  setIdentificationResults: (results) => set({ identificationResults: results }),
  user: null,
  setUser: (user) => set({ user }),
  accessToken: null,
  setAccessToken: (token) => set({ accessToken: token }),
}));
