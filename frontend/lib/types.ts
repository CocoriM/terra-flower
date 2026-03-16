export interface Plant {
  trefle_id: number;
  common_name: string;
  scientific_name: string;
  plant_type: "flower" | "tree" | "grass";
  family: string;
  image_url: string | null;
  native_regions: string[];
  description?: string;
}

export interface OccurrencePoint {
  lat: number;
  lng: number;
  country: string;
  year: number;
  trefle_id: number;
  plant_type: "flower" | "tree" | "grass";
  plant_name: string;
  image_url: string | null;
}

export interface UserUpload {
  id: string;
  trefle_plant_id: number;
  plant_common_name: string;
  plant_scientific_name: string;
  plant_type: string;
  image_url: string;
  thumbnail_url: string;
  latitude: number | null;
  longitude: number | null;
  location_text: string | null;
  ai_predicted_name: string | null;
  ai_confidence: number | null;
  ai_status:
    | "pending"
    | "approved_auto"
    | "needs_review"
    | "rejected_auto";
  moderation_status: "pending" | "approved" | "rejected";
  moderation_reason: string | null;
  submitted_at: string;
}

export interface User {
  id: string;
  email: string;
  display_name: string;
  role: "contributor" | "moderator" | "admin";
}
