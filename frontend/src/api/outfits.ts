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
  /** Set after photo upload + Gemini tagging (Cloudinary URL). */
  image_url?: string | null
}

export type OutfitCard = {
  items: string[]
  item_details?: Array<{
    id?: string | null
    image_url?: string
    type?: string
    primary_color?: string | null
    pattern?: string | null
    formality?: number | null
  }>
  reasoning: string
  scores: {
    color_match: number
    seasonal_versatility: number
    style_coherence: number
    weather_fit?: number
    trend_relevance?: number
    judge?: {
      style_coherence?: { score: number; reasoning: string }
      color_harmony?: { score: number; reasoning: string }
      occasion_appropriateness?: { score: number; reasoning: string }
      trend_relevance?: { score: number; reasoning: string }
      practicality?: { score: number; reasoning: string }
      overall_score?: number
    }
  }
  overall_score: number
  matched_item?: {
    id?: string | null
    image_url?: string
    type?: string
    primary_color?: string | null
    pattern?: string | null
    formality?: number | null
  }
}

export async function tagHypotheticalPhoto(
  file: File,
): Promise<{ image_url: string; candidate: CandidateItem }> {
  const fd = new FormData()
  fd.append("file", file)
  const r = await fetch(`${BASE}/api/outfits/hypothetical-photo`, {
    method: "POST",
    body: fd,
  })
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(data.detail ?? "Photo tagging failed")
  return data as { image_url: string; candidate: CandidateItem }
}

export async function generateOutfits(body: {
  occasion: string
  weather_temp?: number | null
  weather_conditions?: string | null
  vibe?: string | null
  engine?: "react"
  candidate?: CandidateItem | null
  /** When true, one slot (top / bottom / shoes) uses the hypothetical item if its type matches. */
  include_hypothetical?: boolean
}): Promise<{
  outfits: OutfitCard[]
  debug?: Record<string, unknown>
  shopping_message?: string | null
  suggested_buys?: string[] | null
}> {
  const r = await fetch(`${BASE}/api/outfits/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(data.detail ?? "Outfit generation failed")
  return data as {
    outfits: OutfitCard[]
    debug?: Record<string, unknown>
    shopping_message?: string | null
    suggested_buys?: string[] | null
  }
}

export async function logWearFromOutfit(itemIds: string[]): Promise<void> {
  const r = await fetch(`${BASE}/api/outfits/wear-log`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ item_ids: itemIds, source: "outfit_card" }),
  })
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(data.detail ?? "Could not log wear")
}

