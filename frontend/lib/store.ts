import { create } from "zustand";
import type { Plant, OccurrencePoint, User } from "./types";

interface AppState {
  selectedPlantType: "all" | "flower" | "tree" | "grass";
  setPlantType: (type: "all" | "flower" | "tree" | "grass") => void;
  plants: Plant[];
  setPlants: (plants: Plant[]) => void;
  occurrences: OccurrencePoint[];
  setOccurrences: (points: OccurrencePoint[]) => void;
  appendOccurrences: (points: OccurrencePoint[]) => void;
  selectedPlant: Plant | null;
  setSelectedPlant: (plant: Plant | null) => void;
  isUploadModalOpen: boolean;
  openUploadModal: () => void;
  closeUploadModal: () => void;
  user: User | null;
  setUser: (user: User | null) => void;
  accessToken: string | null;
  setAccessToken: (token: string | null) => void;
}

export const useStore = create<AppState>((set) => ({
  selectedPlantType: "all",
  setPlantType: (type) => set({ selectedPlantType: type }),
  plants: [],
  setPlants: (plants) => set({ plants }),
  occurrences: [],
  setOccurrences: (points) => set({ occurrences: points }),
  appendOccurrences: (points) =>
    set((state) => ({ occurrences: [...state.occurrences, ...points] })),
  selectedPlant: null,
  setSelectedPlant: (plant) => set({ selectedPlant: plant }),
  isUploadModalOpen: false,
  openUploadModal: () => set({ isUploadModalOpen: true }),
  closeUploadModal: () => set({ isUploadModalOpen: false }),
  user: null,
  setUser: (user) => set({ user }),
  accessToken: null,
  setAccessToken: (token) => set({ accessToken: token }),
}));
