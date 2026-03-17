const BASE = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

export type CandidateItem = {
  type: string;
  primary_color?: string | null;
  secondary_color?: string | null;
  pattern?: string | null;
  formality?: number | null;
  seasons?: string[] | null;
  material?: string | null;
  style_tags?: string[] | null;
  price?: number | null;
};

export type UtilityScore = {
  score: number;
  outfit_potential: number;
  outfit_potential_normalized: number;
  seasonal_versatility: number;
  color_match: number;
  trend_alignment: number;
  gap_filling: number;
  cost_per_wear: number | null;
  color_season: string | null;
};

export async function scoreUtility(candidate: CandidateItem): Promise<UtilityScore> {
  const r = await fetch(`${BASE}/api/utility/score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(candidate),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail ?? "Scoring failed");
  return data as UtilityScore;
}

