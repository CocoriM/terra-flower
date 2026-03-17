import axios from "axios";
import { useStore } from "./store";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api",
});

api.interceptors.request.use((config) => {
  const token = useStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export async function fetchGlobeMarkers(params?: {
  type?: string;
  continent?: string;
}) {
  const { data } = await api.get("/globe/markers", { params });
  return data;
}

export async function fetchPlants(params: {
  type?: string;
  search?: string;
  continent?: string;
  page?: number;
  per_page?: number;
}) {
  const { data } = await api.get("/plants", { params });
  return data;
}

export async function fetchPlantDetail(plantId: string) {
  const { data } = await api.get(`/plants/${plantId}`);
  return data;
}

export async function fetchDistributions(plantId: string, limit?: number) {
  const params: Record<string, any> = {};
  if (limit) params.limit = limit;
  const { data } = await api.get(`/plants/${plantId}/distributions`, {
    params: Object.keys(params).length > 0 ? params : undefined,
  });
  return data;
}

export async function fetchGallery(plantId: string, page = 1) {
  const { data } = await api.get(`/plants/${plantId}/gallery`, {
    params: { page },
  });
  return data;
}

export async function uploadPhoto(formData: FormData) {
  const { data } = await api.post("/uploads", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function confirmUpload(uploadId: string, confirmedPlantId: string) {
  const { data } = await api.post(`/uploads/${uploadId}/confirm`, {
    confirmed_plant_id: confirmedPlantId,
  });
  return data;
}

export async function fetchMyUploads(page = 1) {
  const { data } = await api.get("/uploads/me", { params: { page } });
  return data;
}

export async function deleteUpload(id: string) {
  const { data } = await api.delete(`/uploads/${id}`);
  return data;
}

export async function fetchPendingUploads(page = 1) {
  const { data } = await api.get("/moderation/pending", { params: { page } });
  return data;
}

export async function approveUpload(id: string, reason?: string) {
  const { data } = await api.post(`/moderation/${id}/approve`, { reason });
  return data;
}

export async function rejectUpload(id: string, reason: string) {
  const { data } = await api.post(`/moderation/${id}/reject`, { reason });
  return data;
}

export async function login(email: string, password: string) {
  const { data } = await api.post("/auth/login", { email, password });
  return data;
}

export async function register(
  email: string,
  password: string,
  displayName: string
) {
  const { data } = await api.post("/auth/register", {
    email,
    password,
    display_name: displayName,
  });
  return data;
}

export async function fetchMe() {
  const { data } = await api.get("/auth/me");
  return data;
}

export default api;
