const BASE = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000"

export type CandidateItem = {
  type: string
  primary_color?: string | null
  secondary_color?: string | null
  pattern?: string | null
  formality?: number | null
  seasons?: string[] | null
  material?: string | null
  style_tags?: string[] | null
  price?: number | null
}

export type OutfitCard = {
  items: string[]
  reasoning: string
  scores: {
    color_match: number
    seasonal_versatility: number
    style_coherence: number
  }
  overall_score: number
  matched_item?: {
    id: string
    image_url?: string
    type?: string
    primary_color?: string | null
    pattern?: string | null
    formality?: number | null
  }
}

export async function generateOutfits(body: {
  occasion: string
  weather_temp?: number | null
  weather_conditions?: string | null
  vibe?: string | null
  candidate: CandidateItem
}): Promise<{ outfits: OutfitCard[]; debug?: Record<string, unknown> }> {
  const r = await fetch(`${BASE}/api/outfits/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(data.detail ?? "Outfit generation failed")
  return data as { outfits: OutfitCard[]; debug?: Record<string, unknown> }
}

