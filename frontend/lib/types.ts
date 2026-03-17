export interface Plant {
  id: string;
  common_name: string;
  common_name_zh: string | null;
  scientific_name: string;
  plant_type: "flower" | "tree" | "grass";
  family: string;
  genus: string;
  description: string | null;
  habitat: string | null;
  hero_image_url: string | null;
  hero_image_attribution: string | null;
  distribution_count: number;
}

export interface GlobeMarker {
  plant_id: string;
  common_name: string;
  plant_type: "flower" | "tree" | "grass";
  lat: number;
  lng: number;
  elevation: number;
  occurrence_count: number;
  hero_image_url: string | null;
}

export interface DistributionPoint {
  lat: number;
  lng: number;
  elevation: number | null;
  country: string;
}

export interface AIResult {
  scientific_name: string;
  common_name: string;
  confidence: number;
  matched_plant_id: string | null;
  matched_plant_image: string | null;
}

export interface UserUpload {
  id: string;
  image_url: string;
  thumbnail_url: string;
  latitude: number | null;
  longitude: number | null;
  ai_best_match_name: string | null;
  ai_best_match_score: number | null;
  ai_top_results: AIResult[];
  confirmed_plant_id: string | null;
  user_confirmed: boolean;
  ai_status:
    | "pending"
    | "approved_auto"
    | "needs_review"
    | "not_identified";
  moderation_status: "pending" | "approved" | "rejected";
  submitted_at: string;
}

export interface User {
  id: string;
  email: string;
  display_name: string;
  role: "contributor" | "moderator" | "admin";
}
