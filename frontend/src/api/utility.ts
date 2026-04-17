export const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";
const BASE = API_BASE_URL;

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
  cost_per_wear: number | null;
  color_season: string | null;
  price_value_penalty?: number;
  max_reasonable_cpw?: number | null;
  expensive_for_value?: boolean;
};

export type AiExplanation = {
  summary: string;
  reasoning: string[];
  confidence: number;
};

export type EnhancedUtilityResponse = {
  score: number;
  adjusted_score: number;
  preference_adjusted_score?: number;
  breakdown: UtilityScore;
  cost_per_wear: number | null;
  ai_explanation: AiExplanation;
  /** Echo of the candidate item the API scored (useful after photo tagging). */
  scored_item?: CandidateItem | null;
};

export type UserPreferencesPayload = {
  preferred_colors?: Record<string, number>;
  preferred_types?: Record<string, number>;
  interaction_history?: unknown[];
};

const FALLBACK_ENHANCED_NOTE =
  "Full enhanced scoring (AI + preference adjustment) was not found on this API (404). Showing the base utility score instead — restart the backend from the latest StyleSync repo so POST /api/utility/enhanced is registered.";

function normalizeEnhancedResponse(r: EnhancedUtilityResponse): EnhancedUtilityResponse {
  const b = r.breakdown;
  const cpw = r.cost_per_wear ?? b?.cost_per_wear ?? null;
  const hasAi =
    r.ai_explanation &&
    typeof r.ai_explanation.summary === "string" &&
    r.ai_explanation.summary.trim() &&
    Array.isArray(r.ai_explanation.reasoning) &&
    r.ai_explanation.reasoning.length > 0;
  const ai = hasAi
    ? r.ai_explanation
    : {
        summary: "Decent",
        reasoning: [
          "No AI summary was included in the API response. Set GEMINI_API_KEY in backend/.env and restart the server for Gemini explanations.",
          "Cost per wear uses your price and predicted outfit count when the backend receives the price field.",
        ],
        confidence: 0.3,
      };
  return { ...r, breakdown: b, cost_per_wear: cpw, ai_explanation: ai };
}

function toEnhancedFromBase(flat: UtilityScore, reasoningLine: string): EnhancedUtilityResponse {
  return normalizeEnhancedResponse({
    score: flat.score,
    adjusted_score: flat.score,
    breakdown: flat,
    cost_per_wear: flat.cost_per_wear,
    ai_explanation: {
      summary: "Decent",
      reasoning: [reasoningLine],
      confidence: 0.25,
    },
  });
}

export async function scoreUtilityEnhanced(
  candidate: CandidateItem,
  userPreferences?: UserPreferencesPayload,
): Promise<EnhancedUtilityResponse> {
  const payload = JSON.stringify({
    item: candidate,
    user_preferences: {
      preferred_colors: userPreferences?.preferred_colors ?? {},
      preferred_types: userPreferences?.preferred_types ?? {},
      interaction_history: userPreferences?.interaction_history ?? [],
    },
  });

  let r = await fetch(`${BASE}/api/utility/enhanced`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: payload,
  });
  let data = await r.json().catch(() => ({}));

  if (r.status === 404) {
    r = await fetch(`${BASE}/api/utility/score`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(candidate),
    });
    data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.detail ?? "Scoring failed");
    return toEnhancedFromBase(data as UtilityScore, FALLBACK_ENHANCED_NOTE);
  }

  if (!r.ok) throw new Error(data.detail ?? "Enhanced scoring failed");

  // Guard: success responses that are still a flat UtilityScore.
  if (
    data &&
    typeof data === "object" &&
    data.adjusted_score == null &&
    typeof data.outfit_potential === "number"
  ) {
    const flat = data as UtilityScore;
    return toEnhancedFromBase(
      flat,
      "The API returned a legacy score shape. Update the backend so POST /api/utility/enhanced returns adjusted_score and ai_explanation.",
    );
  }
  return normalizeEnhancedResponse(data as EnhancedUtilityResponse);
}

function buildScoreImageForm(file: File, price?: number): FormData {
  const form = new FormData();
  form.append("file", file);
  if (typeof price === "number" && Number.isFinite(price)) {
    form.append("price", String(price));
  }
  return form;
}

export async function scoreUtilityEnhancedFromImage(
  file: File,
  price?: number,
): Promise<EnhancedUtilityResponse> {
  let r = await fetch(`${BASE}/api/utility/enhanced-from-image`, {
    method: "POST",
    body: buildScoreImageForm(file, price),
  });
  let data = await r.json().catch(() => ({}));

  if (r.status === 404) {
    r = await fetch(`${BASE}/api/utility/score-from-image`, {
      method: "POST",
      body: buildScoreImageForm(file, price),
    });
    data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.detail ?? "Image scoring failed");
    return toEnhancedFromBase(data as UtilityScore, FALLBACK_ENHANCED_NOTE);
  }

  if (!r.ok) throw new Error(data.detail ?? "Image enhanced scoring failed");
  return normalizeEnhancedResponse(data as EnhancedUtilityResponse);
}

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

export async function scoreUtilityFromImage(file: File, price?: number): Promise<UtilityScore> {
  const r = await fetch(`${BASE}/api/utility/score-from-image`, {
    method: "POST",
    body: buildScoreImageForm(file, price),
  });

  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail ?? "Image scoring failed");
  return data as UtilityScore;
}

