import { API_BASE_URL } from "./utility";

const BASE = API_BASE_URL;

export type ScoredShoppingRow = {
  id: string;
  name: string;
  type: string;
  price: number | null;
  link?: string | null;
  image_url?: string | null;
  utility_score: number;
  adjusted_score: number;
  cost_per_wear: number | null;
};

export type ShoppingRecommendationsResponse = {
  configured: boolean;
  user_id: string;
  items: ScoredShoppingRow[];
};

export type ShoppingRecommendationCreate = {
  name: string;
  type: string;
  primary_color?: string | null;
  secondary_color?: string | null;
  pattern?: string | null;
  formality?: number | null;
  seasons?: string[] | null;
  material?: string | null;
  style_tags?: string[] | null;
  price?: number | null;
  link?: string | null;
  image_url?: string | null;
};

export async function fetchShoppingRecommendations(): Promise<ShoppingRecommendationsResponse> {
  const r = await fetch(`${BASE}/api/shopping/recommendations`);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error((data as { detail?: string }).detail ?? "Failed to load recommendations");
  return data as ShoppingRecommendationsResponse;
}

export async function createShoppingRecommendation(
  body: ShoppingRecommendationCreate,
): Promise<ScoredShoppingRow> {
  const r = await fetch(`${BASE}/api/shopping/recommendations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error((data as { detail?: string }).detail ?? "Failed to save");
  return data as ScoredShoppingRow;
}

export async function deleteShoppingRecommendation(id: string): Promise<void> {
  const r = await fetch(`${BASE}/api/shopping/recommendations/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error((data as { detail?: string }).detail ?? "Failed to delete");
}
