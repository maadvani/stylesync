const BASE = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000"

export type Trend = {
  id: string
  name: string
  description: string | null
  keywords: string[] | null
  dominant_colors: string[] | null
  size: number | null
  cluster_id: number | null
  velocity: number | null
  match_score?: number
  wardrobe_coverage?: number
}

export async function listTrends(limit: number = 10): Promise<{ items: Trend[] }> {
  const r = await fetch(`${BASE}/api/trends?limit=${encodeURIComponent(String(limit))}`)
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(data.detail ?? "Failed to load trends")
  return data as { items: Trend[] }
}

